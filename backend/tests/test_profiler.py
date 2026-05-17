from pathlib import Path

import pandas as pd

from app.services.profiler import profile_dataframe


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_profile_dataframe_basic_types_and_missingness():
    df = pd.read_csv(FIXTURE_DIR / "dirty_missing_values.csv")

    profiles = profile_dataframe(df, "single", "target")
    by_name = {profile.column_name: profile for profile in profiles}

    assert by_name["age"].inferred_type == "numeric"
    assert by_name["age"].missing_count == 1
    assert by_name["age"].missing_rate == 0.2
    assert by_name["city"].inferred_type == "categorical"
    assert by_name["notes"].inferred_type in {"categorical", "text"}
    assert by_name["target"].summary["is_target"] is True


def test_numeric_profile_contains_distribution_summary():
    df = pd.read_csv(FIXTURE_DIR / "dirty_missing_values.csv")

    profile = {item.column_name: item for item in profile_dataframe(df, "single")}["income"]

    assert profile.inferred_type == "numeric"
    assert "mean" in profile.summary
    assert "outlier_count_iqr" in profile.summary


def test_profile_honors_column_type_override_and_numeric_classification_target():
    df = pd.DataFrame({"quality": [5, 6, 5, 7], "zip_code": [2139, 10001, 2139, 94105]})

    profiles = profile_dataframe(
        df,
        "single",
        target_column="quality",
        problem_type="classification",
        column_type_overrides={"zip_code": "categorical"},
    )
    by_name = {profile.column_name: profile for profile in profiles}

    assert by_name["zip_code"].inferred_type == "categorical"
    assert "user_type_override" in by_name["zip_code"].warnings
    assert by_name["quality"].summary["class_counts"] == {"5": 2, "6": 1, "7": 1}
    assert by_name["quality"].summary["majority_class"] == "5"
