from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.services.issue_detector import detect_issues
from app.services.profiler import profile_dataframe
from app.services.readiness_score import calculate_readiness_score
from app.services.transformations import StepEffect, TransformationError, fit_transform_step, transform_step


@dataclass(frozen=True)
class PipelineStepSpec:
    id: int
    order_index: int
    enabled: bool
    operation_type: str
    columns: list[str]
    params: dict[str, Any]


@dataclass
class PipelineResult:
    single_df: pd.DataFrame | None = None
    train_df: pd.DataFrame | None = None
    test_df: pd.DataFrame | None = None
    step_effects: list[dict[str, Any]] | None = None
    fitted_params: list[dict[str, Any]] | None = None
    warnings: list[str] | None = None


def summarize_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    missing_cells = int(df.isna().sum().sum())
    total_cells = int(max(df.shape[0] * df.shape[1], 1))
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "missing_cells": missing_cells,
        "missing_rate": float(missing_cells / total_cells),
        "columns": [str(column) for column in df.columns],
    }


def readiness_for_dataframe(df: pd.DataFrame, target_column: str | None, problem_type: str) -> dict[str, Any]:
    profiles = profile_dataframe(df, "single", target_column if target_column in df.columns else None)
    issues = detect_issues(df, profiles, target_column if target_column in df.columns else None, problem_type)
    score, breakdown = calculate_readiness_score(issues)
    return {"score": score, "breakdown": breakdown, "issue_count": len(issues)}


def _sample_rows(df: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    sample = df.head(limit)
    return sample.astype(object).where(sample.notna(), None).to_dict(orient="records")


def _values_differ(before_value: Any, after_value: Any) -> bool:
    before_missing = bool(pd.isna(before_value))
    after_missing = bool(pd.isna(after_value))
    if before_missing or after_missing:
        return before_missing != after_missing
    return bool(before_value != after_value)


def _changed_sample_count(before: pd.Series, after: pd.Series) -> int:
    shared_index = before.index.intersection(after.index)[:1000]
    if len(shared_index) == 0:
        return 0
    return int(
        sum(
            _values_differ(before.loc[index], after.loc[index])
            for index in shared_index
        )
    )


def _column_diffs(before_df: pd.DataFrame, after_df: pd.DataFrame) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    before_columns = [str(column) for column in before_df.columns]
    after_columns = [str(column) for column in after_df.columns]
    ordered_columns = before_columns + [column for column in after_columns if column not in before_columns]

    for column in ordered_columns:
        before_exists = column in before_df.columns
        after_exists = column in after_df.columns
        before_missing_count = int(before_df[column].isna().sum()) if before_exists else None
        after_missing_count = int(after_df[column].isna().sum()) if after_exists else None
        before_non_null_count = int(before_df[column].notna().sum()) if before_exists else None
        after_non_null_count = int(after_df[column].notna().sum()) if after_exists else None
        before_dtype = str(before_df[column].dtype) if before_exists else None
        after_dtype = str(after_df[column].dtype) if after_exists else None
        changed_sample_count: int | None = None

        if before_exists and after_exists:
            changed_sample_count = _changed_sample_count(before_df[column], after_df[column])
            status = "changed" if (
                before_missing_count != after_missing_count
                or before_dtype != after_dtype
                or changed_sample_count > 0
            ) else "unchanged"
        elif before_exists:
            status = "removed"
        else:
            status = "added"

        diffs.append(
            {
                "column_name": column,
                "status": status,
                "before_missing_count": before_missing_count,
                "after_missing_count": after_missing_count,
                "before_non_null_count": before_non_null_count,
                "after_non_null_count": after_non_null_count,
                "changed_sample_count": changed_sample_count,
                "before_dtype": before_dtype,
                "after_dtype": after_dtype,
            }
        )

    status_rank = {"changed": 0, "added": 1, "removed": 2, "unchanged": 3}
    return sorted(diffs, key=lambda item: (status_rank[str(item["status"])], str(item["column_name"])))


def _effect_to_dict(step: PipelineStepSpec, effect: StepEffect, fitted: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_id": step.id,
        "operation_type": step.operation_type,
        "columns": step.columns,
        "summary": effect.summary,
        "before": effect.before,
        "after": effect.after,
        "warnings": effect.warnings,
        "fitted_params": fitted,
    }


def apply_pipeline_single(df: pd.DataFrame, steps: list[PipelineStepSpec]) -> PipelineResult:
    working = df.copy()
    effects: list[dict[str, Any]] = []
    fitted_params: list[dict[str, Any]] = []
    warnings: list[str] = []

    for step in sorted([item for item in steps if item.enabled], key=lambda item: item.order_index):
        try:
            working, fitted, effect = fit_transform_step(working, step.operation_type, step.columns, step.params)
        except TransformationError as exc:
            raise TransformationError(f"Step {step.id} failed: {exc}") from exc
        fitted_entry = {"step_id": step.id, "operation_type": step.operation_type, "columns": step.columns, "params": step.params, "fitted": fitted}
        fitted_params.append(fitted_entry)
        effects.append(_effect_to_dict(step, effect, fitted))
        warnings.extend(effect.warnings)

    return PipelineResult(single_df=working, step_effects=effects, fitted_params=fitted_params, warnings=warnings)


def apply_pipeline_train_test(train_df: pd.DataFrame, test_df: pd.DataFrame, steps: list[PipelineStepSpec]) -> PipelineResult:
    train_working = train_df.copy()
    test_working = test_df.copy()
    effects: list[dict[str, Any]] = []
    fitted_params: list[dict[str, Any]] = []
    warnings: list[str] = []

    for step in sorted([item for item in steps if item.enabled], key=lambda item: item.order_index):
        try:
            train_working, fitted, train_effect = fit_transform_step(train_working, step.operation_type, step.columns, step.params)
            test_working, test_effect = transform_step(test_working, step.operation_type, step.columns, fitted)
        except TransformationError as exc:
            raise TransformationError(f"Step {step.id} failed: {exc}") from exc
        fitted_entry = {"step_id": step.id, "operation_type": step.operation_type, "columns": step.columns, "params": step.params, "fitted": fitted}
        fitted_params.append(fitted_entry)
        effect = _effect_to_dict(step, train_effect, fitted)
        effect["test_summary"] = test_effect.summary
        effects.append(effect)
        warnings.extend(train_effect.warnings)
        warnings.extend(test_effect.warnings)

    return PipelineResult(train_df=train_working, test_df=test_working, step_effects=effects, fitted_params=fitted_params, warnings=warnings)


def preview_single(
    df: pd.DataFrame,
    steps: list[PipelineStepSpec],
    target_column: str | None,
    problem_type: str,
    limit: int,
) -> dict[str, Any]:
    before_summary = summarize_dataframe(df)
    before_summary["readiness"] = readiness_for_dataframe(df, target_column, problem_type)
    result = apply_pipeline_single(df, steps)
    assert result.single_df is not None
    after_summary = summarize_dataframe(result.single_df)
    after_summary["readiness"] = readiness_for_dataframe(result.single_df, target_column, problem_type)
    affected = sorted({column for step in steps if step.enabled for column in step.columns})
    return {
        "before_summary": before_summary,
        "after_summary": after_summary,
        "affected_columns": affected,
        "before_sample_rows": _sample_rows(df, limit),
        "sample_rows": _sample_rows(result.single_df, limit),
        "column_diffs": _column_diffs(df, result.single_df),
        "step_effects": result.step_effects or [],
        "warnings": result.warnings or [],
        "fitted_params": result.fitted_params or [],
    }


def preview_train_test(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    steps: list[PipelineStepSpec],
    target_column: str | None,
    problem_type: str,
    limit: int,
) -> dict[str, Any]:
    before_summary = {"train": summarize_dataframe(train_df), "test": summarize_dataframe(test_df)}
    result = apply_pipeline_train_test(train_df, test_df, steps)
    assert result.train_df is not None and result.test_df is not None
    after_summary = {"train": summarize_dataframe(result.train_df), "test": summarize_dataframe(result.test_df)}
    after_summary["train"]["readiness"] = readiness_for_dataframe(result.train_df, target_column, problem_type)
    affected = sorted({column for step in steps if step.enabled for column in step.columns})
    return {
        "before_summary": before_summary,
        "after_summary": after_summary,
        "affected_columns": affected,
        "before_sample_rows": _sample_rows(train_df, limit),
        "sample_rows": _sample_rows(result.train_df, limit),
        "column_diffs": _column_diffs(train_df, result.train_df),
        "step_effects": result.step_effects or [],
        "warnings": ["Train/test mode fits preprocessing parameters on train only."] + (result.warnings or []),
        "fitted_params": result.fitted_params or [],
    }
