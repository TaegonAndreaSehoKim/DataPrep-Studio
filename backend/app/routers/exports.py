import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import PipelineRun, Project
from app.schemas import PipelineRunOut

router = APIRouter(tags=["exports"])


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _run_or_404(pipeline_run_id: int, db: Session) -> PipelineRun:
    run = db.get(PipelineRun, pipeline_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    return run


def _run_to_out(run: PipelineRun) -> PipelineRunOut:
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


def _download(run: PipelineRun, key: str) -> FileResponse:
    output_paths = _json_loads(run.output_paths_json, {})
    path_value = output_paths.get(key)
    if not path_value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested export artifact is not available")
    path = Path(path_value)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export artifact file not found")
    return FileResponse(path, filename=path.name)


@router.get("/pipeline-runs/{pipeline_run_id}", response_model=PipelineRunOut)
def get_pipeline_run(pipeline_run_id: int, db: Session = Depends(get_db)) -> PipelineRunOut:
    return _run_to_out(_run_or_404(pipeline_run_id, db))


@router.get("/projects/{project_id}/pipeline-runs", response_model=list[PipelineRunOut])
def list_project_pipeline_runs(project_id: int, db: Session = Depends(get_db)) -> list[PipelineRunOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.project_id == project_id)
        .order_by(PipelineRun.created_at.desc())
        .all()
    )
    return [_run_to_out(run) for run in runs]


@router.get("/pipeline-runs/{pipeline_run_id}/download/config")
def download_config(pipeline_run_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _download(_run_or_404(pipeline_run_id, db), "config")


@router.get("/pipeline-runs/{pipeline_run_id}/download/report")
def download_report(pipeline_run_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _download(_run_or_404(pipeline_run_id, db), "report")


@router.get("/pipeline-runs/{pipeline_run_id}/download/code")
def download_code(pipeline_run_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _download(_run_or_404(pipeline_run_id, db), "code")


@router.get("/pipeline-runs/{pipeline_run_id}/download/cleaned-single")
def download_cleaned_single(pipeline_run_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _download(_run_or_404(pipeline_run_id, db), "cleaned_single")


@router.get("/pipeline-runs/{pipeline_run_id}/download/cleaned-train")
def download_cleaned_train(pipeline_run_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _download(_run_or_404(pipeline_run_id, db), "cleaned_train")


@router.get("/pipeline-runs/{pipeline_run_id}/download/cleaned-test")
def download_cleaned_test(pipeline_run_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _download(_run_or_404(pipeline_run_id, db), "cleaned_test")
