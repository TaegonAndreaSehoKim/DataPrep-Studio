from pathlib import Path

import json
import numpy as np
import pandas as pd
import pytest

from app.services.drift_detector import detect_train_test_drift
from app.services.drift_detector import _numeric_shift, _categorical_shift
from app.services.profiler import profile_dataframe


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_train_test_drift_detects_unseen_categories_and_overlap():
    train_df = pd.read_csv(FIXTURE_DIR / "train_drift.csv")
    test_df = pd.read_csv(FIXTURE_DIR / "test_drift.csv")
    profiles = profile_dataframe(train_df, "train", "target")

    result = detect_train_test_drift(train_df, test_df, profiles, "target")

    assert result.drift_score > 0
    assert result.summary["row_overlap"]["overlap_count"] == 1
    assert result.summary["columns"]["city"]["unseen_category_count"] == 2
    assert any(issue.category == "drift" for issue in result.issues)
    assert any(issue.category == "split" for issue in result.issues)


def test_train_test_target_distribution_comparison():
    train_df = pd.read_csv(FIXTURE_DIR / "train_drift.csv")
    test_df = pd.read_csv(FIXTURE_DIR / "test_drift.csv")
    profiles = profile_dataframe(train_df, "train", "target")

    result = detect_train_test_drift(train_df, test_df, profiles, "target")
    target = result.summary["target_distribution"]

    assert target["max_class_rate_delta"] >= 0.5
    assert target["drift_flag"] is True


def test_numeric_drift_detects_spread_change_with_identical_means():
    train = pd.DataFrame({"value": [-1.0, 1.0] * 20})
    test = pd.DataFrame({"value": [-10.0, 10.0] * 20})
    result = detect_train_test_drift(train, test, profile_dataframe(train, "train", column_type_overrides={"value": "numeric"}), None)
    column = result.summary["columns"]["value"]
    assert column["standardized_mean_diff"] == 0
    assert column["std_ratio"] == pytest.approx(10)
    assert column["variance_shift_flag"] and column["drift_flag"]
    assert any(issue.title == "Numeric drift in value" for issue in result.issues)


def test_numeric_drift_detects_shape_change_with_identical_mean_and_variance():
    train = pd.Series([-1.0, 1.0] * 50)
    test = pd.Series([0.0] * 80 + [-np.sqrt(5)] * 10 + [np.sqrt(5)] * 10)
    column = _numeric_shift(train, test)
    assert column["standardized_mean_diff"] == pytest.approx(0, abs=1e-12)
    assert column["std_ratio"] == pytest.approx(1)
    assert not column["mean_shift_flag"] and not column["variance_shift_flag"]
    assert column["distribution_distance"] == pytest.approx(0.4)
    assert column["distribution_shift_flag"] and column["drift_flag"]


def test_categorical_drift_detects_proportion_change_without_unseen_categories():
    train = pd.DataFrame({"city": ["A"] * 90 + ["B"] * 10})
    test = pd.DataFrame({"city": ["A"] * 10 + ["B"] * 90})
    result = detect_train_test_drift(train, test, profile_dataframe(train, "train"), None)
    column = result.summary["columns"]["city"]
    assert column["unseen_category_count"] == 0
    assert column["total_variation_distance"] == pytest.approx(0.8)
    assert column["proportion_shift_flag"] and column["drift_flag"]
    assert any(issue.title == "Category proportion drift in city" for issue in result.issues)


def test_equal_distributions_with_different_sample_counts_do_not_flag_drift():
    numeric = _numeric_shift(pd.Series([0.0, 1.0, 2.0] * 20), pd.Series([0.0, 1.0, 2.0] * 10))
    categorical = _categorical_shift(pd.Series(["A", "A", "B"] * 20), pd.Series(["B", "A", "A"] * 10))
    assert numeric["distribution_distance"] == 0 and not numeric["drift_flag"]
    assert categorical["total_variation_distance"] == 0 and not categorical["drift_flag"]


def test_constant_and_missing_numeric_values_produce_finite_serializable_metrics():
    constant = _numeric_shift(pd.Series([2.0] * 20), pd.Series([2.0] * 20))
    assert not constant["drift_flag"]
    dispersed = _numeric_shift(pd.Series([0.0] * 20), pd.Series([-1.0, 1.0] * 10))
    assert dispersed["std_ratio"] is None and dispersed["variance_shift_flag"]
    insufficient = _numeric_shift(pd.Series([np.inf, np.nan, 1.0]), pd.Series([1.0, 2.0]))
    assert insufficient["status"] == "insufficient_data" and insufficient["train_count"] == 1
    empty_categories = _categorical_shift(pd.Series([None, None]), pd.Series(["A"]))
    assert empty_categories["status"] == "insufficient_data" and not empty_categories["drift_flag"]
    json.dumps([constant, dispersed, insufficient, empty_categories], allow_nan=False)


def test_regression_target_uses_numeric_distribution_metrics():
    train = pd.DataFrame({"target": np.arange(10, 30, dtype=float)})
    test = pd.DataFrame({"target": np.arange(10, 30, dtype=float) + 0.01})
    result = detect_train_test_drift(train, test, profile_dataframe(train, "train", "target", "regression"), "target", "regression")
    target = result.summary["target_distribution"]
    assert target["kind"] == "numeric" and not target["drift_flag"]
    assert "max_class_rate_delta" not in target
