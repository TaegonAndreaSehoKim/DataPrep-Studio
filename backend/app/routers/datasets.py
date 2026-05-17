import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.models import DatasetConfig, DatasetFile, Project, utc_now
from app.schemas import (
    DatasetConfigCreate,
    DatasetConfigOut,
    DatasetConfigUpdate,
    DatasetFileOut,
    DatasetPreviewOut,
    DatasetSetupSuggestionOut,
    DatasetUploadResponse,
)
from app.services.csv_loader import CsvValidationError, load_csv_upload, read_csv_file
from app.services.setup_suggester import suggest_dataset_setup

router = APIRouter(tags=["datasets"])


ALLOWED_ROLES = {"single", "train", "test"}


def _json_loads(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _dataset_to_out(dataset: DatasetFile) -> DatasetFileOut:
    return DatasetFileOut(
        id=dataset.id,
        project_id=dataset.project_id,
        role=dataset.role,  # type: ignore[arg-type]
        filename=dataset.filename,
        storage_path=dataset.storage_path,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        columns=json.loads(dataset.columns_json),
        file_size_bytes=dataset.file_size_bytes,
        created_at=dataset.created_at,
    )


def _config_to_out(config: DatasetConfig) -> DatasetConfigOut:
    return DatasetConfigOut(
        id=config.id,
        project_id=config.project_id,
        dataset_file_id=config.dataset_file_id,
        name=config.name,
        target_column=config.target_column,
        problem_type=config.problem_type,  # type: ignore[arg-type]
        mode=config.mode,  # type: ignore[arg-type]
        column_type_overrides=_json_loads(config.column_type_overrides_json, {}),
        missing_value_tokens=_json_loads(config.missing_value_tokens_json, []),
        ignored_columns=_json_loads(config.ignored_columns_json, []),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _validate_dataset_reference(db: Session, project_id: int, dataset_file_id: int | None) -> None:
    if dataset_file_id is None:
        return
    dataset = db.get(DatasetFile, dataset_file_id)
    if dataset is None or dataset.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file does not belong to project")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def _unique_storage_path(upload_dir: str, project_id: int, role: str, filename: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    safe_name = _safe_filename(filename)
    return Path(upload_dir) / f"project_{project_id}" / f"{role}_{timestamp}_{safe_name}"


@router.post("/projects/{project_id}/datasets/upload", response_model=DatasetUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id: int,
    role: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DatasetUploadResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be one of single, train, or test")

    settings = get_settings()
    try:
        filename = file.filename or ""
        raw_bytes = await file.read()
        from app.services.csv_loader import validate_csv_filename

        validate_csv_filename(filename, settings.allowed_extensions)
        loaded = load_csv_upload(raw_bytes, settings.max_upload_mb)
    except CsvValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    storage_path = _unique_storage_path(settings.upload_dir, project_id, role, filename)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(loaded.raw_bytes)

    dataset = DatasetFile(
        project_id=project_id,
        role=role,
        filename=filename,
        storage_path=str(storage_path),
        row_count=int(len(loaded.dataframe)),
        column_count=int(len(loaded.dataframe.columns)),
        columns_json=json.dumps([str(column) for column in loaded.dataframe.columns]),
        file_size_bytes=loaded.file_size_bytes,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return DatasetUploadResponse(dataset=_dataset_to_out(dataset))


@router.post("/projects/{project_id}/dataset-configs", response_model=DatasetConfigOut, status_code=status.HTTP_201_CREATED)
def create_dataset_config(project_id: int, payload: DatasetConfigCreate, db: Session = Depends(get_db)) -> DatasetConfigOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    _validate_dataset_reference(db, project_id, payload.dataset_file_id)

    config = DatasetConfig(
        project_id=project_id,
        dataset_file_id=payload.dataset_file_id,
        name=payload.name,
        target_column=payload.target_column,
        problem_type=payload.problem_type,
        mode=payload.mode,
        column_type_overrides_json=json.dumps(payload.column_type_overrides),
        missing_value_tokens_json=json.dumps(payload.missing_value_tokens),
        ignored_columns_json=json.dumps(payload.ignored_columns),
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return _config_to_out(config)


@router.get("/projects/{project_id}/dataset-configs", response_model=list[DatasetConfigOut])
def list_dataset_configs(project_id: int, db: Session = Depends(get_db)) -> list[DatasetConfigOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    configs = db.scalars(
        select(DatasetConfig).where(DatasetConfig.project_id == project_id).order_by(DatasetConfig.updated_at.desc())
    ).all()
    return [_config_to_out(config) for config in configs]


@router.get("/dataset-configs/{config_id}", response_model=DatasetConfigOut)
def get_dataset_config(config_id: int, db: Session = Depends(get_db)) -> DatasetConfigOut:
    config = db.get(DatasetConfig, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset config not found")
    return _config_to_out(config)


@router.patch("/dataset-configs/{config_id}", response_model=DatasetConfigOut)
def update_dataset_config(config_id: int, payload: DatasetConfigUpdate, db: Session = Depends(get_db)) -> DatasetConfigOut:
    config = db.get(DatasetConfig, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset config not found")

    updates = payload.model_dump(exclude_unset=True)
    if "dataset_file_id" in updates:
        _validate_dataset_reference(db, config.project_id, updates["dataset_file_id"])
        config.dataset_file_id = updates["dataset_file_id"]
    if "name" in updates:
        config.name = updates["name"]
    if "target_column" in updates:
        config.target_column = updates["target_column"]
    if "problem_type" in updates:
        config.problem_type = updates["problem_type"]
    if "mode" in updates:
        config.mode = updates["mode"]
    if "column_type_overrides" in updates:
        config.column_type_overrides_json = json.dumps(updates["column_type_overrides"])
    if "missing_value_tokens" in updates:
        config.missing_value_tokens_json = json.dumps(updates["missing_value_tokens"])
    if "ignored_columns" in updates:
        config.ignored_columns_json = json.dumps(updates["ignored_columns"])
    config.updated_at = utc_now()
    db.commit()
    db.refresh(config)
    return _config_to_out(config)


@router.delete("/dataset-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset_config(config_id: int, db: Session = Depends(get_db)) -> None:
    config = db.get(DatasetConfig, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset config not found")
    db.delete(config)
    db.commit()


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetFileOut])
def list_project_datasets(project_id: int, db: Session = Depends(get_db)) -> list[DatasetFileOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    datasets = db.scalars(
        select(DatasetFile).where(DatasetFile.project_id == project_id).order_by(DatasetFile.created_at.desc())
    ).all()
    return [_dataset_to_out(dataset) for dataset in datasets]


@router.get("/datasets/{dataset_file_id}", response_model=DatasetFileOut)
def get_dataset(dataset_file_id: int, db: Session = Depends(get_db)) -> DatasetFileOut:
    dataset = db.get(DatasetFile, dataset_file_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")
    return _dataset_to_out(dataset)


@router.get("/datasets/{dataset_file_id}/preview", response_model=DatasetPreviewOut)
def preview_dataset(dataset_file_id: int, limit: int = 20, db: Session = Depends(get_db)) -> DatasetPreviewOut:
    dataset = db.get(DatasetFile, dataset_file_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")

    settings = get_settings()
    bounded_limit = max(1, min(limit, settings.max_preview_rows))

    try:
        dataframe = read_csv_file(dataset.storage_path)
    except CsvValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    preview = dataframe.head(bounded_limit).astype(object).where(dataframe.head(bounded_limit).notna(), None)
    return DatasetPreviewOut(
        dataset_file_id=dataset.id,
        columns=[str(column) for column in dataframe.columns],
        rows=preview.to_dict(orient="records"),
        row_count=int(len(dataframe)),
        limit=bounded_limit,
    )


@router.get("/datasets/{dataset_file_id}/setup-suggestions", response_model=DatasetSetupSuggestionOut)
def dataset_setup_suggestions(dataset_file_id: int, db: Session = Depends(get_db)) -> DatasetSetupSuggestionOut:
    dataset = db.get(DatasetFile, dataset_file_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")

    try:
        dataframe = read_csv_file(dataset.storage_path)
    except CsvValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return suggest_dataset_setup(dataset.id, dataframe)


@router.delete("/datasets/{dataset_file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_file_id: int, db: Session = Depends(get_db)) -> None:
    dataset = db.get(DatasetFile, dataset_file_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")

    storage_path = Path(dataset.storage_path)
    if storage_path.exists():
        storage_path.unlink()

    db.delete(dataset)
    db.commit()
