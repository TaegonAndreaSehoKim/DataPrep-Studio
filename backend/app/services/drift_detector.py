from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.services.issue_detector import IssueData
from app.services.profiler import ColumnProfileData


@dataclass(frozen=True)
class DriftResult:
    drift_score: float
    summary: dict[str, object]
    issues: list[IssueData] = field(default_factory=list)


def _numeric_shift(train: pd.Series, test: pd.Series) -> dict[str, object]:
    train_numeric = pd.to_numeric(train, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    test_numeric = pd.to_numeric(test, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    counts = {"train_count": int(len(train_numeric)), "test_count": int(len(test_numeric))}
    if min(len(train_numeric), len(test_numeric)) < 2:
        return {"status": "insufficient_data", "drift_flag": False, **counts}

    train_mean = float(train_numeric.mean())
    test_mean = float(test_numeric.mean())
    train_std = float(train_numeric.std(ddof=1))
    test_std = float(test_numeric.std(ddof=1))
    if not all(np.isfinite(value) for value in [train_mean, test_mean, train_std, test_std]):
        return {"status": "insufficient_data", "drift_flag": False, "reason": "Numeric range is too large for stable drift statistics", **counts}
    pooled_scale = train_std if train_std > 0 else max(abs(train_mean), 1.0)
    standardized_mean_diff = abs(test_mean - train_mean) / pooled_scale
    std_ratio = test_std / train_std if train_std > 0 else (1.0 if test_std == 0 else None)
    variance_flag = test_std > 0 if train_std == 0 else test_std >= 2 * train_std or test_std <= 0.5 * train_std
    train_sorted = np.sort(train_numeric.to_numpy(dtype=float))
    test_sorted = np.sort(test_numeric.to_numpy(dtype=float))
    probes = np.unique(np.concatenate([train_sorted, test_sorted]))
    train_cdf = np.searchsorted(train_sorted, probes, side="right") / len(train_sorted)
    test_cdf = np.searchsorted(test_sorted, probes, side="right") / len(test_sorted)
    distribution_distance = float(np.max(np.abs(train_cdf - test_cdf)))
    # A descriptive distance threshold, not a statistical significance test.
    distribution_flag = min(len(train_numeric), len(test_numeric)) >= 10 and distribution_distance >= 0.25
    mean_flag = standardized_mean_diff >= 1.0

    return {
        "status": "ok", **counts,
        "train_mean": train_mean,
        "test_mean": test_mean,
        "train_std": train_std,
        "test_std": test_std,
        "standardized_mean_diff": float(standardized_mean_diff) if np.isfinite(standardized_mean_diff) else None,
        "std_ratio": float(std_ratio) if std_ratio is not None and np.isfinite(std_ratio) else None,
        "distribution_distance": distribution_distance,
        "mean_shift_flag": bool(mean_flag),
        "variance_shift_flag": bool(variance_flag),
        "distribution_shift_flag": bool(distribution_flag),
        "drift_flag": bool(mean_flag or variance_flag or distribution_flag),
    }


def _categorical_shift(train: pd.Series, test: pd.Series) -> dict[str, object]:
    train_present = train.dropna().astype(str)
    test_present = test.dropna().astype(str)
    if train_present.empty or test_present.empty:
        return {"status": "insufficient_data", "drift_flag": False, "train_count": len(train_present), "test_count": len(test_present)}
    train_dist = train_present.value_counts(normalize=True).to_dict()
    test_dist = test_present.value_counts(normalize=True).to_dict()
    train_values = set(train_dist)
    test_values = set(test_dist)
    unseen = sorted(test_values - train_values)
    unseen_count = int(test_present.isin(unseen).sum()) if unseen else 0
    unseen_rate = unseen_count / len(test_present)
    total_variation = 0.5 * sum(abs(train_dist.get(label, 0.0) - test_dist.get(label, 0.0)) for label in train_values | test_values)
    return {
        "status": "ok", "train_count": len(train_present), "test_count": len(test_present),
        "train_unique": len(train_values),
        "test_unique": len(test_values),
        "unseen_categories": unseen[:25],
        "unseen_category_count": len(unseen),
        "unseen_row_rate": float(unseen_rate),
        "total_variation_distance": float(total_variation),
        "proportion_shift_flag": bool(total_variation >= 0.20),
        "drift_flag": bool(len(unseen) > 0 or total_variation >= 0.20),
    }


def _target_distribution_shift(train_df: pd.DataFrame, test_df: pd.DataFrame, target_column: str | None, problem_type: str) -> dict[str, object] | None:
    if not target_column or target_column not in train_df.columns or target_column not in test_df.columns:
        return None
    if problem_type == "regression":
        return {"kind": "numeric", **_numeric_shift(train_df[target_column], test_df[target_column])}
    if train_df[target_column].dropna().empty or test_df[target_column].dropna().empty:
        return {"kind": "categorical", "status": "insufficient_data", "drift_flag": False}
    train_dist = train_df[target_column].dropna().astype(str).value_counts(normalize=True).to_dict()
    test_dist = test_df[target_column].dropna().astype(str).value_counts(normalize=True).to_dict()
    labels = sorted(set(train_dist) | set(test_dist))
    max_delta = max((abs(float(train_dist.get(label, 0.0)) - float(test_dist.get(label, 0.0))) for label in labels), default=0.0)
    return {
        "kind": "categorical",
        "train_distribution": {str(key): float(value) for key, value in train_dist.items()},
        "test_distribution": {str(key): float(value) for key, value in test_dist.items()},
        "max_class_rate_delta": float(max_delta),
        "drift_flag": bool(max_delta >= 0.20),
    }


def _row_overlap(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict[str, object]:
    common_columns = [column for column in train_df.columns if column in test_df.columns]
    if not common_columns:
        return {"overlap_count": 0, "overlap_rate": 0.0}
    train_rows = set(map(tuple, train_df[common_columns].astype(str).to_numpy()))
    test_rows = list(map(tuple, test_df[common_columns].astype(str).to_numpy()))
    overlap_count = sum(1 for row in test_rows if row in train_rows)
    return {
        "overlap_count": int(overlap_count),
        "overlap_rate": float(overlap_count / max(len(test_df), 1)),
        "columns_compared": [str(column) for column in common_columns],
    }


def detect_train_test_drift(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    train_profiles: list[ColumnProfileData],
    target_column: str | None,
    problem_type: str = "unknown",
) -> DriftResult:
    issues: list[IssueData] = []
    summary: dict[str, object] = {
        "row_counts": {"train": int(len(train_df)), "test": int(len(test_df))},
        "column_counts": {"train": int(len(train_df.columns)), "test": int(len(test_df.columns))},
        "missing_columns_in_test": sorted([str(column) for column in train_df.columns if column not in test_df.columns and column != target_column]),
        "extra_columns_in_test": sorted([str(column) for column in test_df.columns if column not in train_df.columns]),
        "columns": {},
        "test_target_present": target_column in test_df.columns if target_column else None,
    }

    if summary["missing_columns_in_test"] or summary["extra_columns_in_test"]:
        issues.append(
            IssueData(
                severity="warning",
                category="split",
                title="Train/test column mismatch",
                explanation="Train and test feature columns do not match. An omitted test target is allowed.",
                affected_columns=list(summary["missing_columns_in_test"]) + list(summary["extra_columns_in_test"]),
                suggested_actions=["align train/test columns", "verify split/export process"],
            )
        )

    drift_points = 0.0
    profile_by_name = {profile.column_name: profile for profile in train_profiles}
    common_columns = [column for column in train_df.columns if column in test_df.columns]
    column_summaries: dict[str, object] = {}

    for column in common_columns:
        if column == target_column:
            continue
        profile = profile_by_name.get(str(column))
        if profile is None:
            continue

        if profile.inferred_type == "numeric":
            column_summary = _numeric_shift(train_df[column], test_df[column])
            if column_summary.get("drift_flag"):
                drift_points += 1.0
                issues.append(
                    IssueData(
                        severity="warning",
                        category="drift",
                        title=f"Numeric drift in {column}",
                        explanation="The test feature differs in mean, spread, or empirical distribution. Review the component metrics and sample counts.",
                        affected_columns=[str(column)],
                        suggested_actions=["inspect split quality", "fit preprocessing on train only", "monitor feature drift"],
                    )
                )
        elif profile.inferred_type in {"categorical", "boolean", "text"}:
            column_summary = _categorical_shift(train_df[column], test_df[column])
            if column_summary.get("drift_flag"):
                drift_points += 1.0
                issues.append(
                    IssueData(
                        severity="warning",
                        category="drift",
                        title=f"Unseen categories in {column}" if column_summary.get("unseen_category_count") else f"Category proportion drift in {column}",
                        explanation="The test set contains new categories or different category proportions. Review the unseen rate and total variation distance.",
                        affected_columns=[str(column)],
                        suggested_actions=["use unknown-safe encoding", "group rare categories", "inspect train/test split"] if column_summary.get("unseen_category_count") else ["inspect category proportions", "verify train/test split"],
                    )
                )
        else:
            continue
        column_summaries[str(column)] = column_summary

    summary["columns"] = column_summaries
    target_shift = _target_distribution_shift(train_df, test_df, target_column, problem_type)
    summary["target_distribution_status"] = "available" if target_shift is not None else "not_available" if target_column else "not_configured"
    if target_shift is not None:
        summary["target_distribution"] = target_shift
        if target_shift["drift_flag"]:
            drift_points += 1.0
            issues.append(
                IssueData(
                    severity="warning",
                    category="target",
                    title="Train/test target distribution shift",
                    explanation="The target distribution differs between train and test.",
                    affected_columns=[target_column] if target_column else [],
                    suggested_actions=["inspect target range and distribution", "verify test set construction"] if problem_type == "regression" else ["use stratified splitting", "verify test set construction"],
                )
            )

    overlap = _row_overlap(train_df, test_df)
    summary["row_overlap"] = overlap
    if float(overlap["overlap_rate"]) > 0:
        drift_points += 1.0
        issues.append(
            IssueData(
                severity="critical" if float(overlap["overlap_rate"]) >= 0.10 else "warning",
                category="split",
                title="Duplicate row overlap across train/test",
                explanation="Some test rows also appear in train.",
                suggested_actions=["remove split leakage", "recreate train/test split"],
            )
        )

    drift_score = min(100.0, 100.0 * drift_points / max(len(common_columns), 1))
    return DriftResult(drift_score=float(drift_score), summary=summary, issues=issues)
