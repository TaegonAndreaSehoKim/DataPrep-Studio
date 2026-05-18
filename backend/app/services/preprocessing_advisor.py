import json
from collections import OrderedDict

from app.models import ColumnProfile, Issue
from app.schemas import PreprocessingRecommendationOut, SuggestedPipelineStepOut
from app.services.suggestion_builder import build_suggested_step


SEVERITY_PRIORITY = {
    "critical": "critical",
    "warning": "high",
    "info": "low",
}

PRIORITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _merge_columns(current: list[str], incoming: list[str]) -> list[str]:
    merged = list(current)
    for column in incoming:
        if column not in merged:
            merged.append(column)
    return merged


def _recommendation_title(category: str, suggestion: SuggestedPipelineStepOut) -> str:
    if suggestion.operation_type == "remove_duplicate_rows":
        return "Remove duplicate rows"
    if suggestion.operation_type == "replace_placeholder_values":
        return "Normalize placeholder missing values"
    if suggestion.operation_type == "numeric_imputation":
        return "Impute numeric missing values"
    if suggestion.operation_type == "categorical_imputation":
        return "Impute categorical missing values"
    if suggestion.operation_type == "text_basic_features":
        return "Create basic text preprocessing features"
    if suggestion.operation_type == "outlier_clipping":
        return "Clip numeric outliers"
    if suggestion.operation_type == "rare_category_grouping":
        return "Group rare categories"
    if suggestion.operation_type == "drop_columns":
        if category == "leakage":
            return "Review and drop leakage-prone columns"
        if category == "cardinality":
            return "Drop likely identifier columns"
        if category == "constant":
            return "Drop constant or near-constant columns"
        return "Drop low-value columns"
    if suggestion.operation_type == "add_missing_indicator":
        return "Add missingness indicator columns"
    return f"Apply {suggestion.operation_type}"


def _manual_recommendation(issue: Issue) -> PreprocessingRecommendationOut | None:
    columns = [str(column) for column in _json_loads(issue.affected_columns_json, [])]
    priority = SEVERITY_PRIORITY.get(issue.severity, "medium")
    if issue.category == "target":
        return PreprocessingRecommendationOut(
            priority=priority,  # type: ignore[arg-type]
            category=issue.category,
            title=issue.title,
            rationale=f"{issue.explanation} This is not an in-place feature preprocessing step; handle it through split strategy, validation design, or model training settings.",
            affected_columns=columns,
            issue_ids=[issue.id],
            suggested_step=None,
        )
    if issue.category == "split":
        return PreprocessingRecommendationOut(
            priority=priority,  # type: ignore[arg-type]
            category=issue.category,
            title=issue.title,
            rationale=f"{issue.explanation} Resolve the split issue before trusting preprocessing previews or model validation.",
            affected_columns=columns,
            issue_ids=[issue.id],
            suggested_step=None,
        )
    if issue.category == "drift":
        return PreprocessingRecommendationOut(
            priority="medium",
            category=issue.category,
            title=issue.title,
            rationale=f"{issue.explanation} Use train-only fitted preprocessing and inspect whether the split reflects deployment data.",
            affected_columns=columns,
            issue_ids=[issue.id],
            suggested_step=None,
        )
    return None


def build_preprocessing_recommendations(
    analysis_id: int,
    issues: list[Issue],
    profiles: list[ColumnProfile],
) -> tuple[list[PreprocessingRecommendationOut], list[str]]:
    grouped: OrderedDict[tuple[str, str, str], PreprocessingRecommendationOut] = OrderedDict()
    manual: list[PreprocessingRecommendationOut] = []

    for issue in issues:
        suggestion = build_suggested_step(issue, profiles)
        if suggestion is None:
            manual_recommendation = _manual_recommendation(issue)
            if manual_recommendation is not None:
                manual.append(manual_recommendation)
            continue

        priority = SEVERITY_PRIORITY.get(issue.severity, "medium")
        key = (issue.category, suggestion.operation_type, json.dumps(suggestion.params, sort_keys=True))
        if key not in grouped:
            grouped[key] = PreprocessingRecommendationOut(
                priority=priority,  # type: ignore[arg-type]
                category=issue.category,
                title=_recommendation_title(issue.category, suggestion),
                rationale=suggestion.reason,
                affected_columns=[] if suggestion.operation_type == "remove_duplicate_rows" else list(suggestion.columns),
                issue_ids=[issue.id],
                suggested_step=SuggestedPipelineStepOut(
                    operation_type=suggestion.operation_type,
                    columns=list(suggestion.columns),
                    params=suggestion.params,
                    reason=suggestion.reason,
                ),
            )
            continue

        existing = grouped[key]
        existing.issue_ids.append(issue.id)
        existing.affected_columns = _merge_columns(existing.affected_columns, suggestion.columns)
        if existing.suggested_step is not None:
            existing.suggested_step.columns = _merge_columns(existing.suggested_step.columns, suggestion.columns)
        if PRIORITY_RANK[priority] < PRIORITY_RANK[existing.priority]:
            existing.priority = priority  # type: ignore[assignment]

    recommendations = list(grouped.values()) + manual
    recommendations.sort(key=lambda item: (PRIORITY_RANK[item.priority], item.category, item.title))
    notes = [
        "Recommendations are advisory and should be reviewed before applying.",
        "In train/test mode, learned preprocessing parameters must be fit on train only.",
    ]
    if not recommendations:
        notes.insert(0, f"No preprocessing recommendations were generated for analysis {analysis_id}.")
    return recommendations, notes
