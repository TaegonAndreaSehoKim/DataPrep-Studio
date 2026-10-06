import pandas as pd
import pytest

from app.services.code_generator import generate_pipeline_code
from app.services.pipeline_engine import PipelineStepSpec, apply_pipeline_single, apply_pipeline_train_test
from app.services.transformations import TransformationError


def test_one_hot_names_preserve_categories_existing_features_and_replay():
    train = pd.DataFrame({"city": ["A-B", "A B", "A_B", "C"], "city_A_B": [10, 20, 30, 40]})
    test = pd.DataFrame({"city": ["A B", "A-B", "unseen"], "city_A_B": [50, 60, 70]})
    result = apply_pipeline_train_test(train, test, [PipelineStepSpec(1, 0, True, "one_hot_encoding", ["city"], {})])
    mapping = result.fitted_params[0]["fitted"]["output_columns"]["city"]
    assert len(set(mapping.values())) == 4
    assert "city_A_B" not in mapping.values()
    assert result.train_df["city_A_B"].tolist() == [10, 20, 30, 40]
    for category in ["A-B", "A B", "A_B", "C"]:
        assert result.train_df[mapping[category]].tolist() == (train["city"] == category).astype(int).tolist()
    assert result.train_df.columns.tolist() == result.test_df.columns.tolist()
    assert result.test_df[list(mapping.values())].iloc[-1].sum() == 0
    namespace = {"__name__": "replay"}
    exec(generate_pipeline_code({"mode": "train_test", "steps": result.fitted_params}), namespace)
    replay_train, replay_test = namespace["preprocess_train_test"](train, test)
    pd.testing.assert_frame_equal(result.train_df, replay_train)
    pd.testing.assert_frame_equal(result.test_df, replay_test)


def test_one_hot_rejects_test_only_output_name_collision():
    with pytest.raises(TransformationError, match="Generated column already exists"):
        apply_pipeline_train_test(pd.DataFrame({"city": ["A", "B"]}), pd.DataFrame({"city": ["A"], "city_A": [42]}), [
            PipelineStepSpec(1, 0, True, "one_hot_encoding", ["city"], {}),
        ])


@pytest.mark.parametrize("operation,params,source,generated", [
    ("add_missing_indicator", {}, [1, None], "x_was_missing"),
    ("log_transform", {"replace_original": False}, [1, 2], "x_log"),
    ("datetime_extract", {"features": ["year"]}, ["2024-01-01", "2024-02-01"], "x_year"),
    ("text_basic_features", {}, ["hello", "world"], "x_length"),
    ("rename_columns", {"rename_map": {"x": "existing"}}, [1, 2], "existing"),
])
def test_derived_features_cannot_silently_overwrite_source_columns(operation, params, source, generated):
    frame = pd.DataFrame({"x": source, generated: [123, 456]})
    original = frame.copy(deep=True)
    with pytest.raises(TransformationError, match="already exists|conflict"):
        apply_pipeline_single(frame, [PipelineStepSpec(1, 0, True, operation, ["x"], params)])
    pd.testing.assert_frame_equal(frame, original)
