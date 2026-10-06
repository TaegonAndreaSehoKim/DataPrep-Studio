import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import AnalysisRun, ColumnProfile, DatasetFile, Issue, Pipeline, PipelineRun, PipelineStep, Project, utc_now
from app.schemas import (
    AnalysisOptions,
    OperationMetadata,
    PipelineConfigImportCreate,
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
from app.services.analysis_setup import build_analysis_setup_steps
from app.services.export_service import write_pipeline_exports
from app.services.operation_registry import (
    OPERATIONS_ALLOW_EMPTY_COLUMNS,
    operation_metadata as get_operation_metadata,
    validate_operation_params,
)
from app.services.pipeline_engine import (
    PipelineStepSpec,
    apply_pipeline_single,
    apply_pipeline_train_test,
    prepare_train_test_step,
    summarize_dataframe,
)
from app.services.suggestion_builder import build_suggested_pipeline_steps, build_suggested_step
from app.services.transformations import TransformationError

router = APIRouter(tags=["pipeline"])


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


@router.get("/pipeline/operations", response_model=list[OperationMetadata])
def operation_metadata() -> list[OperationMetadata]:
    return get_operation_metadata()


def _validate_step_against_metadata(
    step: PipelineStep,
    metadata_by_type: dict[str, OperationMetadata],
    current_column_types: dict[str, str],
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

    if len(columns) != len(set(columns)):
        issues.append(PipelineValidationIssue(severity="error", step_id=step.id, operation_type=step.operation_type, message="Selected columns must not contain duplicates"))

    if current_column_types and isinstance(columns, list):
        supported = set(metadata.supported_column_types)
        for column in columns:
            if column not in current_column_types:
                issues.append(
                    PipelineValidationIssue(
                        severity="error",
                        step_id=step.id,
                        operation_type=step.operation_type,
                        message=f"Column is not available at this step: {column}",
                    )
                )
                continue
            inferred_type = current_column_types[column]
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

    for message in validate_operation_params(step.operation_type, params):
        issues.append(PipelineValidationIssue(
            severity="error", step_id=step.id, operation_type=step.operation_type, message=message,
        ))

    issues.extend(_validate_operation_dependencies(step, columns, params, current_column_types))
    return issues


def _validate_operation_dependencies(
    step: PipelineStep,
    columns: list[str],
    params: dict[str, object],
    current_column_types: dict[str, str],
) -> list[PipelineValidationIssue]:
    issues: list[PipelineValidationIssue] = []
    if not current_column_types:
        return issues

    generated: list[str] = []
    if step.operation_type == "add_missing_indicator":
        generated = [f"{column}{params.get('suffix', '_was_missing')}" for column in columns]
    elif step.operation_type == "log_transform" and not params.get("replace_original", True):
        generated = [f"{column}{params.get('new_suffix', '_log')}" for column in columns]
    elif step.operation_type == "datetime_extract" and isinstance(params.get("features", []), list):
        features = params.get("features", ["year", "month", "day", "day_of_week", "is_weekend"])
        generated = [f"{column}_{feature}" for column in columns for feature in features]
    elif step.operation_type == "text_basic_features":
        generated = [f"{column}_{suffix}" for column in columns for suffix, enabled in [
            ("length", params.get("create_length_feature", True)),
            ("word_count", params.get("create_word_count_feature", True)),
        ] if enabled]
    for column in generated:
        if column in current_column_types:
            issues.append(PipelineValidationIssue(
                severity="error", step_id=step.id, operation_type=step.operation_type,
                message=f"Generated column already exists: {column}",
            ))

    if step.operation_type == "remove_duplicate_rows":
        subset = params.get("subset") or columns
        if subset and isinstance(subset, list):
            for column in [str(item) for item in subset]:
                if column not in current_column_types:
                    issues.append(
                        PipelineValidationIssue(
                            severity="error",
                            step_id=step.id,
                            operation_type=step.operation_type,
                            message=f"Duplicate subset column is not available at this step: {column}",
                        )
                    )

    if step.operation_type == "rename_columns":
        rename_map = params.get("rename_map", {})
        if not isinstance(rename_map, dict):
            return issues
        existing_targets = set(current_column_types)
        for source, target in rename_map.items():
            source_name = str(source)
            target_name = str(target)
            if source_name not in current_column_types:
                issues.append(
                    PipelineValidationIssue(
                        severity="error",
                        step_id=step.id,
                        operation_type=step.operation_type,
                        message=f"Rename source column is not available at this step: {source_name}",
                    )
                )
            if target_name in existing_targets and target_name not in rename_map:
                issues.append(
                    PipelineValidationIssue(
                        severity="error",
                        step_id=step.id,
                        operation_type=step.operation_type,
                        message=f"Rename target already exists: {target_name}",
                    )
                )

    if step.operation_type == "reorder_columns":
        order = params.get("column_order", [])
        if not isinstance(order, list):
            return issues
        for column in [str(item) for item in order]:
            if column not in current_column_types:
                issues.append(
                    PipelineValidationIssue(
                        severity="error",
                        step_id=step.id,
                        operation_type=step.operation_type,
                        message=f"Reorder column is not available at this step: {column}",
                    )
                )
    return issues


def _apply_step_column_state(step: PipelineStep, current_column_types: dict[str, str]) -> dict[str, str]:
    next_types = dict(current_column_types)
    columns = _json_loads(step.columns_json, [])
    params = _json_loads(step.params_json, {})
    if not isinstance(columns, list) or not isinstance(params, dict):
        return next_types
    columns = [str(column) for column in columns if str(column) in next_types]

    if step.operation_type == "drop_columns":
        for column in columns:
            next_types.pop(column, None)
    elif step.operation_type == "add_missing_indicator":
        suffix = str(params.get("suffix", "_was_missing"))
        for column in columns:
            next_types[f"{column}{suffix}"] = "numeric"
    elif step.operation_type == "one_hot_encoding":
        for column in columns:
            next_types.pop(column, None)
            max_categories = params.get("max_categories")
            if isinstance(max_categories, int) and max_categories > 0:
                for index in range(max_categories):
                    next_types[f"{column}_category_{index + 1}"] = "numeric"
    elif step.operation_type in {"ordinal_encoding", "frequency_encoding"}:
        for column in columns:
            next_types[column] = "numeric"
    elif step.operation_type == "log_transform":
        if not bool(params.get("replace_original", True)):
            suffix = str(params.get("new_suffix", "_log"))
            for column in columns:
                next_types[f"{column}{suffix}"] = "numeric"
    elif step.operation_type == "datetime_extract":
        features = params.get("features", ["year", "month", "day", "day_of_week", "is_weekend"])
        if not isinstance(features, list):
            features = []
        for column in columns:
            for feature in [str(item) for item in features]:
                next_types[f"{column}_{feature}"] = "numeric"
            if bool(params.get("drop_original", True)):
                next_types.pop(column, None)
    elif step.operation_type == "text_basic_features":
        for column in columns:
            if bool(params.get("create_length_feature", True)):
                next_types[f"{column}_length"] = "numeric"
            if bool(params.get("create_word_count_feature", True)):
                next_types[f"{column}_word_count"] = "numeric"
            if bool(params.get("drop_original", False)):
                next_types.pop(column, None)
    elif step.operation_type == "rename_columns":
        rename_map = params.get("rename_map", {})
        if isinstance(rename_map, dict):
            next_types = {str(rename_map.get(column, column)): type_ for column, type_ in next_types.items()}

    return next_types


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


def _step_from_import_entry(entry: object, index: int, supported_operations: set[str]) -> dict[str, object]:
    if not isinstance(entry, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Config step {index + 1} must be an object")
    operation_type = entry.get("operation_type")
    if not isinstance(operation_type, str) or not operation_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Config step {index + 1} is missing operation_type")
    if operation_type not in supported_operations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported operation in config step {index + 1}: {operation_type}")
    columns = entry.get("columns", [])
    params = entry.get("params", {})
    if not isinstance(columns, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Config step {index + 1} columns must be a list")
    if not isinstance(params, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Config step {index + 1} params must be an object")
    return {
        "operation_type": operation_type,
        "columns": [str(column) for column in columns],
        "params": params,
    }


@router.post("/projects/{project_id}/pipelines/from-config", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline_from_config(
    project_id: int,
    payload: PipelineConfigImportCreate,
    db: Session = Depends(get_db),
) -> PipelineOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if payload.analysis_run_id is not None:
        analysis = db.get(AnalysisRun, payload.analysis_run_id)
        if analysis is None or analysis.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Analysis run does not belong to project")

    config = payload.config
    mode = config.get("mode", "single")
    if not isinstance(mode, str) or mode not in {"single", "train_test"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Config mode must be single or train_test")
    raw_steps = config.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Config must contain at least one step")

    supported_operations = {metadata.operation_type for metadata in operation_metadata()}
    imported_steps = [_step_from_import_entry(entry, index, supported_operations) for index, entry in enumerate(raw_steps)]
    metadata = config.get("metadata")
    metadata_name = metadata.get("pipeline_name") if isinstance(metadata, dict) else None
    default_name = metadata_name if isinstance(metadata_name, str) and metadata_name.strip() else "Imported preprocessing config"
    pipeline = Pipeline(
        project_id=project_id,
        analysis_run_id=payload.analysis_run_id,
        name=payload.name or default_name,
        description="Imported from a DataPrep Studio preprocessing_config.json. Review and validate before applying.",
        mode=str(mode),
        status="draft",
    )
    db.add(pipeline)
    db.flush()

    steps: list[PipelineStep] = []
    for index, imported_step in enumerate(imported_steps):
        step = PipelineStep(
            pipeline_id=pipeline.id,
            order_index=index,
            enabled=True,
            operation_type=str(imported_step["operation_type"]),
            columns_json=json.dumps(imported_step["columns"]),
            params_json=json.dumps(imported_step["params"]),
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


@router.post("/pipelines/{pipeline_id}/analysis-setup", response_model=PipelineOut)
def add_analysis_setup(pipeline_id: int, db: Session = Depends(get_db)) -> PipelineOut:
    pipeline = _get_pipeline_or_404(pipeline_id, db)
    analysis = db.get(AnalysisRun, pipeline.analysis_run_id) if pipeline.analysis_run_id else None
    if analysis is None or _json_loads(analysis.options_json, None) is None:
        raise HTTPException(status_code=400, detail="Linked analysis has no saved setup snapshot; run analysis again")
    options = AnalysisOptions.model_validate_json(analysis.options_json)
    if options.mode != pipeline.mode:
        raise HTTPException(status_code=400, detail="Pipeline mode must match the linked analysis setup")
    steps = sorted(pipeline.steps, key=lambda step: step.order_index)
    for step in steps:
        source = _json_loads(step.params_json, {}).get("__dataprep_source")
        if isinstance(source, dict) and source.get("type") == "analysis_setup":
            return _pipeline_to_out(pipeline, steps)
    ids = [analysis.single_dataset_file_id] if pipeline.mode == "single" else [analysis.train_dataset_file_id, analysis.test_dataset_file_id]
    datasets = [db.get(DatasetFile, dataset_id) if dataset_id else None for dataset_id in ids]
    if any(dataset is None for dataset in datasets):
        raise HTTPException(status_code=400, detail="Analysis source dataset is missing")
    try:
        drafts = build_analysis_setup_steps(options, [read_csv_file(dataset.storage_path) for dataset in datasets])
    except (CsvValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for index, step in enumerate(steps, start=len(drafts)):
        step.order_index = index
    prepended = []
    for index, draft in enumerate(drafts):
        step = PipelineStep(pipeline_id=pipeline.id, order_index=index, enabled=True,
                            operation_type=draft.operation_type, columns_json=json.dumps(draft.columns), params_json=json.dumps(draft.params))
        db.add(step)
        prepended.append(step)
    pipeline.updated_at = utc_now()
    db.commit()
    return _pipeline_to_out(pipeline, prepended + steps)


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
    current_column_types = {column_name: profile.inferred_type for column_name, profile in profiles_by_name.items()}
    analysis = db.get(AnalysisRun, pipeline.analysis_run_id) if pipeline.analysis_run_id else None
    source_id = (analysis.single_dataset_file_id if pipeline.mode == "single" else analysis.train_dataset_file_id) if analysis else None
    dataset = db.get(DatasetFile, source_id) if source_id else _latest_dataset(db, pipeline.project_id, "single" if pipeline.mode == "single" else "train")
    if dataset:
        current_column_types = {**{column: "unknown" for column in _json_loads(dataset.columns_json, [])}, **current_column_types}
    test_dataset = db.get(DatasetFile, analysis.test_dataset_file_id) if analysis and analysis.test_dataset_file_id else None
    test_columns = _json_loads(test_dataset.columns_json, []) if test_dataset else []

    issues: list[PipelineValidationIssue] = []
    if not steps:
        issues.append(PipelineValidationIssue(severity="warning", message="Pipeline has no steps."))
    for step in steps:
        if not step.enabled:
            continue
        if pipeline.mode == "train_test" and analysis and test_dataset:
            spec = PipelineStepSpec(step.id, step.order_index, step.enabled, step.operation_type, _json_loads(step.columns_json, []), _json_loads(step.params_json, {}))
            try:
                prepare_train_test_step(spec, list(current_column_types), test_columns, analysis.target_column)
            except TransformationError as exc:
                issues.append(PipelineValidationIssue(severity="error", step_id=step.id, operation_type=step.operation_type, message=str(exc)))
        step_issues = _validate_step_against_metadata(step, metadata_by_type, current_column_types)
        issues.extend(step_issues)
        if not any(issue.severity == "error" for issue in step_issues):
            current_column_types = _apply_step_column_state(step, current_column_types)

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
        params_json=json.dumps(
            {
                **suggestion.params,
                "__dataprep_source": {
                    "type": "issue",
                    "issue_id": issue.id,
                    "title": issue.title,
                    "category": issue.category,
                    "reason": suggestion.reason,
                },
            }
        ),
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
                pipeline_name=pipeline.name,
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
                analysis_options=_json_loads(analysis.options_json, None) if analysis else None,
            )
        else:
            train_dataset = db.get(DatasetFile, analysis.train_dataset_file_id) if analysis and analysis.train_dataset_file_id else _latest_dataset(db, pipeline.project_id, "train")
            test_dataset = db.get(DatasetFile, analysis.test_dataset_file_id) if analysis and analysis.test_dataset_file_id else _latest_dataset(db, pipeline.project_id, "test")
            if train_dataset is None or test_dataset is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline project must have train and test datasets")
            train_df = read_csv_file(train_dataset.storage_path)
            test_df = read_csv_file(test_dataset.storage_path)
            before_summary = {"train": summarize_dataframe(train_df), "test": summarize_dataframe(test_df)}
            result = apply_pipeline_train_test(train_df, test_df, steps, target_column)
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
                pipeline_name=pipeline.name,
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
                analysis_options=_json_loads(analysis.options_json, None) if analysis else None,
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
