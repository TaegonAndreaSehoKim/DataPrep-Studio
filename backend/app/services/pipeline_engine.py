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
    sample = result.single_df.head(limit).astype(object).where(result.single_df.head(limit).notna(), None).to_dict(orient="records")
    return {
        "before_summary": before_summary,
        "after_summary": after_summary,
        "affected_columns": affected,
        "sample_rows": sample,
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
    sample = result.train_df.head(limit).astype(object).where(result.train_df.head(limit).notna(), None).to_dict(orient="records")
    return {
        "before_summary": before_summary,
        "after_summary": after_summary,
        "affected_columns": affected,
        "sample_rows": sample,
        "step_effects": result.step_effects or [],
        "warnings": ["Train/test mode fits preprocessing parameters on train only."] + (result.warnings or []),
        "fitted_params": result.fitted_params or [],
    }
