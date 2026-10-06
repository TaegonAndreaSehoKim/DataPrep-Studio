import math

from app.schemas import OperationMetadata, OperationParamMetadata


OPERATIONS_ALLOW_EMPTY_COLUMNS = {"remove_duplicate_rows", "rename_columns", "reorder_columns"}


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_operation_params(operation_type: str, params: dict[str, object]) -> list[str]:
    """Shared by advisory validation and execution; invalid drafts remain editable."""
    metadata = next((item for item in operation_metadata() if item.operation_type == operation_type), None)
    if metadata is None:
        return [f"Unsupported operation type: {operation_type}"]
    errors: list[str] = []
    values = {param.name: params.get(param.name, param.default) for param in metadata.params}
    known = set(values) | {"__dataprep_source"}
    for name in params.keys() - known:
        errors.append(f"Unknown param for {operation_type}: {name}")
    for param in metadata.params:
        value = values[param.name]
        if value is None:
            if param.default is not None or param.required:
                errors.append(f"Param {param.name} cannot be null")
            continue
        valid_type = {
            "string": isinstance(value, str), "select": isinstance(value, str),
            "number": _number(value), "boolean": isinstance(value, bool),
            "list": isinstance(value, list), "object": isinstance(value, dict),
        }[param.type]
        if not valid_type:
            errors.append(f"Param {param.name} must be {param.type}")
        if param.options is not None and value not in param.options:
            errors.append(f"Param {param.name} must be one of {', '.join(param.options)}")
    if errors:
        return errors

    def string_list(name: str, allowed: set[str] | None = None) -> None:
        value = values[name]
        if not all(isinstance(item, str) and item for item in value):
            errors.append(f"Param {name} must contain nonempty strings")
        elif len(value) != len(set(value)):
            errors.append(f"Param {name} must not contain duplicates")
        elif allowed is not None and not set(value).issubset(allowed):
            errors.append(f"Param {name} supports only {', '.join(sorted(allowed))}")

    def ordered_range(name: str, bounds: tuple[float, float] | None = None) -> None:
        value = values[name]
        if len(value) != 2 or not all(_number(item) for item in value):
            errors.append(f"Param {name} must contain two finite numbers")
        elif value[0] >= value[1]:
            errors.append(f"Param {name} lower value must be less than upper value")
        elif bounds and not (bounds[0] <= value[0] < value[1] <= bounds[1]):
            errors.append(f"Param {name} must be within {bounds[0]:g} and {bounds[1]:g}")

    if operation_type == "numeric_scaling":
        ordered_range("feature_range")
        ordered_range("quantile_range", (0, 100))
    if operation_type == "numeric_imputation" and values["strategy"] == "constant" and values["fill_value"] is None:
        errors.append("Constant numeric imputation requires a finite fill_value")
    if operation_type == "outlier_clipping":
        lower, upper = values["lower_percentile"], values["upper_percentile"]
        if not 0 <= lower < upper <= 100:
            errors.append("Clipping percentiles must satisfy 0 <= lower_percentile < upper_percentile <= 100")
        if values["iqr_multiplier"] <= 0:
            errors.append("Param iqr_multiplier must be positive")
    if operation_type == "rare_category_grouping":
        if not 0 <= values["min_frequency"] <= 1:
            errors.append("Param min_frequency must be within 0 and 1")
        count = values["min_count"]
        if count is not None and (not isinstance(count, int) or count < 1):
            errors.append("Param min_count must be a positive integer")
    if operation_type == "one_hot_encoding":
        count = values["max_categories"]
        if count is not None and (not isinstance(count, int) or count < 1):
            errors.append("Param max_categories must be a positive integer")
    if operation_type == "ordinal_encoding":
        if not isinstance(values["unknown_value"], int):
            errors.append("Param unknown_value must be an integer")
        for column, categories in values["categories_order"].items():
            if not isinstance(column, str) or not isinstance(categories, list) or not all(isinstance(item, str) for item in categories):
                errors.append("Param categories_order must map column names to lists of strings")
            elif len(categories) != len(set(categories)):
                errors.append(f"Param categories_order contains duplicates for {column}")
    for operation, name in [("remove_duplicate_rows", "subset"), ("reorder_columns", "column_order"), ("replace_placeholder_values", "placeholders")]:
        if operation_type == operation:
            string_list(name)
    if operation_type == "datetime_extract":
        string_list("features", {"year", "month", "day", "day_of_week", "is_weekend"})
        if not values["features"]:
            errors.append("Param features requires at least one datetime feature")
    if operation_type == "rename_columns":
        mapping = values["rename_map"]
        if not all(isinstance(key, str) and key and isinstance(value, str) and value for key, value in mapping.items()):
            errors.append("Param rename_map must map nonempty column names to nonempty names")
        elif len(mapping.values()) != len(set(mapping.values())):
            errors.append("Param rename_map targets must be unique")
    return errors


def _operation_param(
    name: str,
    type_: str,
    description: str,
    default: object | None = None,
    required: bool = False,
    options: list[str] | None = None,
) -> OperationParamMetadata:
    return OperationParamMetadata(
        name=name,
        type=type_,  # type: ignore[arg-type]
        required=required,
        default=default,
        options=options,
        description=description,
    )


def operation_metadata() -> list[OperationMetadata]:
    return [
        OperationMetadata(operation_type="drop_columns", label="Drop Columns", description="Remove selected columns.", supported_column_types=["numeric", "categorical", "boolean", "datetime", "text", "unknown"], params=[]),
        OperationMetadata(operation_type="remove_duplicate_rows", label="Remove Duplicate Rows", description="Remove duplicate rows using all or selected columns.", supported_column_types=["any"], params=[_operation_param("subset", "list", "Columns to use for duplicate detection.", []), _operation_param("keep", "select", "Which duplicate to keep.", "first", options=["first", "last", "none"])]),
        OperationMetadata(operation_type="numeric_imputation", label="Numeric Imputation", description="Fill missing numeric values.", supported_column_types=["numeric"], params=[_operation_param("strategy", "select", "Imputation strategy.", "median", options=["mean", "median", "constant"]), _operation_param("fill_value", "number", "Constant fill value.", None)]),
        OperationMetadata(operation_type="categorical_imputation", label="Categorical Imputation", description="Fill missing categorical values.", supported_column_types=["categorical", "boolean"], params=[_operation_param("strategy", "select", "Imputation strategy.", "most_frequent", options=["most_frequent", "constant"]), _operation_param("fill_value", "string", "Constant fill value.", "__MISSING__")]),
        OperationMetadata(operation_type="add_missing_indicator", label="Missing Indicator", description="Create binary missingness indicator columns.", supported_column_types=["numeric", "categorical", "boolean", "datetime", "text", "unknown"], params=[_operation_param("suffix", "string", "Suffix for indicator columns.", "_was_missing")]),
        OperationMetadata(operation_type="replace_placeholder_values", label="Replace Placeholder Values", description="Replace placeholder strings with missing values.", supported_column_types=["any"], params=[_operation_param("placeholders", "list", "Placeholder strings to replace.", ["N/A", "NA", "unknown", "?", "-"]), _operation_param("replacement", "string", "Replacement value; null means missing.", None), _operation_param("strip_whitespace", "boolean", "Trim strings for placeholder matching while preserving other values.", False)]),
        OperationMetadata(operation_type="rare_category_grouping", label="Rare Category Grouping", description="Replace rare categories with a shared label.", supported_column_types=["categorical", "text"], params=[_operation_param("min_frequency", "number", "Minimum category frequency.", 0.01), _operation_param("min_count", "number", "Minimum category count.", None), _operation_param("rare_label", "string", "Replacement label.", "__RARE__"), _operation_param("include_missing", "boolean", "Group missing values too.", False)]),
        OperationMetadata(operation_type="one_hot_encoding", label="One-Hot Encoding", description="Create one binary column per category.", supported_column_types=["categorical", "boolean"], params=[_operation_param("drop_first", "boolean", "Drop first category.", False), _operation_param("handle_unknown", "select", "Unknown category behavior.", "ignore", options=["ignore"]), _operation_param("max_categories", "number", "Maximum categories to encode.", None)]),
        OperationMetadata(operation_type="ordinal_encoding", label="Ordinal Encoding", description="Map categories to integer codes.", supported_column_types=["categorical", "boolean"], params=[_operation_param("categories_order", "object", "Explicit category order per column.", {}), _operation_param("unknown_value", "number", "Value for unknown categories.", -1)]),
        OperationMetadata(operation_type="frequency_encoding", label="Frequency Encoding", description="Map categories to observed train frequencies.", supported_column_types=["categorical", "boolean"], params=[_operation_param("normalize", "boolean", "Use normalized frequencies.", True), _operation_param("unknown_value", "number", "Value for unknown categories.", 0)]),
        OperationMetadata(operation_type="numeric_scaling", label="Numeric Scaling", description="Scale numeric columns.", supported_column_types=["numeric"], params=[_operation_param("method", "select", "Scaling method.", "standard", options=["standard", "minmax", "robust"]), _operation_param("feature_range", "list", "Min/max range for minmax scaling.", [0, 1]), _operation_param("quantile_range", "list", "Quantile range for robust scaling.", [25, 75])]),
        OperationMetadata(operation_type="outlier_clipping", label="Outlier Clipping", description="Clip numeric values to learned thresholds.", supported_column_types=["numeric"], params=[_operation_param("method", "select", "Threshold method.", "percentile", options=["percentile", "iqr"]), _operation_param("lower_percentile", "number", "Lower percentile.", 1.0), _operation_param("upper_percentile", "number", "Upper percentile.", 99.0), _operation_param("iqr_multiplier", "number", "IQR multiplier.", 1.5)]),
        OperationMetadata(operation_type="log_transform", label="Log Transform", description="Apply log1p-style numeric transformation.", supported_column_types=["numeric"], params=[_operation_param("method", "select", "Log method.", "log1p", options=["log1p"]), _operation_param("offset", "number", "Offset before transform.", 0), _operation_param("replace_original", "boolean", "Replace original column.", True), _operation_param("new_suffix", "string", "Suffix for new column.", "_log")]),
        OperationMetadata(operation_type="datetime_extract", label="Datetime Extract", description="Extract datetime features.", supported_column_types=["datetime"], params=[_operation_param("date_format", "string", "Optional datetime format.", None), _operation_param("features", "list", "Datetime features to create.", ["year", "month", "day", "day_of_week", "is_weekend"]), _operation_param("drop_original", "boolean", "Drop original column.", True)]),
        OperationMetadata(operation_type="text_basic_features", label="Text Basic Features", description="Clean text and optionally create length features.", supported_column_types=["text"], params=[_operation_param("lowercase", "boolean", "Lowercase text.", False), _operation_param("strip_whitespace", "boolean", "Strip whitespace.", True), _operation_param("create_length_feature", "boolean", "Create character length feature.", True), _operation_param("create_word_count_feature", "boolean", "Create word count feature.", True), _operation_param("drop_original", "boolean", "Drop original column.", False)]),
        OperationMetadata(operation_type="rename_columns", label="Rename Columns", description="Rename columns with an explicit map.", supported_column_types=["any"], params=[_operation_param("rename_map", "object", "Old-to-new column name map.", {})]),
        OperationMetadata(operation_type="reorder_columns", label="Reorder Columns", description="Reorder columns.", supported_column_types=["any"], params=[_operation_param("column_order", "list", "Desired column order.", [])]),
    ]


