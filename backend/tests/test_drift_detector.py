from pathlib import Path

import pandas as pd

from app.services.drift_detector import detect_train_test_drift
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
