import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import get_settings
from app.services.code_generator import generate_pipeline_code
from app.services.report_generator import generate_report


def write_pipeline_exports(
    project_id: int,
    pipeline_id: int,
    pipeline_run_id: int,
    mode: str,
    target_column: str | None,
    problem_type: str,
    input_file_names: list[str],
    before_summary: dict[str, Any],
    after_summary: dict[str, Any],
    step_effects: list[dict[str, Any]],
    fitted_params: list[dict[str, Any]],
    warnings: list[str],
    single_df: pd.DataFrame | None = None,
    train_df: pd.DataFrame | None = None,
    test_df: pd.DataFrame | None = None,
) -> dict[str, str]:
    settings = get_settings()
    export_dir = Path(settings.export_dir) / f"project_{project_id}" / f"pipeline_run_{pipeline_run_id}"
    export_dir.mkdir(parents=True, exist_ok=True)

    output_paths: dict[str, str] = {}
    output_file_names: list[str] = []

    if mode == "single":
        if single_df is None:
            raise ValueError("single_df is required for single mode export")
        cleaned_path = export_dir / "cleaned_dataset.csv"
        single_df.to_csv(cleaned_path, index=False)
        output_paths["cleaned_single"] = str(cleaned_path)
        output_file_names.append(cleaned_path.name)
    else:
        if train_df is None or test_df is None:
            raise ValueError("train_df and test_df are required for train_test mode export")
        train_path = export_dir / "clean_train.csv"
        test_path = export_dir / "clean_test.csv"
        train_df.to_csv(train_path, index=False)
        test_df.to_csv(test_path, index=False)
        output_paths["cleaned_train"] = str(train_path)
        output_paths["cleaned_test"] = str(test_path)
        output_file_names.extend([train_path.name, test_path.name])

    config = {
        "project_id": project_id,
        "pipeline_id": pipeline_id,
        "pipeline_run_id": pipeline_run_id,
        "mode": mode,
        "target_column": target_column,
        "problem_type": problem_type,
        "steps": fitted_params,
        "input_file_names": input_file_names,
        "output_file_names": output_file_names,
    }

    config_path = export_dir / "preprocessing_config.json"
    report_path = export_dir / "preprocessing_report.md"
    code_path = export_dir / "pipeline_code.py"

    config_path.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    report_path.write_text(generate_report(config, before_summary, after_summary, step_effects, warnings), encoding="utf-8")
    code_path.write_text(generate_pipeline_code(config), encoding="utf-8")

    output_paths["config"] = str(config_path)
    output_paths["report"] = str(report_path)
    output_paths["code"] = str(code_path)
    return output_paths
