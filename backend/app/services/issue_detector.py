from dataclasses import dataclass, field

import pandas as pd

from app.services.profiler import ColumnProfileData


@dataclass(frozen=True)
class IssueData:
    severity: str
    category: str
    title: str
    explanation: str
    affected_columns: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)


PLACEHOLDERS = {"N/A", "NA", "unknown", "Unknown", "UNK", "?", "-", "--", "null", "None", "missing"}


def _missingness_issues(profiles: list[ColumnProfileData]) -> list[IssueData]:
    issues: list[IssueData] = []
    for profile in profiles:
        if profile.missing_rate >= 0.50:
            severity = "critical"
        elif profile.missing_rate >= 0.10:
            severity = "warning"
        elif profile.missing_rate > 0:
            severity = "info"
        else:
            continue

        issues.append(
            IssueData(
                severity=severity,
                category="missingness",
                title=f"Missing values in {profile.column_name}",
                explanation=f"{profile.missing_rate:.1%} of values are missing.",
                affected_columns=[profile.column_name],
                suggested_actions=["impute missing values", "add missingness indicator", "drop column if missingness is too high"],
            )
        )
    return issues


def _profile_issues(profiles: list[ColumnProfileData]) -> list[IssueData]:
    issues: list[IssueData] = []
    for profile in profiles:
        dominant_rate = float(profile.summary.get("dominant_value_rate", 0.0) or 0.0)
        outlier_rate = float(profile.summary.get("outlier_rate_iqr", 0.0) or 0.0)

        if profile.unique_count <= 1:
            issues.append(
                IssueData(
                    severity="critical",
                    category="constant",
                    title=f"Constant column {profile.column_name}",
                    explanation="The column has one or zero unique non-missing values.",
                    affected_columns=[profile.column_name],
                    suggested_actions=["drop column"],
                )
            )
        elif dominant_rate >= 0.95:
            issues.append(
                IssueData(
                    severity="warning",
                    category="constant",
                    title=f"Near-constant column {profile.column_name}",
                    explanation=f"The dominant value covers {dominant_rate:.1%} of non-missing rows.",
                    affected_columns=[profile.column_name],
                    suggested_actions=["drop column", "keep only with domain justification"],
                )
            )

        if profile.inferred_type == "categorical" and profile.unique_count > 50 and profile.cardinality_ratio > 0.20:
            issues.append(
                IssueData(
                    severity="warning",
                    category="cardinality",
                    title=f"High-cardinality categorical column {profile.column_name}",
                    explanation="The column has many unique categories relative to row count.",
                    affected_columns=[profile.column_name],
                    suggested_actions=["group rare categories", "frequency encode", "drop ID-like column"],
                )
            )
        if profile.cardinality_ratio > 0.90 and profile.unique_count > 10:
            issues.append(
                IssueData(
                    severity="warning",
                    category="cardinality",
                    title=f"Possible ID-like column {profile.column_name}",
                    explanation="The column is nearly unique per row.",
                    affected_columns=[profile.column_name],
                    suggested_actions=["drop ID-like column", "keep only with domain justification"],
                )
            )

        if outlier_rate >= 0.05:
            issues.append(
                IssueData(
                    severity="warning",
                    category="outlier",
                    title=f"Outliers detected in {profile.column_name}",
                    explanation=f"IQR rule flags {outlier_rate:.1%} of numeric values as outliers.",
                    affected_columns=[profile.column_name],
                    suggested_actions=["percentile clipping", "IQR clipping", "log1p transform", "leave unchanged if meaningful"],
                )
            )
        elif outlier_rate > 0:
            issues.append(
                IssueData(
                    severity="info",
                    category="outlier",
                    title=f"Some outliers in {profile.column_name}",
                    explanation=f"IQR rule flags {outlier_rate:.1%} of numeric values as outliers.",
                    affected_columns=[profile.column_name],
                    suggested_actions=["inspect outliers", "clip if appropriate"],
                )
            )
    return issues


def _dataframe_issues(df: pd.DataFrame) -> list[IssueData]:
    issues: list[IssueData] = []
    duplicate_count = int(df.duplicated().sum())
    duplicate_rate = duplicate_count / max(len(df), 1)
    if duplicate_count:
        issues.append(
            IssueData(
                severity="critical" if duplicate_rate >= 0.10 else "warning",
                category="duplicate",
                title="Duplicate rows detected",
                explanation=f"{duplicate_count} duplicate rows were found.",
                suggested_actions=["remove duplicate rows", "inspect whether duplicates are legitimate repeated observations"],
            )
        )

    for column in df.select_dtypes(include=["object", "string"]).columns:
        values = df[column].dropna().astype(str).str.strip()
        placeholder_count = int(values.isin(PLACEHOLDERS).sum())
        if placeholder_count:
            issues.append(
                IssueData(
                    severity="warning",
                    category="missingness",
                    title=f"Placeholder values in {column}",
                    explanation=f"{placeholder_count} placeholder strings may represent missing values.",
                    affected_columns=[str(column)],
                    suggested_actions=["replace placeholder values with missing", "impute missing values"],
                )
            )
    return issues


def _target_issues(df: pd.DataFrame, target_column: str | None, problem_type: str) -> list[IssueData]:
    if not target_column or target_column not in df.columns:
        return []

    issues: list[IssueData] = []
    suspicious_terms = ["target", "label", "outcome", "result", "approved", "final"]
    for column in df.columns:
        if column == target_column:
            continue
        lower = str(column).lower()
        if any(term in lower for term in suspicious_terms):
            issues.append(
                IssueData(
                    severity="warning",
                    category="leakage",
                    title=f"Possible leakage feature {column}",
                    explanation="The column name looks related to the target or final outcome.",
                    affected_columns=[str(column)],
                    suggested_actions=["inspect feature timing", "drop leakage-prone feature"],
                )
            )

    if problem_type == "classification":
        target = df[target_column].dropna()
        if not target.empty:
            counts = target.value_counts(normalize=True)
            majority_rate = float(counts.iloc[0])
            if majority_rate >= 0.90:
                issues.append(
                    IssueData(
                        severity="warning",
                        category="target",
                        title="Imbalanced target",
                        explanation=f"The majority class covers {majority_rate:.1%} of labeled rows.",
                        affected_columns=[target_column],
                        suggested_actions=["review class distribution", "use stratified split", "consider class weighting during modeling"],
                    )
                )
    return issues


def detect_issues(
    df: pd.DataFrame,
    column_profiles: list[ColumnProfileData],
    target_column: str | None,
    problem_type: str,
) -> list[IssueData]:
    issues: list[IssueData] = []
    issues.extend(_missingness_issues(column_profiles))
    issues.extend(_profile_issues(column_profiles))
    issues.extend(_dataframe_issues(df))
    issues.extend(_target_issues(df, target_column, problem_type))
    return issues
