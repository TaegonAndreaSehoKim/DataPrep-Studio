from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class StepEffect:
    operation_type: str
    columns: list[str]
    summary: str
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class TransformationError(ValueError):
    pass


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise TransformationError(f"Columns do not exist: {', '.join(missing)}")


def _target_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    selected = columns or list(df.columns)
    _require_columns(df, selected)
    return selected


def _missing_counts(df: pd.DataFrame, columns: list[str]) -> dict[str, int]:
    return {column: int(df[column].isna().sum()) for column in columns if column in df.columns}


def fit_transform_step(df: pd.DataFrame, operation_type: str, columns: list[str], params: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any], StepEffect]:
    working = df.copy()
    columns = _target_columns(working, columns)
    before_shape = {"rows": int(len(working)), "columns": int(len(working.columns))}

    if operation_type == "drop_columns":
        working = working.drop(columns=columns)
        fitted = {"columns": columns}
        effect = StepEffect(operation_type, columns, f"Dropped {len(columns)} columns.", before_shape, {"columns": int(len(working.columns))})
        return working, fitted, effect

    if operation_type == "remove_duplicate_rows":
        subset = params.get("subset") or columns
        if not isinstance(subset, list):
            raise TransformationError("subset must be a list")
        _require_columns(working, [str(column) for column in subset])
        keep_param = params.get("keep", "first")
        keep = False if keep_param == "none" else keep_param
        before_rows = len(working)
        working = working.drop_duplicates(subset=[str(column) for column in subset], keep=keep)  # type: ignore[arg-type]
        removed = before_rows - len(working)
        return working, {"subset": subset, "keep": keep_param}, StepEffect(operation_type, columns, f"Removed {removed} duplicate rows.", before_shape, {"rows": int(len(working))})

    if operation_type == "replace_placeholder_values":
        placeholders = params.get("placeholders", ["N/A", "NA", "unknown", "?", "-"])
        replacement = params.get("replacement", None)
        if not isinstance(placeholders, list):
            raise TransformationError("placeholders must be a list")
        count = 0
        for column in columns:
            before = working[column].copy()
            working[column] = working[column].replace(placeholders, replacement)
            count += int((before != working[column]).sum())
        return working, {"placeholders": placeholders, "replacement": replacement}, StepEffect(operation_type, columns, f"Replaced {count} placeholder values.")

    if operation_type == "numeric_imputation":
        before_missing = _missing_counts(working, columns)
        strategy = params.get("strategy", "median")
        fill_values: dict[str, float] = {}
        for column in columns:
            numeric = pd.to_numeric(working[column], errors="coerce")
            if strategy == "mean":
                value = float(numeric.mean())
            elif strategy == "median":
                value = float(numeric.median())
            elif strategy == "constant":
                value = float(params.get("fill_value", 0))
            else:
                raise TransformationError("numeric_imputation strategy must be mean, median, or constant")
            fill_values[column] = value
            working[column] = numeric.fillna(value)
        after_missing = _missing_counts(working, columns)
        return working, {"strategy": strategy, "fill_values": fill_values}, StepEffect(operation_type, columns, f"Filled numeric missing values using {strategy}.", before_missing, after_missing)

    if operation_type == "categorical_imputation":
        before_missing = _missing_counts(working, columns)
        strategy = params.get("strategy", "most_frequent")
        fill_values: dict[str, str] = {}
        for column in columns:
            if strategy == "most_frequent":
                mode = working[column].dropna().mode()
                value = str(mode.iloc[0]) if not mode.empty else "__MISSING__"
            elif strategy == "constant":
                value = str(params.get("fill_value", "__MISSING__"))
            else:
                raise TransformationError("categorical_imputation strategy must be most_frequent or constant")
            fill_values[column] = value
            working[column] = working[column].fillna(value)
        after_missing = _missing_counts(working, columns)
        return working, {"strategy": strategy, "fill_values": fill_values}, StepEffect(operation_type, columns, f"Filled categorical missing values using {strategy}.", before_missing, after_missing)

    if operation_type == "add_missing_indicator":
        suffix = str(params.get("suffix", "_was_missing"))
        created = []
        for column in columns:
            new_column = f"{column}{suffix}"
            working[new_column] = working[column].isna().astype(int)
            created.append(new_column)
        return working, {"created_columns": created, "suffix": suffix}, StepEffect(operation_type, columns, f"Created {len(created)} missingness indicators.", before_shape, {"columns": int(len(working.columns))})

    if operation_type == "rare_category_grouping":
        min_frequency = float(params.get("min_frequency", 0.01))
        min_count = params.get("min_count")
        rare_label = str(params.get("rare_label", "__RARE__"))
        include_missing = bool(params.get("include_missing", False))
        frequent_values: dict[str, list[str]] = {}
        for column in columns:
            series = working[column].fillna("__MISSING__") if include_missing else working[column]
            counts = series.dropna().astype(str).value_counts()
            threshold = int(min_count) if min_count is not None else max(1, int(np.ceil(len(series) * min_frequency)))
            frequent = counts[counts >= threshold].index.astype(str).tolist()
            frequent_values[column] = frequent
            mask = ~working[column].astype(str).isin(frequent)
            if not include_missing:
                mask = mask & working[column].notna()
            working.loc[mask, column] = rare_label
        return working, {"frequent_values": frequent_values, "rare_label": rare_label}, StepEffect(operation_type, columns, "Grouped rare categories using train frequencies.")

    if operation_type == "one_hot_encoding":
        drop_first = bool(params.get("drop_first", False))
        max_categories = params.get("max_categories")
        categories: dict[str, list[str]] = {}
        for column in columns:
            cats = sorted(working[column].dropna().astype(str).unique().tolist())
            if max_categories is not None:
                cats = cats[: int(max_categories)]
            if drop_first and cats:
                cats = cats[1:]
            categories[column] = cats
        return _apply_one_hot(working, columns, categories), {"categories": categories, "drop_first": drop_first}, StepEffect(operation_type, columns, "One-hot encoded categorical columns.")

    if operation_type == "ordinal_encoding":
        provided = params.get("categories_order", {})
        unknown_value = int(params.get("unknown_value", -1))
        mappings: dict[str, dict[str, int]] = {}
        for column in columns:
            if isinstance(provided, dict) and column in provided and isinstance(provided[column], list):
                cats = [str(value) for value in provided[column]]
            else:
                cats = sorted(working[column].dropna().astype(str).unique().tolist())
            mapping = {value: index for index, value in enumerate(cats)}
            mappings[column] = mapping
            working[column] = working[column].astype(str).map(mapping).fillna(unknown_value).astype(int)
        return working, {"mappings": mappings, "unknown_value": unknown_value}, StepEffect(operation_type, columns, "Ordinal encoded categorical columns.")

    if operation_type == "frequency_encoding":
        normalize = bool(params.get("normalize", True))
        unknown_value = float(params.get("unknown_value", 0))
        maps: dict[str, dict[str, float]] = {}
        for column in columns:
            counts = working[column].dropna().astype(str).value_counts(normalize=normalize)
            mapping = {str(key): float(value) for key, value in counts.items()}
            maps[column] = mapping
            working[column] = working[column].astype(str).map(mapping).fillna(unknown_value)
        return working, {"frequency_maps": maps, "unknown_value": unknown_value}, StepEffect(operation_type, columns, "Frequency encoded categorical columns.")

    if operation_type == "numeric_scaling":
        method = params.get("method", "standard")
        stats: dict[str, dict[str, float]] = {}
        for column in columns:
            numeric = pd.to_numeric(working[column], errors="coerce")
            if method == "standard":
                mean = float(numeric.mean())
                std = float(numeric.std(ddof=0)) or 1.0
                working[column] = (numeric - mean) / std
                stats[column] = {"mean": mean, "std": std}
            elif method == "minmax":
                min_value = float(numeric.min())
                max_value = float(numeric.max())
                low, high = params.get("feature_range", [0, 1])
                denom = max_value - min_value or 1.0
                working[column] = ((numeric - min_value) / denom) * (float(high) - float(low)) + float(low)
                stats[column] = {"min": min_value, "max": max_value, "low": float(low), "high": float(high)}
            elif method == "robust":
                q_low, q_high = params.get("quantile_range", [25, 75])
                q1 = float(numeric.quantile(float(q_low) / 100.0))
                q3 = float(numeric.quantile(float(q_high) / 100.0))
                denom = q3 - q1 or 1.0
                working[column] = (numeric - q1) / denom
                stats[column] = {"q_low": q1, "q_high": q3}
            else:
                raise TransformationError("numeric_scaling method must be standard, minmax, or robust")
        return working, {"method": method, "stats": stats}, StepEffect(operation_type, columns, f"Scaled numeric columns using {method}.")

    if operation_type == "outlier_clipping":
        method = params.get("method", "percentile")
        thresholds: dict[str, dict[str, float]] = {}
        clipped = 0
        for column in columns:
            numeric = pd.to_numeric(working[column], errors="coerce")
            if method == "percentile":
                lower = float(numeric.quantile(float(params.get("lower_percentile", 1.0)) / 100.0))
                upper = float(numeric.quantile(float(params.get("upper_percentile", 99.0)) / 100.0))
            elif method == "iqr":
                q1 = float(numeric.quantile(0.25))
                q3 = float(numeric.quantile(0.75))
                iqr = q3 - q1
                multiplier = float(params.get("iqr_multiplier", 1.5))
                lower = q1 - multiplier * iqr
                upper = q3 + multiplier * iqr
            else:
                raise TransformationError("outlier_clipping method must be percentile or iqr")
            clipped += int(((numeric < lower) | (numeric > upper)).sum())
            thresholds[column] = {"lower": lower, "upper": upper}
            working[column] = numeric.clip(lower=lower, upper=upper)
        return working, {"method": method, "thresholds": thresholds}, StepEffect(operation_type, columns, f"Clipped {clipped} values.")

    if operation_type == "log_transform":
        offset = float(params.get("offset", 0))
        replace_original = bool(params.get("replace_original", True))
        suffix = str(params.get("new_suffix", "_log"))
        for column in columns:
            numeric = pd.to_numeric(working[column], errors="coerce") + offset
            if (numeric.dropna() < 0).any():
                raise TransformationError(f"Column {column} contains negative values after offset")
            transformed = np.log1p(numeric)
            if replace_original:
                working[column] = transformed
            else:
                working[f"{column}{suffix}"] = transformed
        return working, {"offset": offset, "replace_original": replace_original, "new_suffix": suffix}, StepEffect(operation_type, columns, "Applied log1p transform.")

    if operation_type == "datetime_extract":
        features = params.get("features", ["year", "month", "day", "day_of_week", "is_weekend"])
        drop_original = bool(params.get("drop_original", True))
        date_format = params.get("date_format")
        for column in columns:
            parsed = pd.to_datetime(working[column], format=date_format, errors="coerce")
            if "year" in features:
                working[f"{column}_year"] = parsed.dt.year
            if "month" in features:
                working[f"{column}_month"] = parsed.dt.month
            if "day" in features:
                working[f"{column}_day"] = parsed.dt.day
            if "day_of_week" in features:
                working[f"{column}_day_of_week"] = parsed.dt.dayofweek
            if "is_weekend" in features:
                working[f"{column}_is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype(int)
            if drop_original:
                working = working.drop(columns=[column])
        return working, {"features": features, "drop_original": drop_original, "date_format": date_format}, StepEffect(operation_type, columns, "Extracted datetime features.")

    if operation_type == "text_basic_features":
        lowercase = bool(params.get("lowercase", False))
        strip = bool(params.get("strip_whitespace", True))
        create_length = bool(params.get("create_length_feature", True))
        create_word_count = bool(params.get("create_word_count_feature", True))
        drop_original = bool(params.get("drop_original", False))
        for column in columns:
            text = working[column].fillna("").astype(str)
            if strip:
                text = text.str.strip()
            if lowercase:
                text = text.str.lower()
            if create_length:
                working[f"{column}_length"] = text.str.len()
            if create_word_count:
                working[f"{column}_word_count"] = text.str.split().str.len()
            if drop_original:
                working = working.drop(columns=[column])
            else:
                working[column] = text
        return (
            working,
            {
                "lowercase": lowercase,
                "strip_whitespace": strip,
                "create_length_feature": create_length,
                "create_word_count_feature": create_word_count,
                "drop_original": drop_original,
            },
            StepEffect(operation_type, columns, "Created basic text features."),
        )

    if operation_type == "rename_columns":
        rename_map = params.get("rename_map", {})
        if not isinstance(rename_map, dict):
            raise TransformationError("rename_map must be an object")
        _require_columns(working, [str(column) for column in rename_map.keys()])
        working = working.rename(columns={str(key): str(value) for key, value in rename_map.items()})
        return working, {"rename_map": rename_map}, StepEffect(operation_type, list(rename_map.keys()), "Renamed columns.")

    if operation_type == "reorder_columns":
        order = params.get("column_order", [])
        if not isinstance(order, list):
            raise TransformationError("column_order must be a list")
        order = [str(column) for column in order]
        _require_columns(working, order)
        remaining = [column for column in working.columns if column not in order]
        working = working[order + remaining]
        return working, {"column_order": order}, StepEffect(operation_type, order, "Reordered columns.")

    raise TransformationError(f"Unsupported operation type: {operation_type}")


def transform_step(df: pd.DataFrame, operation_type: str, columns: list[str], fitted_params: dict[str, Any]) -> tuple[pd.DataFrame, StepEffect]:
    working = df.copy()
    columns = [column for column in columns if column in working.columns]

    if operation_type == "drop_columns":
        drop = [column for column in fitted_params["columns"] if column in working.columns]
        return working.drop(columns=drop), StepEffect(operation_type, drop, f"Dropped {len(drop)} columns.")

    if operation_type == "remove_duplicate_rows":
        subset = [column for column in fitted_params.get("subset", []) if column in working.columns]
        keep_param = fitted_params.get("keep", "first")
        keep = False if keep_param == "none" else keep_param
        before = len(working)
        working = working.drop_duplicates(subset=subset or None, keep=keep)  # type: ignore[arg-type]
        return working, StepEffect(operation_type, subset, f"Removed {before - len(working)} duplicate rows.")

    if operation_type == "replace_placeholder_values":
        for column in columns:
            working[column] = working[column].replace(fitted_params["placeholders"], fitted_params.get("replacement"))
        return working, StepEffect(operation_type, columns, "Replaced placeholder values.")

    if operation_type in {"numeric_imputation", "categorical_imputation"}:
        for column, value in fitted_params["fill_values"].items():
            if column in working.columns:
                working[column] = working[column].fillna(value)
        return working, StepEffect(operation_type, columns, "Filled missing values using train-fitted values.")

    if operation_type == "add_missing_indicator":
        suffix = fitted_params["suffix"]
        for column in columns:
            working[f"{column}{suffix}"] = working[column].isna().astype(int)
        return working, StepEffect(operation_type, columns, "Created missingness indicators.")

    if operation_type == "rare_category_grouping":
        rare_label = fitted_params["rare_label"]
        for column, frequent in fitted_params["frequent_values"].items():
            if column in working.columns:
                mask = ~working[column].astype(str).isin(frequent) & working[column].notna()
                working.loc[mask, column] = rare_label
        return working, StepEffect(operation_type, columns, "Grouped rare and unseen categories.")

    if operation_type == "one_hot_encoding":
        return _apply_one_hot(working, columns, fitted_params["categories"]), StepEffect(operation_type, columns, "One-hot encoded with train categories.")

    if operation_type == "ordinal_encoding":
        unknown_value = fitted_params["unknown_value"]
        for column, mapping in fitted_params["mappings"].items():
            if column in working.columns:
                working[column] = working[column].astype(str).map(mapping).fillna(unknown_value).astype(int)
        return working, StepEffect(operation_type, columns, "Ordinal encoded with train mappings.")

    if operation_type == "frequency_encoding":
        unknown_value = fitted_params["unknown_value"]
        for column, mapping in fitted_params["frequency_maps"].items():
            if column in working.columns:
                working[column] = working[column].astype(str).map(mapping).fillna(unknown_value)
        return working, StepEffect(operation_type, columns, "Frequency encoded with train frequencies.")

    if operation_type == "numeric_scaling":
        method = fitted_params["method"]
        for column, stats in fitted_params["stats"].items():
            if column not in working.columns:
                continue
            numeric = pd.to_numeric(working[column], errors="coerce")
            if method == "standard":
                working[column] = (numeric - stats["mean"]) / stats["std"]
            elif method == "minmax":
                denom = stats["max"] - stats["min"] or 1.0
                working[column] = ((numeric - stats["min"]) / denom) * (stats["high"] - stats["low"]) + stats["low"]
            elif method == "robust":
                denom = stats["q_high"] - stats["q_low"] or 1.0
                working[column] = (numeric - stats["q_low"]) / denom
        return working, StepEffect(operation_type, columns, "Scaled with train-fitted statistics.")

    if operation_type == "outlier_clipping":
        for column, threshold in fitted_params["thresholds"].items():
            if column in working.columns:
                working[column] = pd.to_numeric(working[column], errors="coerce").clip(threshold["lower"], threshold["upper"])
        return working, StepEffect(operation_type, columns, "Clipped with train-fitted thresholds.")

    return fit_transform_step(working, operation_type, columns, fitted_params)[0], StepEffect(operation_type, columns, "Applied stateless transform.")


def _apply_one_hot(df: pd.DataFrame, columns: list[str], categories: dict[str, list[str]]) -> pd.DataFrame:
    working = df.copy()
    for column in columns:
        if column not in working.columns:
            continue
        source = working[column].astype(str)
        for category in categories.get(column, []):
            safe_category = "".join(char if char.isalnum() or char == "_" else "_" for char in str(category))
            working[f"{column}_{safe_category}"] = (source == category).astype(int)
        working = working.drop(columns=[column])
    return working
