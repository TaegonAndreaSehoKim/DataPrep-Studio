import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import AnalysisRun, DatasetFile, Pipeline, PipelineRun, Project
from app.schemas import AnalysisRunOut, DashboardOut, PipelineRunOut, ProjectOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _analysis_to_out(analysis: AnalysisRun) -> AnalysisRunOut:
    return AnalysisRunOut(
        id=analysis.id,
        project_id=analysis.project_id,
        target_column=analysis.target_column,
        problem_type=analysis.problem_type,  # type: ignore[arg-type]
        readiness_score=analysis.readiness_score,
        score_breakdown=_json_loads(analysis.score_breakdown_json, {}),
        status=analysis.status,  # type: ignore[arg-type]
        created_at=analysis.created_at,
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


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)) -> DashboardOut:
    project_count = db.scalar(select(func.count(Project.id))) or 0
    dataset_count = db.scalar(select(func.count(DatasetFile.id))) or 0
    analysis_count = db.scalar(select(func.count(AnalysisRun.id))) or 0
    pipeline_count = db.scalar(select(func.count(Pipeline.id))) or 0
    recent_projects = list(db.scalars(select(Project).order_by(Project.created_at.desc()).limit(5)).all())
    recent_analysis_runs = list(db.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(5)).all())
    recent_pipeline_runs = list(db.scalars(select(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(5)).all())

    return DashboardOut(
        project_count=project_count,
        dataset_count=dataset_count,
        analysis_count=analysis_count,
        pipeline_count=pipeline_count,
        recent_projects=[ProjectOut.model_validate(project) for project in recent_projects],
        recent_analysis_runs=[_analysis_to_out(run) for run in recent_analysis_runs],
        recent_pipeline_runs=[_pipeline_run_to_out(run) for run in recent_pipeline_runs],
    )
