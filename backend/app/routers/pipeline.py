import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import AnalysisRun, ColumnProfile, DatasetFile, Issue, Pipeline, PipelineRun, PipelineStep, Project, utc_now
from app.schemas import (
    OperationMetadata,
    OperationParamMetadata,
    PipelineCreate,
    PipelineOut,
    PipelineRunOut,
    PipelineStepCreate,
    PipelineStepOut,
    PipelineStepReorder,
    PipelineStepUpdate,
    PipelineValidationIssue,
    PipelineValidationOut,
    PreviewRequest,
    SuggestedPipelineCreate,
    SuggestedPipelineStepOut,
)
from app.services.csv_loader import CsvValidationError, read_csv_file
from app.services.export_service import write_pipeline_exports
from app.services.pipeline_engine import (
    PipelineStepSpec,
    apply_pipeline_single,
    apply_pipeline_train_test,
    summarize_dataframe,
)
from app.services.suggestion_builder import build_suggested_pipeline_steps, build_suggested_step
from app.services.transformations import TransformationError

router = APIRouter(tags=["pipeline"])

OPERATIONS_ALLOW_EMPTY_COLUMNS = {"remove_duplicate_rows", "rename_columns", "reorder_columns"}


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _step_to_out(step: PipelineStep) -> PipelineStepOut:
    return PipelineStepOut(
        id=step.id,
        pipeline_id=step.pipeline_id,
        order_index=step.order_index,
        enabled=step.enabled,
        operation_type=step.operation_type,
        columns=_json_loads(step.columns_json, []),
        params=_json_loads(step.params_json, {}),
        created_at=step.created_at,
        updated_at=step.updated_at,
    )


def _pipeline_to_out(pipeline: Pipeline, steps: list[PipelineStep] | None = None) -> PipelineOut:
    ordered_steps = steps if steps is not None else sorted(pipeline.steps, key=lambda item: item.order_index)
    return PipelineOut(
        id=pipeline.id,
        project_id=pipeline.project_id,
        analysis_run_id=pipeline.analysis_run_id,
        name=pipeline.name,
        description=pipeline.description,
        mode=pipeline.mode,  # type: ignore[arg-type]
        status=pipeline.status,  # type: ignore[arg-type]
        steps=[_step_to_out(step) for step in ordered_steps],
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
    )


def _pipeline_run_to_out(run: PipelineRun) -> PipelineRunOut:
    return PipelineRunOut(
        id=run.id,
        pipeline_id=run.pipeline_id,
        project_id=run.project_id,
        status=run.status,  # type: ignore[arg-type]
        before_summary=_json_loads(run.before_summary_json, {}),
        after_summary=_json_loads(run.after_summary_json, {}),
        output_paths=_json_loads(run.output_paths_json, {}),
        report_path=run.report_path,
        config_path=run.config_path,
        code_path=run.code_path,
        created_at=run.created_at,
    )


def _get_pipeline_or_404(pipeline_id: int, db: Session) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return pipeline


def _get_step_or_404(pipeline_id: int, step_id: int, db: Session) -> PipelineStep:
    step = db.get(PipelineStep, step_id)
    if step is None or step.pipeline_id != pipeline_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline step not found")
    return step


def _latest_dataset(db: Session, project_id: int, role: str) -> DatasetFile | None:
    return db.scalars(
        select(DatasetFile)
        .where(DatasetFile.project_id == project_id, DatasetFile.role == role)
        .order_by(DatasetFile.created_at.desc())
        .limit(1)
    ).first()


def _step_specs(db: Session, pipeline_id: int) -> list[PipelineStepSpec]:
    steps = db.scalars(select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)).all()
    return [
        PipelineStepSpec(
            id=step.id,
            order_index=step.order_index,
            enabled=step.enabled,
            operation_type=step.operation_type,
            columns=_json_loads(step.columns_json, []),
            params=_json_loads(step.params_json, {}),
        )
        for step in steps
    ]


def _column_profiles_by_name(db: Session, analysis_run_id: int | None) -> dict[str, ColumnProfile]:
    if analysis_run_id is None:
        return {}
    profiles = db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_run_id)).all()
    by_name: dict[str, ColumnProfile] = {}
    for profile in profiles:
        by_name.setdefault(profile.column_name, profile)
    return by_name


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


@router.get("/pipeline/operations", response_model=list[OperationMetadata])
def operation_metadata() -> list[OperationMetadata]:
    return [
        OperationMetadata(operation_type="drop_columns", label="Drop Columns", description="Remove selected columns.", supported_column_types=["numeric", "categorical", "boolean", "datetime", "text", "unknown"], params=[]),
        OperationMetadata(operation_type="remove_duplicate_rows", label="Remove Duplicate Rows", description="Remove duplicate rows using all or selected columns.", supported_column_types=["any"], params=[_operation_param("subset", "list", "Columns to use for duplicate detection.", []), _operation_param("keep", "select", "Which duplicate to keep.", "first", options=["first", "last", "none"])]),
        OperationMetadata(operation_type="numeric_imputation", label="Numeric Imputation", description="Fill missing numeric values.", supported_column_types=["numeric"], params=[_operation_param("strategy", "select", "Imputation strategy.", "median", options=["mean", "median", "constant"]), _operation_param("fill_value", "number", "Constant fill value.", None)]),
        OperationMetadata(operation_type="categorical_imputation", label="Categorical Imputation", description="Fill missing categorical values.", supported_column_types=["categorical", "boolean"], params=[_operation_param("strategy", "select", "Imputation strategy.", "most_frequent", options=["most_frequent", "constant"]), _operation_param("fill_value", "string", "Constant fill value.", "__MISSING__")]),
        OperationMetadata(operation_type="add_missing_indicator", label="Missing Indicator", description="Create binary missingness indicator columns.", supported_column_types=["numeric", "categorical", "boolean", "datetime", "text", "unknown"], params=[_operation_param("suffix", "string", "Suffix for indicator columns.", "_was_missing")]),
        OperationMetadata(operation_type="replace_placeholder_values", label="Replace Placeholder Values", description="Replace placeholder strings with missing values.", supported_column_types=["categorical", "text", "unknown"], params=[_operation_param("placeholders", "list", "Placeholder strings to replace.", ["N/A", "NA", "unknown", "?", "-"]), _operation_param("replacement", "string", "Replacement value; null means missing.", None)]),
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


def _validate_step_against_metadata(
    step: PipelineStep,
    metadata_by_type: dict[str, OperationMetadata],
    profiles_by_name: dict[str, ColumnProfile],
) -> list[PipelineValidationIssue]:
    issues: list[PipelineValidationIssue] = []
    columns = _json_loads(step.columns_json, [])
    params = _json_loads(step.params_json, {})
    metadata = metadata_by_type.get(step.operation_type)
    if metadata is None:
        return [
            PipelineValidationIssue(
                severity="error",
                step_id=step.id,
                operation_type=step.operation_type,
                message=f"Unsupported operation type: {step.operation_type}",
            )
        ]

    if not isinstance(columns, list):
        issues.append(
            PipelineValidationIssue(
                severity="error",
                step_id=step.id,
                operation_type=step.operation_type,
                message="Step columns must be a list.",
            )
        )
        columns = []

    if not columns and step.operation_type not in OPERATIONS_ALLOW_EMPTY_COLUMNS:
        issues.append(
            PipelineValidationIssue(
                severity="error",
                step_id=step.id,
                operation_type=step.operation_type,
                message=f"{step.operation_type} requires at least one selected column.",
            )
        )

    if profiles_by_name and isinstance(columns, list):
        supported = set(metadata.supported_column_types)
        for column in columns:
            if column not in profiles_by_name:
                issues.append(
                    PipelineValidationIssue(
                        severity="error",
                        step_id=step.id,
                        operation_type=step.operation_type,
                        message=f"Column does not exist in analysis profile: {column}",
                    )
                )
                continue
            inferred_type = profiles_by_name[column].inferred_type
            if "any" not in supported and inferred_type not in supported:
                issues.append(
                    PipelineValidationIssue(
                        severity="error",
                        step_id=step.id,
                        operation_type=step.operation_type,
                        message=f"Column {column} is {inferred_type}, but {step.operation_type} supports {', '.join(metadata.supported_column_types)}",
                    )
                )

    if not isinstance(params, dict):
        issues.append(
            PipelineValidationIssue(
                severity="error",
                step_id=step.id,
                operation_type=step.operation_type,
                message="Step params must be an object.",
            )
        )
        return issues

    for param in metadata.params:
        value = params.get(param.name, param.default)
        if param.required and param.name not in params:
            issues.append(
                PipelineValidationIssue(
                    severity="error",
                    step_id=step.id,
                    operation_type=step.operation_type,
                    message=f"Missing required param: {param.name}",
                )
            )
        if param.options is not None and value is not None and str(value) not in param.options:
            issues.append(
                PipelineValidationIssue(
                    severity="error",
                    step_id=step.id,
                    operation_type=step.operation_type,
                    message=f"Param {param.name} must be one of {', '.join(param.options)}",
                )
            )

    return issues


@router.post("/projects/{project_id}/pipelines", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(project_id: int, payload: PipelineCreate, db: Session = Depends(get_db)) -> PipelineOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if payload.analysis_run_id is not None:
        analysis = db.get(AnalysisRun, payload.analysis_run_id)
        if analysis is None or analysis.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Analysis run does not belong to project")

    pipeline = Pipeline(
        project_id=project_id,
        analysis_run_id=payload.analysis_run_id,
        name=payload.name,
        description=payload.description,
        mode=payload.mode,
        status="draft",
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return _pipeline_to_out(pipeline, [])


@router.post("/projects/{project_id}/pipelines/from-analysis/{analysis_id}", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_suggested_pipeline(
    project_id: int,
    analysis_id: int,
    payload: SuggestedPipelineCreate | None = None,
    db: Session = Depends(get_db),
) -> PipelineOut:
    analysis = db.get(AnalysisRun, analysis_id)
    if analysis is None or analysis.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found for project")
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    profiles = db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id)).all()
    issues = db.scalars(select(Issue).where(Issue.analysis_run_id == analysis_id).order_by(Issue.id)).all()
    suggested_steps = build_suggested_pipeline_steps(list(issues), list(profiles))
    mode = "train_test" if analysis.train_dataset_file_id and analysis.test_dataset_file_id else "single"
    pipeline = Pipeline(
        project_id=project_id,
        analysis_run_id=analysis_id,
        name=(payload.name if payload and payload.name else f"Suggested preprocessing #{analysis_id}"),
        description="Generated from the analysis issue suggestions. Review and validate before applying.",
        mode=mode,
        status="draft",
    )
    db.add(pipeline)
    db.flush()

    steps: list[PipelineStep] = []
    for index, suggestion in enumerate(suggested_steps):
        step = PipelineStep(
            pipeline_id=pipeline.id,
            order_index=index,
            enabled=True,
            operation_type=suggestion.operation_type,
            columns_json=json.dumps(suggestion.columns),
            params_json=json.dumps(suggestion.params),
        )
        db.add(step)
        steps.append(step)

    db.commit()
    db.refresh(pipeline)
    for step in steps:
        db.refresh(step)
    return _pipeline_to_out(pipeline, steps)


@router.get("/projects/{project_id}/pipelines", response_model=list[PipelineOut])
def list_project_pipelines(project_id: int, db: Session = Depends(get_db)) -> list[PipelineOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    pipelines = db.scalars(select(Pipeline).where(Pipeline.project_id == project_id).order_by(Pipeline.created_at.desc())).all()
    return [_pipeline_to_out(pipeline) for pipeline in pipelines]


@router.get("/pipelines/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(pipeline_id: int, db: Session = Depends(get_db)) -> PipelineOut:
    return _pipeline_to_out(_get_pipeline_or_404(pipeline_id, db))


@router.delete("/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(pipeline_id: int, db: Session = Depends(get_db)) -> None:
    pipeline = _get_pipeline_or_404(pipeline_id, db)
    db.delete(pipeline)
    db.commit()


@router.post("/pipelines/{pipeline_id}/validate", response_model=PipelineValidationOut)
def validate_pipeline(pipeline_id: int, db: Session = Depends(get_db)) -> PipelineValidationOut:
    pipeline = _get_pipeline_or_404(pipeline_id, db)
    steps = db.scalars(select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)).all()
    metadata_by_type = {metadata.operation_type: metadata for metadata in operation_metadata()}
    profiles_by_name = _column_profiles_by_name(db, pipeline.analysis_run_id)

    issues: list[PipelineValidationIssue] = []
    if not steps:
        issues.append(PipelineValidationIssue(severity="warning", message="Pipeline has no steps."))
    for step in steps:
        if not step.enabled:
            continue
        issues.extend(_validate_step_against_metadata(step, metadata_by_type, profiles_by_name))

    return PipelineValidationOut(valid=not any(issue.severity == "error" for issue in issues), issues=issues)


@router.get("/issues/{issue_id}/suggested-step", response_model=SuggestedPipelineStepOut)
def get_issue_suggested_step(issue_id: int, db: Session = Depends(get_db)) -> SuggestedPipelineStepOut:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    profiles = db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == issue.analysis_run_id)).all()
    suggestion = build_suggested_step(issue, list(profiles))
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No suggested pipeline step for this issue")
    return suggestion


@router.post("/pipelines/{pipeline_id}/steps/from-issue/{issue_id}", response_model=PipelineStepOut, status_code=status.HTTP_201_CREATED)
def create_pipeline_step_from_issue(pipeline_id: int, issue_id: int, db: Session = Depends(get_db)) -> PipelineStepOut:
    pipeline = _get_pipeline_or_404(pipeline_id, db)
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    analysis = db.get(AnalysisRun, issue.analysis_run_id)
    if analysis is None or analysis.project_id != pipeline.project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Issue does not belong to pipeline project")

    profiles = db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == issue.analysis_run_id)).all()
    suggestion = build_suggested_step(issue, list(profiles))
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No suggested pipeline step for this issue")

    max_order = db.scalar(select(func.max(PipelineStep.order_index)).where(PipelineStep.pipeline_id == pipeline_id))
    step = PipelineStep(
        pipeline_id=pipeline_id,
        order_index=int(max_order + 1 if max_order is not None else 0),
        enabled=True,
        operation_type=suggestion.operation_type,
        columns_json=json.dumps(suggestion.columns),
        params_json=json.dumps(suggestion.params),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return _step_to_out(step)


@router.post("/pipelines/{pipeline_id}/steps", response_model=PipelineStepOut, status_code=status.HTTP_201_CREATED)
def create_pipeline_step(pipeline_id: int, payload: PipelineStepCreate, db: Session = Depends(get_db)) -> PipelineStepOut:
    _get_pipeline_or_404(pipeline_id, db)
    max_order = db.scalar(select(func.max(PipelineStep.order_index)).where(PipelineStep.pipeline_id == pipeline_id))
    step = PipelineStep(
        pipeline_id=pipeline_id,
        order_index=int(max_order + 1 if max_order is not None else 0),
        enabled=payload.enabled,
        operation_type=payload.operation_type,
        columns_json=json.dumps(payload.columns),
        params_json=json.dumps(payload.params),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return _step_to_out(step)


@router.patch("/pipelines/{pipeline_id}/steps/{step_id}", response_model=PipelineStepOut)
def update_pipeline_step(pipeline_id: int, step_id: int, payload: PipelineStepUpdate, db: Session = Depends(get_db)) -> PipelineStepOut:
    step = _get_step_or_404(pipeline_id, step_id, db)
    updates = payload.model_dump(exclude_unset=True)
    if "operation_type" in updates:
        step.operation_type = updates["operation_type"]
    if "columns" in updates:
        step.columns_json = json.dumps(updates["columns"])
    if "params" in updates:
        step.params_json = json.dumps(updates["params"])
    if "enabled" in updates:
        step.enabled = updates["enabled"]
    step.updated_at = utc_now()
    db.commit()
    db.refresh(step)
    return _step_to_out(step)


@router.delete("/pipelines/{pipeline_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_step(pipeline_id: int, step_id: int, db: Session = Depends(get_db)) -> None:
    step = _get_step_or_404(pipeline_id, step_id, db)
    db.delete(step)
    db.flush()
    steps = db.scalars(select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)).all()
    for index, item in enumerate(steps):
        item.order_index = index
    db.commit()


@router.post("/pipelines/{pipeline_id}/steps/reorder", response_model=PipelineOut)
def reorder_pipeline_steps(pipeline_id: int, payload: PipelineStepReorder, db: Session = Depends(get_db)) -> PipelineOut:
    pipeline = _get_pipeline_or_404(pipeline_id, db)
    steps = db.scalars(select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id)).all()
    by_id = {step.id: step for step in steps}
    if set(payload.step_ids) != set(by_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Step ids must match the pipeline's current steps")
    for index, step_id in enumerate(payload.step_ids):
        by_id[step_id].order_index = index
        by_id[step_id].updated_at = utc_now()
    pipeline.updated_at = utc_now()
    db.commit()
    db.refresh(pipeline)
    ordered_steps = sorted(by_id.values(), key=lambda item: item.order_index)
    return _pipeline_to_out(pipeline, ordered_steps)


@router.post("/pipelines/{pipeline_id}/steps/{step_id}/toggle", response_model=PipelineStepOut)
def toggle_pipeline_step(pipeline_id: int, step_id: int, db: Session = Depends(get_db)) -> PipelineStepOut:
    step = _get_step_or_404(pipeline_id, step_id, db)
    step.enabled = not step.enabled
    step.updated_at = utc_now()
    db.commit()
    db.refresh(step)
    return _step_to_out(step)


@router.post("/pipelines/{pipeline_id}/apply", response_model=PipelineRunOut, status_code=status.HTTP_201_CREATED)
def apply_pipeline(pipeline_id: int, payload: PreviewRequest | None = None, db: Session = Depends(get_db)) -> PipelineRunOut:
    pipeline = _get_pipeline_or_404(pipeline_id, db)
    analysis = db.get(AnalysisRun, pipeline.analysis_run_id) if pipeline.analysis_run_id else None
    target_column = analysis.target_column if analysis else None
    problem_type = analysis.problem_type if analysis else "unknown"
    steps = _step_specs(db, pipeline_id)

    try:
        if pipeline.mode == "single":
            dataset = db.get(DatasetFile, analysis.single_dataset_file_id) if analysis and analysis.single_dataset_file_id else _latest_dataset(db, pipeline.project_id, "single")
            if dataset is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline project does not have a single dataset")
            df = read_csv_file(dataset.storage_path)
            before_summary = summarize_dataframe(df)
            result = apply_pipeline_single(df, steps)
            assert result.single_df is not None
            after_summary = summarize_dataframe(result.single_df)
            input_file_names = [dataset.filename]

            run = PipelineRun(
                pipeline_id=pipeline.id,
                project_id=pipeline.project_id,
                status="completed",
                before_summary_json=json.dumps(before_summary, default=str),
                after_summary_json=json.dumps(after_summary, default=str),
                output_paths_json="{}",
            )
            db.add(run)
            db.flush()
            output_paths = write_pipeline_exports(
                project_id=pipeline.project_id,
                pipeline_id=pipeline.id,
                pipeline_run_id=run.id,
                mode=pipeline.mode,
                target_column=target_column,
                problem_type=problem_type,
                input_file_names=input_file_names,
                before_summary=before_summary,
                after_summary=after_summary,
                step_effects=result.step_effects or [],
                fitted_params=result.fitted_params or [],
                warnings=result.warnings or [],
                single_df=result.single_df,
            )
        else:
            train_dataset = db.get(DatasetFile, analysis.train_dataset_file_id) if analysis and analysis.train_dataset_file_id else _latest_dataset(db, pipeline.project_id, "train")
            test_dataset = db.get(DatasetFile, analysis.test_dataset_file_id) if analysis and analysis.test_dataset_file_id else _latest_dataset(db, pipeline.project_id, "test")
            if train_dataset is None or test_dataset is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline project must have train and test datasets")
            train_df = read_csv_file(train_dataset.storage_path)
            test_df = read_csv_file(test_dataset.storage_path)
            before_summary = {"train": summarize_dataframe(train_df), "test": summarize_dataframe(test_df)}
            result = apply_pipeline_train_test(train_df, test_df, steps)
            assert result.train_df is not None and result.test_df is not None
            after_summary = {"train": summarize_dataframe(result.train_df), "test": summarize_dataframe(result.test_df)}
            input_file_names = [train_dataset.filename, test_dataset.filename]

            run = PipelineRun(
                pipeline_id=pipeline.id,
                project_id=pipeline.project_id,
                status="completed",
                before_summary_json=json.dumps(before_summary, default=str),
                after_summary_json=json.dumps(after_summary, default=str),
                output_paths_json="{}",
            )
            db.add(run)
            db.flush()
            output_paths = write_pipeline_exports(
                project_id=pipeline.project_id,
                pipeline_id=pipeline.id,
                pipeline_run_id=run.id,
                mode=pipeline.mode,
                target_column=target_column,
                problem_type=problem_type,
                input_file_names=input_file_names,
                before_summary=before_summary,
                after_summary=after_summary,
                step_effects=result.step_effects or [],
                fitted_params=result.fitted_params or [],
                warnings=(result.warnings or []) + ["Train/test mode fit preprocessing parameters on train only."],
                train_df=result.train_df,
                test_df=result.test_df,
            )
    except CsvValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TransformationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    run.output_paths_json = json.dumps(output_paths)
    run.config_path = output_paths.get("config")
    run.report_path = output_paths.get("report")
    run.code_path = output_paths.get("code")
    pipeline.status = "applied"
    pipeline.updated_at = utc_now()
    db.commit()
    db.refresh(run)
    return _pipeline_run_to_out(run)
