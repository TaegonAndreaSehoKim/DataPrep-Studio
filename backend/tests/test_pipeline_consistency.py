import pandas as pd
import pytest

from app.services.code_generator import generate_pipeline_code
from app.services.pipeline_engine import PipelineStepSpec, apply_pipeline_train_test
from app.services.transformations import TransformationError


def _replay(result, train, test):
    namespace = {"__name__": "replay"}
    exec(generate_pipeline_code({"mode": "train_test", "steps": result.fitted_params}), namespace)
    replay_train, replay_test = namespace["preprocess_train_test"](train, test)
    pd.testing.assert_frame_equal(result.train_df, replay_train)
    pd.testing.assert_frame_equal(result.test_df, replay_test)


@pytest.mark.parametrize("strategy,params,fill", [
    ("mean", {}, 15), ("median", {}, 15), ("constant", {"fill_value": 0}, 0),
])
def test_numeric_imputation_coerces_both_splits_and_replays(strategy, params, fill):
    train = pd.DataFrame({"x": [10, 20, None]})
    test = pd.DataFrame({"x": ["10", "bad", None]})
    original = test.copy(deep=True)
    result = apply_pipeline_train_test(train, test, [
        PipelineStepSpec(1, 0, True, "numeric_imputation", ["x"], {"strategy": strategy, **params}),
    ])
    assert result.test_df["x"].tolist() == [10, fill, fill]
    pd.testing.assert_frame_equal(test, original)
    _replay(result, train, test)


@pytest.mark.parametrize("operation,params", [
    ("numeric_imputation", {}), ("numeric_scaling", {}), ("outlier_clipping", {}),
    ("one_hot_encoding", {}), ("rare_category_grouping", {}),
    ("ordinal_encoding", {}), ("frequency_encoding", {}), ("add_missing_indicator", {}),
])
def test_missing_test_feature_is_rejected(operation, params):
    with pytest.raises(TransformationError, match="Columns do not exist: x"):
        apply_pipeline_train_test(pd.DataFrame({"x": [10, 20, 30]}), pd.DataFrame({"other": [1]}), [
            PipelineStepSpec(1, 0, True, operation, ["x"], params),
        ])


@pytest.mark.parametrize("method", ["standard", "minmax", "robust"])
def test_scaling_ignores_test_statistics_and_replays(method):
    train = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    test = pd.DataFrame({"x": [100.0, 200.0]})
    steps = [PipelineStepSpec(1, 0, True, "numeric_scaling", ["x"], {"method": method})]
    result = apply_pipeline_train_test(train, test, steps)
    other = apply_pipeline_train_test(train, pd.DataFrame({"x": [-1e9, 1e9]}), steps)
    assert result.fitted_params == other.fitted_params
    pd.testing.assert_frame_equal(result.train_df, other.train_df)
    if method == "robust":
        assert result.train_df["x"].iloc[1] == 0
    _replay(result, train, test)


@pytest.mark.parametrize("missing_count,expected", [(1, "__RARE__"), (2, "__MISSING__")])
def test_rare_grouping_missing_option_uses_train_frequencies(missing_count, expected):
    train = pd.DataFrame({"x": ["a", "a", "b"] + [None] * missing_count})
    test = pd.DataFrame({"x": [None, "unseen", "a"]})
    result = apply_pipeline_train_test(train, test, [
        PipelineStepSpec(1, 0, True, "rare_category_grouping", ["x"], {"include_missing": True, "min_count": 2}),
    ])
    assert result.test_df["x"].tolist() == [expected, "__RARE__", "a"]
    _replay(result, train, test)


def test_datetime_format_is_fit_on_train_and_replayed():
    train = pd.DataFrame({"date": ["01/02/2024", "03/04/2024"]})
    test = pd.DataFrame({"date": ["13/02/2024", "01/02/2024"]})
    result = apply_pipeline_train_test(train, test, [
        PipelineStepSpec(1, 0, True, "datetime_extract", ["date"], {}),
    ])
    assert result.fitted_params[0]["fitted"]["date_formats"] == {"date": "%m/%d/%Y"}
    assert result.test_df["date_month"].iloc[1] == result.train_df["date_month"].iloc[0] == 1
    assert pd.isna(result.test_df["date_month"].iloc[0])
    assert pd.isna(result.test_df["date_is_weekend"].iloc[0])
    _replay(result, train, test)


@pytest.mark.parametrize("operation,params", [
    ("numeric_imputation", {"strategy": "mean"}), ("numeric_imputation", {"strategy": "median"}),
    ("numeric_scaling", {}), ("outlier_clipping", {}),
])
def test_empty_train_statistics_require_an_explicit_strategy(operation, params):
    with pytest.raises(TransformationError, match="finite train|finite train imputation"):
        apply_pipeline_train_test(pd.DataFrame({"x": [float("nan")]}), pd.DataFrame({"x": [100]}), [
            PipelineStepSpec(1, 0, True, operation, ["x"], params),
        ])
