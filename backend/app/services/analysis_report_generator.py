import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.models import AnalysisRun, ColumnProfile, DatasetFile, Issue, Project, TrainTestComparison
from app.schemas import AnalysisChartsOut, AnalysisPreprocessingRecommendationsOut


def _json_loads(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _json_inline(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _fmt_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_score(value: float) -> str:
    return f"{value:.1f}"


def _dataset_line(label: str, dataset: DatasetFile | None) -> str:
    if dataset is None:
        return f"- {label}: not available"
    return (
        f"- {label}: `{dataset.filename}` "
        f"({dataset.row_count} rows, {dataset.column_count} columns, {dataset.file_size_bytes} bytes)"
    )


def _profile_summary_value(summary: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ["count", "missing_count", "mean", "median", "min", "max", "unique_count"]:
        if key in summary:
            pieces.append(f"{key}={summary[key]}")
    class_counts = summary.get("class_counts")
    if isinstance(class_counts, dict):
        pieces.append(f"class_counts={class_counts}")
    top_values = summary.get("top_values")
    if isinstance(top_values, list) and top_values:
        pieces.append(f"top_values={top_values[:3]}")
    return "; ".join(pieces) if pieces else "summary not available"


def _top_profiles_by_missing(profiles: list[ColumnProfile], limit: int = 10) -> list[ColumnProfile]:
    return sorted(profiles, key=lambda item: (item.missing_rate, item.missing_count), reverse=True)[:limit]


def _top_profiles_by_cardinality(profiles: list[ColumnProfile], limit: int = 10) -> list[ColumnProfile]:
    return sorted(profiles, key=lambda item: item.cardinality_ratio, reverse=True)[:limit]


def generate_analysis_report(
    *,
    project: Project,
    analysis: AnalysisRun,
    datasets: dict[str, DatasetFile | None],
    profiles: list[ColumnProfile],
    issues: list[Issue],
    recommendations: AnalysisPreprocessingRecommendationsOut,
    charts: AnalysisChartsOut,
    comparison: TrainTestComparison | None,
) -> str:
    severity_counts = Counter(issue.severity for issue in issues)
    category_counts = Counter(issue.category for issue in issues)
    type_counts = Counter(profile.inferred_type for profile in profiles)
    role_counts = Counter(profile.dataset_role for profile in profiles)
    warnings = [
        (profile.column_name, warning)
        for profile in profiles
        for warning in _json_loads(profile.warnings_json, [])
    ]

    lines = [
        "# DataPrep Studio Analysis Report",
        "",
        "## Executive Summary",
        f"- Project: {project.name} (ID {project.id})",
        f"- Analysis ID: {analysis.id}",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Status: {analysis.status}",
        f"- Readiness score: {_fmt_score(analysis.readiness_score)}",
        f"- Problem type: {analysis.problem_type}",
        f"- Target column: {analysis.target_column or 'not specified'}",
        f"- Profiled columns: {len(profiles)}",
        f"- Detected issues: {len(issues)}",
        f"- Generated preprocessing recommendations: {len(recommendations.recommendations)}",
        "",
        "## Dataset Context",
        _dataset_line("Single dataset", datasets.get("single")),
        _dataset_line("Train dataset", datasets.get("train")),
        _dataset_line("Test dataset", datasets.get("test")),
        "",
        "## Readiness Score Breakdown",
        "```json",
        _json_block(_json_loads(analysis.score_breakdown_json, {})),
        "```",
        "",
        "## Column Type Distribution",
    ]

    if type_counts:
        lines.extend([f"- {column_type}: {count}" for column_type, count in sorted(type_counts.items())])
    else:
        lines.append("- No column profiles were generated.")

    lines.extend(["", "## Dataset Roles"])
    lines.extend([f"- {role}: {count} profiled columns" for role, count in sorted(role_counts.items())] or ["- No dataset roles available."])

    lines.extend(["", "## Issue Summary"])
    if issues:
        lines.append("### By Severity")
        lines.extend([f"- {severity}: {count}" for severity, count in sorted(severity_counts.items())])
        lines.append("")
        lines.append("### By Category")
        lines.extend([f"- {category}: {count}" for category, count in sorted(category_counts.items())])
    else:
        lines.append("- No issues were detected.")

    lines.extend(["", "## Notable Issues"])
    for issue in issues[:25]:
        affected = _json_loads(issue.affected_columns_json, [])
        actions = _json_loads(issue.suggested_actions_json, [])
        lines.extend(
            [
                f"### {issue.title}",
                f"- Severity: {issue.severity}",
                f"- Category: {issue.category}",
                f"- Affected columns: {', '.join(affected) if affected else 'none'}",
                f"- Explanation: {issue.explanation}",
                f"- Suggested actions: {' / '.join(actions) if actions else 'none'}",
                "",
            ]
        )
    if not issues:
        lines.append("- None")

    lines.extend(["", "## Preprocessing Recommendations"])
    if recommendations.recommendations:
        for item in recommendations.recommendations:
            step = item.suggested_step
            lines.extend(
                [
                    f"### {item.title}",
                    f"- Priority: {item.priority}",
                    f"- Category: {item.category}",
                    f"- Columns: {', '.join(item.affected_columns) if item.affected_columns else 'none'}",
                    f"- Rationale: {item.rationale}",
                    f"- Suggested operation: {step.operation_type if step else 'manual review'}",
                    f"- Suggested parameters: `{_json_inline(step.params) if step else '{}'}`",
                ]
            )
    else:
        lines.extend([f"- {note}" for note in recommendations.notes] or ["- No recommendations were generated."])

    lines.extend(["", "## Missingness Hotspots"])
    for profile in _top_profiles_by_missing(profiles):
        lines.append(
            f"- `{profile.column_name}` ({profile.dataset_role}, {profile.inferred_type}): "
            f"{profile.missing_count} missing / {_fmt_percent(profile.missing_rate)}"
        )
    if not profiles:
        lines.append("- No profiles available.")

    lines.extend(["", "## High Cardinality Columns"])
    for profile in _top_profiles_by_cardinality(profiles):
        lines.append(
            f"- `{profile.column_name}` ({profile.dataset_role}, {profile.inferred_type}): "
            f"{profile.unique_count} unique / {_fmt_percent(profile.cardinality_ratio)}"
        )
    if not profiles:
        lines.append("- No profiles available.")

    lines.extend(["", "## Column Profile Details"])
    lines.append("| Role | Column | Type | Missing | Unique | Cardinality | Summary |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for profile in profiles:
        summary = _json_loads(profile.summary_json, {})
        lines.append(
            f"| {profile.dataset_role} | `{profile.column_name}` | {profile.inferred_type} | "
            f"{profile.missing_count} ({_fmt_percent(profile.missing_rate)}) | "
            f"{profile.unique_count} | {_fmt_percent(profile.cardinality_ratio)} | "
            f"{_profile_summary_value(summary)} |"
        )

    lines.extend(["", "## Column Warnings"])
    if warnings:
        lines.extend([f"- `{column}`: {warning}" for column, warning in warnings[:50]])
    else:
        lines.append("- No column-level warnings were recorded.")

    lines.extend(["", "## Chart Data Summary"])
    if charts.charts:
        for key, chart in charts.charts.items():
            lines.extend(
                [
                    f"### {chart.title}",
                    f"- Key: `{key}`",
                    f"- Type: {chart.chart_type}",
                    f"- Description: {chart.description or 'not specified'}",
                    "- Data:",
                    "```json",
                    _json_block(chart.data[:30]),
                    "```",
                    "",
                ]
            )
    else:
        lines.append("- No chart data available.")

    lines.extend(["", "## Train/Test Drift"])
    if comparison is not None:
        lines.extend(
            [
                f"- Drift score: {_fmt_score(comparison.drift_score)}",
                "```json",
                _json_block(_json_loads(comparison.summary_json, {})),
                "```",
            ]
        )
    else:
        lines.append("- Train/test comparison was not generated for this analysis.")

    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "- Readiness score is a heuristic summary of detected data-quality and ML-readiness issues.",
            "- Recommendations are advisory and should be reviewed before applying preprocessing.",
            "- In train/test mode, learned preprocessing parameters should be fit on train only and applied to test.",
            "- This report describes analysis findings; it does not train or evaluate a model.",
            "",
        ]
    )
    return "\n".join(lines)
