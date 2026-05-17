import pandas as pd

from app.services.pipeline_engine import PipelineStepSpec, apply_pipeline_single, apply_pipeline_train_test


def test_pipeline_engine_single_core_operations():
    df = pd.DataFrame(
        {
            "age": [10, None, 30, 1000],
            "city": ["Seattle", None, "Austin", "Tiny"],
            "id": [1, 2, 3, 4],
        }
    )
    steps = [
        PipelineStepSpec(1, 0, True, "add_missing_indicator", ["age"], {"suffix": "_was_missing"}),
        PipelineStepSpec(2, 1, True, "numeric_imputation", ["age"], {"strategy": "median"}),
        PipelineStepSpec(3, 2, True, "categorical_imputation", ["city"], {"strategy": "constant", "fill_value": "__MISSING__"}),
        PipelineStepSpec(4, 3, True, "drop_columns", ["id"], {}),
        PipelineStepSpec(5, 4, True, "outlier_clipping", ["age"], {"method": "iqr", "iqr_multiplier": 1.5}),
    ]

    result = apply_pipeline_single(df, steps)

    assert result.single_df is not None
    assert "id" not in result.single_df.columns
    assert "age_was_missing" in result.single_df.columns
    assert result.single_df["age"].isna().sum() == 0
    assert len(result.step_effects or []) == 5


def test_train_test_pipeline_fits_categories_on_train_only():
    train_df = pd.DataFrame({"city": ["Seattle", "Austin", "Seattle"], "income": [10, 20, 30]})
    test_df = pd.DataFrame({"city": ["Miami", "Seattle"], "income": [100, 200]})
    steps = [
        PipelineStepSpec(1, 0, True, "rare_category_grouping", ["city"], {"min_count": 2, "rare_label": "__RARE__"}),
        PipelineStepSpec(2, 1, True, "one_hot_encoding", ["city"], {}),
        PipelineStepSpec(3, 2, True, "numeric_scaling", ["income"], {"method": "standard"}),
    ]

    result = apply_pipeline_train_test(train_df, test_df, steps)

    assert result.train_df is not None
    assert result.test_df is not None
    assert "city_Seattle" in result.train_df.columns
    assert "city_Seattle" in result.test_df.columns
    assert result.test_df["city_Seattle"].tolist() == [0, 1]
    scaling = result.fitted_params[2]["fitted"]["stats"]["income"]
    assert scaling["mean"] == 20.0
    assert result.test_df["income"].iloc[0] > 9
