from app.services.report_generator import generate_report
from app.services.code_generator import generate_pipeline_code


def test_markdown_report_includes_key_sections():
    report = generate_report(
        {
            "project_id": 1,
            "pipeline_id": 2,
            "mode": "single",
            "input_file_names": ["input.csv"],
            "output_file_names": ["cleaned.csv"],
            "steps": [
                {
                    "step_id": 10,
                    "operation_type": "numeric_imputation",
                    "columns": ["age"],
                    "params": {"strategy": "median"},
                }
            ],
        },
        {"row_count": 3, "missing_cells": 1},
        {"row_count": 3, "missing_cells": 0},
        [{"summary": "Filled values"}],
        [],
    )

    assert "# DataPrep Studio Preprocessing Report" in report
    assert "## Pipeline Steps" in report
    assert "## Before Summary" in report
    assert "## After Summary" in report
    assert "## Notes on Leakage-Safe Train/Test Processing" in report
    assert '- Step 10: `numeric_imputation`' in report
    assert '"missing_cells": 1' in report
    assert "{'row_count': 3" not in report


def test_generated_pipeline_code_replays_fitted_steps():
    config = {
        "mode": "single",
        "pipeline_id": 1,
        "steps": [
            {
                "step_id": 1,
                "operation_type": "numeric_imputation",
                "columns": ["age"],
                "params": {"strategy": "median"},
                "fitted": {"strategy": "median", "fill_values": {"age": 30}},
            },
            {
                "step_id": 2,
                "operation_type": "drop_columns",
                "columns": ["city"],
                "params": {},
                "fitted": {"columns": ["city"]},
            },
        ],
    }
    code = generate_pipeline_code(config)
    namespace: dict[str, object] = {}

    exec(code, namespace)

    import pandas as pd

    df = pd.DataFrame({"age": [10, None], "city": ["Seattle", "Austin"]})
    output = namespace["preprocess_single"](df)
    assert output["age"].tolist() == [10, 30]
    assert "city" not in output.columns
