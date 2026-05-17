import json

from app.models import ColumnProfile, Issue, TrainTestComparison
from app.schemas import AnalysisChartsOut, ChartData


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _count_values(values: list[str]) -> list[dict[str, str | int | float | None]]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return [{"label": key, "value": value} for key, value in sorted(counts.items())]


def build_analysis_charts(
    analysis_id: int,
    profiles: list[ColumnProfile],
    issues: list[Issue],
    comparison: TrainTestComparison | None = None,
) -> AnalysisChartsOut:
    missingness = sorted(
        [
            {
                "label": profile.column_name,
                "value": round(float(profile.missing_rate), 4),
                "dataset_role": profile.dataset_role,
            }
            for profile in profiles
        ],
        key=lambda item: float(item["value"]),
        reverse=True,
    )
    cardinality = sorted(
        [
            {
                "label": profile.column_name,
                "value": round(float(profile.cardinality_ratio), 4),
                "dataset_role": profile.dataset_role,
            }
            for profile in profiles
        ],
        key=lambda item: float(item["value"]),
        reverse=True,
    )

    charts: dict[str, ChartData] = {
        "issue_severity": ChartData(
            chart_type="bar",
            title="Issues by Severity",
            data=_count_values([issue.severity for issue in issues]),
        ),
        "issue_category": ChartData(
            chart_type="bar",
            title="Issues by Category",
            data=_count_values([issue.category for issue in issues]),
        ),
        "missingness": ChartData(
            chart_type="horizontal_bar",
            title="Missing Rate by Column",
            description="Column-level missing values as a fraction of rows.",
            data=missingness[:30],
        ),
        "cardinality": ChartData(
            chart_type="horizontal_bar",
            title="Cardinality Ratio by Column",
            description="Unique non-missing values divided by row count.",
            data=cardinality[:30],
        ),
        "inferred_types": ChartData(
            chart_type="bar",
            title="Inferred Column Types",
            data=_count_values([profile.inferred_type for profile in profiles]),
        ),
    }

    if comparison is not None:
        summary = _json_loads(comparison.summary_json, {})
        drift_rows: list[dict[str, str | int | float | None]] = [
            {"label": "overall_drift_score", "value": round(float(comparison.drift_score), 4)}
        ]
        columns = summary.get("columns", {})
        if isinstance(columns, dict):
            for column_name, column_summary in columns.items():
                if isinstance(column_summary, dict):
                    if "standardized_mean_diff" in column_summary:
                        drift_rows.append({"label": str(column_name), "value": round(float(column_summary["standardized_mean_diff"]), 4)})
                    elif "unseen_row_rate" in column_summary:
                        drift_rows.append({"label": str(column_name), "value": round(float(column_summary["unseen_row_rate"]), 4)})
        charts["train_test_drift"] = ChartData(
            chart_type="bar",
            title="Train/Test Drift Summary",
            description="Numeric mean shift or unseen category rate by feature, plus the overall drift score.",
            data=drift_rows,
        )

    return AnalysisChartsOut(analysis_id=analysis_id, charts=charts)


def build_column_charts(analysis_id: int, profile: ColumnProfile) -> AnalysisChartsOut:
    summary = _json_loads(profile.summary_json, {})
    if isinstance(summary.get("count"), int):
        present_count = int(summary["count"])
    elif isinstance(summary.get("class_counts"), dict):
        present_count = sum(int(count) for count in summary["class_counts"].values())
    else:
        present_count = _estimated_present_count(profile)
    charts: dict[str, ChartData] = {
        "missingness": ChartData(
            chart_type="bar",
            title=f"{profile.column_name} Missingness",
            data=[
                {"label": "missing", "value": profile.missing_count},
                {"label": "present", "value": present_count},
            ],
        )
    }

    if profile.inferred_type == "numeric":
        numeric_points = []
        for label in ["min", "q1", "median", "q3", "max", "mean"]:
            value = summary.get(label)
            if isinstance(value, int | float):
                numeric_points.append({"label": label, "value": round(float(value), 4)})
        if numeric_points:
            charts["numeric_summary"] = ChartData(
                chart_type="bar",
                title=f"{profile.column_name} Numeric Summary",
                description="Summary statistics from the profiled column.",
                data=numeric_points,
            )

    top_values = summary.get("top_values")
    if isinstance(top_values, list):
        rows: list[dict[str, str | int | float | None]] = []
        for item in top_values:
            if isinstance(item, dict):
                rows.append({"label": str(item.get("value")), "value": int(item.get("count", 0) or 0)})
        if rows:
            charts["top_values"] = ChartData(
                chart_type="horizontal_bar",
                title=f"{profile.column_name} Top Values",
                data=rows,
            )

    class_counts = summary.get("class_counts")
    if isinstance(class_counts, dict):
        charts["class_balance"] = ChartData(
            chart_type="bar",
            title=f"{profile.column_name} Class Balance",
            data=[{"label": str(label), "value": int(count)} for label, count in class_counts.items()],
        )

    return AnalysisChartsOut(analysis_id=analysis_id, charts=charts)


def _estimated_present_count(profile: ColumnProfile) -> int:
    if profile.missing_rate <= 0:
        return profile.unique_count
    estimated_rows = int(round(profile.missing_count / profile.missing_rate))
    return max(0, estimated_rows - profile.missing_count)


def build_preview_charts(analysis_id: int, before_summary: dict[str, object], after_summary: dict[str, object]) -> AnalysisChartsOut:
    charts = {
        "shape_change": ChartData(
            chart_type="bar",
            title="Shape Change",
            data=[
                {"label": "rows_before", "value": int(before_summary.get("row_count", 0) or 0)},
                {"label": "rows_after", "value": int(after_summary.get("row_count", 0) or 0)},
                {"label": "columns_before", "value": int(before_summary.get("column_count", 0) or 0)},
                {"label": "columns_after", "value": int(after_summary.get("column_count", 0) or 0)},
            ],
        ),
        "missing_rate_change": ChartData(
            chart_type="bar",
            title="Missing Rate Change",
            data=[
                {"label": "before", "value": round(float(before_summary.get("missing_rate", 0) or 0), 4)},
                {"label": "after", "value": round(float(after_summary.get("missing_rate", 0) or 0), 4)},
            ],
        ),
    }
    return AnalysisChartsOut(analysis_id=analysis_id, charts=charts)
