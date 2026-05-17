import json
from collections import OrderedDict

from app.models import ColumnProfile, Issue
from app.schemas import SuggestedPipelineStepOut


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def build_suggested_step(issue: Issue, profiles: list[ColumnProfile]) -> SuggestedPipelineStepOut | None:
    columns = [str(column) for column in _json_loads(issue.affected_columns_json, [])]
    by_column = {profile.column_name: profile for profile in profiles}
    column_types = [by_column[column].inferred_type for column in columns if column in by_column]
    first_column_type = column_types[0] if column_types else "unknown"

    if issue.category == "duplicate":
        return SuggestedPipelineStepOut(
            operation_type="remove_duplicate_rows",
            columns=[],
            params={"subset": [], "keep": "first"},
            reason="Duplicate rows can usually be removed before modeling after domain review.",
        )

    if issue.category == "missingness" and columns:
        if "Placeholder values" in issue.title:
            return SuggestedPipelineStepOut(
                operation_type="replace_placeholder_values",
                columns=columns,
                params={"placeholders": ["N/A", "NA", "unknown", "?", "-", "--", "null", "None", "missing"], "replacement": None},
                reason="Placeholder strings should be normalized to missing values before imputation.",
            )
        if first_column_type == "numeric":
            return SuggestedPipelineStepOut(
                operation_type="numeric_imputation",
                columns=columns,
                params={"strategy": "median"},
                reason="Median imputation is a conservative numeric default that is robust to outliers.",
            )
        if first_column_type in {"categorical", "boolean"}:
            return SuggestedPipelineStepOut(
                operation_type="categorical_imputation",
                columns=columns,
                params={"strategy": "constant", "fill_value": "__MISSING__"},
                reason="A constant missing label preserves missingness as a model-visible category.",
            )
        if first_column_type == "text":
            return SuggestedPipelineStepOut(
                operation_type="text_basic_features",
                columns=columns,
                params={
                    "lowercase": False,
                    "strip_whitespace": True,
                    "create_length_feature": True,
                    "create_word_count_feature": True,
                    "drop_original": False,
                },
                reason="Text feature extraction normalizes missing text to an empty string and adds usable length features.",
            )
        return SuggestedPipelineStepOut(
            operation_type="add_missing_indicator",
            columns=columns,
            params={"suffix": "_was_missing"},
            reason="For this type, a missingness indicator is safer than changing the source value automatically.",
        )

    if issue.category == "outlier" and columns:
        return SuggestedPipelineStepOut(
            operation_type="outlier_clipping",
            columns=columns,
            params={"method": "iqr", "iqr_multiplier": 1.5},
            reason="IQR clipping limits extreme numeric values while fitting thresholds from the training data.",
        )

    if issue.category == "cardinality" and columns:
        if "ID-like" in issue.title:
            return SuggestedPipelineStepOut(
                operation_type="drop_columns",
                columns=columns,
                params={},
                reason="Nearly unique columns often act as identifiers rather than reusable predictors.",
            )
        return SuggestedPipelineStepOut(
            operation_type="rare_category_grouping",
            columns=columns,
            params={"min_frequency": 0.01, "rare_label": "__RARE__", "include_missing": False},
            reason="Grouping rare categories reduces sparse categorical noise before encoding.",
        )

    if issue.category in {"constant", "leakage"} and columns:
        return SuggestedPipelineStepOut(
            operation_type="drop_columns",
            columns=columns,
            params={},
            reason="The flagged column is unlikely to add stable predictive value without further justification.",
        )

    return None


def build_suggested_pipeline_steps(issues: list[Issue], profiles: list[ColumnProfile]) -> list[SuggestedPipelineStepOut]:
    suggestions = [suggestion for issue in issues if (suggestion := build_suggested_step(issue, profiles)) is not None]
    drop_columns = {
        column
        for suggestion in suggestions
        if suggestion.operation_type == "drop_columns"
        for column in suggestion.columns
    }

    merged: OrderedDict[tuple[str, str], SuggestedPipelineStepOut] = OrderedDict()
    for suggestion in sorted(suggestions, key=_suggestion_sort_key):
        columns = [] if suggestion.operation_type == "remove_duplicate_rows" else [column for column in suggestion.columns if column not in drop_columns or suggestion.operation_type == "drop_columns"]
        if suggestion.operation_type != "remove_duplicate_rows" and not columns:
            continue
        key = (suggestion.operation_type, json.dumps(suggestion.params, sort_keys=True))
        if key not in merged:
            merged[key] = SuggestedPipelineStepOut(
                operation_type=suggestion.operation_type,
                columns=[],
                params=suggestion.params,
                reason=suggestion.reason,
            )
        existing = merged[key]
        for column in columns:
            if column not in existing.columns:
                existing.columns.append(column)

    return list(merged.values())


def _suggestion_sort_key(suggestion: SuggestedPipelineStepOut) -> int:
    order = {
        "remove_duplicate_rows": 0,
        "drop_columns": 10,
        "replace_placeholder_values": 20,
        "add_missing_indicator": 30,
        "numeric_imputation": 40,
        "categorical_imputation": 45,
        "text_basic_features": 50,
        "outlier_clipping": 60,
        "rare_category_grouping": 70,
    }
    return order.get(suggestion.operation_type, 100)
