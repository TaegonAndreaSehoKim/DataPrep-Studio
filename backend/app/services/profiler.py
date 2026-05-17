from dataclasses import dataclass, field
from typing import Literal
import warnings

import numpy as np
import pandas as pd

InferredType = Literal["numeric", "categorical", "boolean", "datetime", "text", "unknown"]


@dataclass(frozen=True)
class ColumnProfileData:
    dataset_role: str
    column_name: str
    inferred_type: InferredType
    missing_count: int
    missing_rate: float
    unique_count: int
    cardinality_ratio: float
    summary: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _sample_values(series: pd.Series, limit: int = 5) -> list[object]:
    values = series.dropna().head(limit).tolist()
    return [value.item() if hasattr(value, "item") else value for value in values]


def _numeric_parse_rate(series: pd.Series) -> float:
    non_missing = series.dropna()
    if non_missing.empty:
        return 0.0
    parsed = pd.to_numeric(non_missing, errors="coerce")
    return float(parsed.notna().mean())


def _datetime_parse_rate(series: pd.Series) -> float:
    non_missing = series.dropna()
    if non_missing.empty:
        return 0.0
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Could not infer format.*", category=UserWarning)
        parsed = pd.to_datetime(non_missing, errors="coerce")
    return float(parsed.notna().mean())


def infer_column_type(series: pd.Series, target_column: str | None = None) -> InferredType:
    non_missing = series.dropna()
    unique_count = int(non_missing.nunique(dropna=True))
    row_count = max(len(series), 1)

    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        if series.name != target_column and unique_count <= min(10, max(2, int(row_count * 0.05))):
            return "categorical"
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    normalized = non_missing.astype(str).str.strip().str.lower()
    boolean_values = {"true", "false", "yes", "no", "y", "n", "0", "1"}
    if unique_count and unique_count <= 4 and set(normalized.unique()).issubset(boolean_values):
        return "boolean"

    numeric_rate = _numeric_parse_rate(series)
    if numeric_rate >= 0.90:
        return "numeric"

    datetime_rate = _datetime_parse_rate(series)
    if datetime_rate >= 0.85:
        return "datetime"

    text_values = non_missing.astype(str)
    average_length = float(text_values.str.len().mean()) if not text_values.empty else 0.0
    cardinality_ratio = unique_count / row_count
    if average_length >= 40 or (average_length >= 20 and cardinality_ratio > 0.5):
        return "text"

    if len(series) == 0:
        return "unknown"
    return "categorical"


def _numeric_summary(series: pd.Series) -> dict[str, object]:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return {"count": 0}

    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = valid[(valid < lower) | (valid > upper)]

    return {
        "count": int(valid.count()),
        "mean": float(valid.mean()),
        "std": float(valid.std(ddof=1)) if len(valid) > 1 else 0.0,
        "min": float(valid.min()),
        "max": float(valid.max()),
        "median": float(valid.median()),
        "q1": q1,
        "q3": q3,
        "iqr": float(iqr),
        "zero_count": int((valid == 0).sum()),
        "negative_count": int((valid < 0).sum()),
        "skewness": float(valid.skew()) if len(valid) > 2 and not np.isnan(valid.skew()) else 0.0,
        "outlier_count_iqr": int(len(outliers)),
        "outlier_rate_iqr": float(len(outliers) / len(valid)),
    }


def _categorical_summary(series: pd.Series) -> dict[str, object]:
    non_missing = series.dropna().astype(str)
    value_counts = non_missing.value_counts()
    total = max(len(non_missing), 1)
    top_values = [{"value": str(index), "count": int(count)} for index, count in value_counts.head(10).items()]
    rare_count = int((value_counts <= max(1, int(total * 0.01))).sum())
    dominant_value = str(value_counts.index[0]) if not value_counts.empty else None
    dominant_count = int(value_counts.iloc[0]) if not value_counts.empty else 0

    return {
        "count": int(len(non_missing)),
        "top_values": top_values,
        "rare_value_count": rare_count,
        "rare_value_rate": float(rare_count / max(len(value_counts), 1)) if len(value_counts) else 0.0,
        "dominant_value": dominant_value,
        "dominant_value_rate": float(dominant_count / total),
        "possible_id_column": bool(series.nunique(dropna=True) / max(len(series), 1) > 0.9),
    }


def _datetime_summary(series: pd.Series) -> dict[str, object]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Could not infer format.*", category=UserWarning)
        parsed = pd.to_datetime(series, errors="coerce")
    valid = parsed.dropna()
    non_missing_count = int(series.notna().sum())
    return {
        "count": non_missing_count,
        "parse_success_rate": float(parsed.notna().sum() / max(non_missing_count, 1)),
        "min_date": valid.min().isoformat() if not valid.empty else None,
        "max_date": valid.max().isoformat() if not valid.empty else None,
        "invalid_date_count": int(non_missing_count - parsed.notna().sum()),
    }


def _text_summary(series: pd.Series) -> dict[str, object]:
    text = series.dropna().astype(str)
    lengths = text.str.len()
    words = text.str.split().str.len()
    return {
        "count": int(len(text)),
        "average_length": float(lengths.mean()) if not text.empty else 0.0,
        "min_length": int(lengths.min()) if not text.empty else 0,
        "max_length": int(lengths.max()) if not text.empty else 0,
        "empty_string_count": int((text.str.strip() == "").sum()),
        "average_word_count": float(words.mean()) if not text.empty else 0.0,
    }


def _classification_target_summary(series: pd.Series) -> dict[str, object]:
    non_missing = series.dropna().astype(str)
    value_counts = non_missing.value_counts()
    if value_counts.empty:
        return {
            "count": 0,
            "class_counts": {},
            "majority_class": None,
            "majority_class_rate": 0.0,
            "minority_class": None,
            "minority_class_rate": 0.0,
        }
    total = max(len(non_missing), 1)
    return {
        "count": int(len(non_missing)),
        "class_counts": {str(index): int(count) for index, count in value_counts.items()},
        "majority_class": str(value_counts.index[0]),
        "majority_class_rate": float(value_counts.iloc[0] / total),
        "minority_class": str(value_counts.index[-1]),
        "minority_class_rate": float(value_counts.iloc[-1] / total),
    }


def profile_dataframe(
    df: pd.DataFrame,
    dataset_role: str,
    target_column: str | None = None,
    problem_type: str = "unknown",
    column_type_overrides: dict[str, InferredType] | None = None,
) -> list[ColumnProfileData]:
    row_count = max(len(df), 1)
    profiles: list[ColumnProfileData] = []
    overrides = column_type_overrides or {}

    for column in df.columns:
        series = df[column]
        inferred_type = overrides.get(str(column)) or infer_column_type(series, target_column)
        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        cardinality_ratio = float(unique_count / row_count)
        warnings: list[str] = []
        summary: dict[str, object] = {"sample_values": _sample_values(series)}

        if missing_count:
            warnings.append("contains_missing_values")
        if unique_count <= 1:
            warnings.append("constant_or_empty")
        if str(column) in overrides:
            warnings.append("user_type_override")

        if column == target_column and problem_type == "classification":
            summary.update(_classification_target_summary(series))
        elif inferred_type == "numeric":
            summary.update(_numeric_summary(series))
        elif inferred_type in {"categorical", "boolean"}:
            summary.update(_categorical_summary(series))
        elif inferred_type == "datetime":
            summary.update(_datetime_summary(series))
        elif inferred_type == "text":
            summary.update(_text_summary(series))

        if column == target_column:
            summary["is_target"] = True

        profiles.append(
            ColumnProfileData(
                dataset_role=dataset_role,
                column_name=str(column),
                inferred_type=inferred_type,
                missing_count=missing_count,
                missing_rate=float(missing_count / row_count),
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                summary=summary,
                warnings=warnings,
            )
        )

    return profiles
