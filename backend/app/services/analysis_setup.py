import pandas as pd

from app.schemas import AnalysisOptions, PipelineStepCreate


def build_analysis_setup_steps(options: AnalysisOptions, frames: list[pd.DataFrame]) -> list[PipelineStepCreate]:
    """Produce explicit, editable steps from an immutable analysis snapshot."""
    source = {"type": "analysis_setup", "title": "Analysis setup", "reason": "Added explicitly from the linked analysis snapshot."}
    steps = []
    ignored = [column for column in options.ignored_columns if any(column in frame.columns for frame in frames)]
    missing = [column for column in ignored if not all(column in frame.columns for frame in frames)]
    if missing:
        raise ValueError(f"Analysis setup columns must exist in both splits: {', '.join(missing)}")
    if ignored:
        steps.append(PipelineStepCreate(operation_type="drop_columns", columns=ignored, params={"__dataprep_source": source}))
    if options.missing_value_tokens:
        text_columns = set().union(*(set(frame.select_dtypes(include=["object", "string"]).columns) for frame in frames))
        columns = [column for column in frames[0].columns if column in text_columns and column not in ignored and all(column in frame.columns for frame in frames)]
        if columns:
            steps.append(PipelineStepCreate(
                operation_type="replace_placeholder_values", columns=columns,
                params={"placeholders": options.missing_value_tokens, "replacement": None, "strip_whitespace": True, "__dataprep_source": source},
            ))
    return steps
