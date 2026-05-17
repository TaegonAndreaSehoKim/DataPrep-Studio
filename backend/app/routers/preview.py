import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.models import AnalysisRun, DatasetFile, Pipeline, PipelineStep
from app.schemas import AnalysisChartsOut, PreviewOut, PreviewRequest
from app.services.chart_builder import build_preview_charts
from app.services.csv_loader import CsvValidationError, read_csv_file
from app.services.pipeline_engine import PipelineStepSpec, preview_single, preview_train_test
from app.services.transformations import TransformationError

router = APIRouter(tags=["preview"])


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _steps_for_pipeline(db: Session, pipeline_id: int) -> list[PipelineStepSpec]:
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


def _latest_dataset(db: Session, project_id: int, role: str) -> DatasetFile | None:
    return db.scalars(
        select(DatasetFile)
        .where(DatasetFile.project_id == project_id, DatasetFile.role == role)
        .order_by(DatasetFile.created_at.desc())
        .limit(1)
    ).first()


def _analysis_or_none(db: Session, analysis_id: int | None) -> AnalysisRun | None:
    if analysis_id is None:
        return None
    return db.get(AnalysisRun, analysis_id)


@router.post("/pipelines/{pipeline_id}/preview", response_model=PreviewOut)
def preview_pipeline(pipeline_id: int, payload: PreviewRequest | None = None, db: Session = Depends(get_db)) -> PreviewOut:
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    settings = get_settings()
    limit = max(1, min(payload.limit if payload and payload.limit else settings.max_preview_rows, settings.max_preview_rows))
    analysis = _analysis_or_none(db, pipeline.analysis_run_id)
    target_column = analysis.target_column if analysis else None
    problem_type = analysis.problem_type if analysis else "unknown"
    steps = _steps_for_pipeline(db, pipeline_id)

    try:
        if pipeline.mode == "single":
            dataset = db.get(DatasetFile, analysis.single_dataset_file_id) if analysis and analysis.single_dataset_file_id else _latest_dataset(db, pipeline.project_id, "single")
            if dataset is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline project does not have a single dataset")
            df = read_csv_file(dataset.storage_path)
            return PreviewOut(**preview_single(df, steps, target_column, problem_type, limit))

        train_dataset = db.get(DatasetFile, analysis.train_dataset_file_id) if analysis and analysis.train_dataset_file_id else _latest_dataset(db, pipeline.project_id, "train")
        test_dataset = db.get(DatasetFile, analysis.test_dataset_file_id) if analysis and analysis.test_dataset_file_id else _latest_dataset(db, pipeline.project_id, "test")
        if train_dataset is None or test_dataset is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline project must have train and test datasets")
        train_df = read_csv_file(train_dataset.storage_path)
        test_df = read_csv_file(test_dataset.storage_path)
        return PreviewOut(**preview_train_test(train_df, test_df, steps, target_column, problem_type, limit))
    except CsvValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TransformationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _chart_summary(summary: dict[str, object]) -> dict[str, object]:
    train_summary = summary.get("train")
    if isinstance(train_summary, dict):
        return train_summary
    return summary


@router.post("/pipelines/{pipeline_id}/preview/charts", response_model=AnalysisChartsOut)
def preview_pipeline_charts(pipeline_id: int, payload: PreviewRequest | None = None, db: Session = Depends(get_db)) -> AnalysisChartsOut:
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    preview = preview_pipeline(pipeline_id, payload, db)
    analysis_id = pipeline.analysis_run_id or 0
    return build_preview_charts(analysis_id, _chart_summary(preview.before_summary), _chart_summary(preview.after_summary))
