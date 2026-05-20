import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.models import AnalysisRun, ColumnProfile, DatasetConfig, DatasetFile, Issue, Project, TrainTestComparison
from app.schemas import (
    AnalysisOverviewOut,
    AnalysisChartsOut,
    AnalysisPreprocessingRecommendationsOut,
    AnalysisRunCreate,
    AnalysisRunOut,
    ColumnProfileOut,
    IssueOut,
    ReadinessScoreOut,
)
from app.services.csv_loader import CsvValidationError, read_csv_file
from app.services.chart_builder import build_analysis_charts, build_column_charts
from app.services.analysis_report_generator import generate_analysis_report
from app.services.drift_detector import detect_train_test_drift
from app.services.issue_detector import detect_issues
from app.services.preprocessing_advisor import build_preprocessing_recommendations
from app.services.profiler import profile_dataframe
from app.services.readiness_score import calculate_readiness_score

router = APIRouter(tags=["analysis"])


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


def _column_to_out(profile: ColumnProfile) -> ColumnProfileOut:
    return ColumnProfileOut(
        id=profile.id,
        analysis_run_id=profile.analysis_run_id,
        dataset_role=profile.dataset_role,  # type: ignore[arg-type]
        column_name=profile.column_name,
        inferred_type=profile.inferred_type,  # type: ignore[arg-type]
        missing_count=profile.missing_count,
        missing_rate=profile.missing_rate,
        unique_count=profile.unique_count,
        cardinality_ratio=profile.cardinality_ratio,
        summary=_json_loads(profile.summary_json, {}),
        warnings=_json_loads(profile.warnings_json, []),
    )


def _issue_to_out(issue: Issue) -> IssueOut:
    return IssueOut(
        id=issue.id,
        analysis_run_id=issue.analysis_run_id,
        severity=issue.severity,  # type: ignore[arg-type]
        category=issue.category,
        title=issue.title,
        explanation=issue.explanation,
        affected_columns=_json_loads(issue.affected_columns_json, []),
        suggested_actions=_json_loads(issue.suggested_actions_json, []),
        created_at=issue.created_at,
    )


def _latest_dataset(db: Session, project_id: int, role: str) -> DatasetFile | None:
    return db.scalars(
        select(DatasetFile)
        .where(DatasetFile.project_id == project_id, DatasetFile.role == role)
        .order_by(DatasetFile.created_at.desc())
        .limit(1)
    ).first()


def _resolve_analysis_options(project_id: int, payload: AnalysisRunCreate, db: Session) -> dict[str, object]:
    config = None
    if payload.dataset_config_id is not None:
        config = db.get(DatasetConfig, payload.dataset_config_id)
        if config is None or config.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset config does not belong to project")

    fields_set = payload.model_fields_set
    column_type_overrides = _json_loads(config.column_type_overrides_json, {}) if config else {}
    column_type_overrides.update(payload.column_type_overrides)

    return {
        "dataset_config": config,
        "target_column": payload.target_column if "target_column" in fields_set or config is None else config.target_column,
        "problem_type": payload.problem_type if "problem_type" in fields_set or config is None else config.problem_type,
        "mode": payload.mode if "mode" in fields_set or config is None else config.mode,
        "column_type_overrides": column_type_overrides,
        "missing_value_tokens": payload.missing_value_tokens
        if "missing_value_tokens" in fields_set or config is None
        else _json_loads(config.missing_value_tokens_json, []),
        "ignored_columns": payload.ignored_columns
        if "ignored_columns" in fields_set or config is None
        else _json_loads(config.ignored_columns_json, []),
    }


def _single_dataset_for_options(db: Session, project_id: int, config: DatasetConfig | None) -> DatasetFile | None:
    if config and config.dataset_file_id is not None:
        dataset = db.get(DatasetFile, config.dataset_file_id)
        if dataset is None or dataset.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset config references a missing dataset")
        if dataset.role != "single":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset config must reference a single-role dataset")
        return dataset
    return _latest_dataset(db, project_id, "single")


def _drop_ignored_columns(dataframe, ignored_columns: list[str]):
    if not ignored_columns:
        return dataframe
    present = [column for column in ignored_columns if column in dataframe.columns]
    if not present:
        return dataframe
    return dataframe.drop(columns=present)


def _persist_profiles(db: Session, analysis_id: int, profiles) -> None:
    for profile in profiles:
        db.add(
            ColumnProfile(
                analysis_run_id=analysis_id,
                dataset_role=profile.dataset_role,
                column_name=profile.column_name,
                inferred_type=profile.inferred_type,
                missing_count=profile.missing_count,
                missing_rate=profile.missing_rate,
                unique_count=profile.unique_count,
                cardinality_ratio=profile.cardinality_ratio,
                summary_json=json.dumps(profile.summary, default=str),
                warnings_json=json.dumps(profile.warnings),
            )
        )


def _persist_issues(db: Session, analysis_id: int, issues) -> None:
    for issue in issues:
        db.add(
            Issue(
                analysis_run_id=analysis_id,
                severity=issue.severity,
                category=issue.category,
                title=issue.title,
                explanation=issue.explanation,
                affected_columns_json=json.dumps(issue.affected_columns),
                suggested_actions_json=json.dumps(issue.suggested_actions),
            )
        )


def _apply_missing_value_tokens(dataframe, tokens: list[str]):
    if not tokens:
        return dataframe
    cleaned = dataframe.copy()
    normalized_tokens = {str(token).strip() for token in tokens if str(token).strip()}
    if not normalized_tokens:
        return cleaned
    object_columns = cleaned.select_dtypes(include=["object", "string"]).columns
    for column in object_columns:
        stripped = cleaned[column].astype(str).str.strip()
        cleaned.loc[stripped.isin(normalized_tokens), column] = None
    return cleaned


@router.post("/projects/{project_id}/analysis/run", response_model=AnalysisRunOut, status_code=status.HTTP_201_CREATED)
def run_analysis(project_id: int, payload: AnalysisRunCreate, db: Session = Depends(get_db)) -> AnalysisRunOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    options = _resolve_analysis_options(project_id, payload, db)
    target_column = options["target_column"]
    problem_type = str(options["problem_type"])
    mode = str(options["mode"])
    column_type_overrides = options["column_type_overrides"]
    missing_value_tokens = options["missing_value_tokens"]
    ignored_columns = options["ignored_columns"]
    if not isinstance(target_column, str):
        target_column = None
    if not isinstance(column_type_overrides, dict):
        column_type_overrides = {}
    if not isinstance(missing_value_tokens, list):
        missing_value_tokens = []
    if not isinstance(ignored_columns, list):
        ignored_columns = []
    if target_column and target_column in ignored_columns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target column cannot be ignored")

    if mode == "single":
        dataset = _single_dataset_for_options(db, project_id, options["dataset_config"] if isinstance(options["dataset_config"], DatasetConfig) else None)
        if dataset is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project does not have a single dataset upload")

        try:
            dataframe = read_csv_file(dataset.storage_path)
        except CsvValidationError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        dataframe = _apply_missing_value_tokens(dataframe, missing_value_tokens)
        dataframe = _drop_ignored_columns(dataframe, ignored_columns)

        if target_column and target_column not in dataframe.columns:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target column does not exist in the dataset")

        profiles = profile_dataframe(
            dataframe,
            "single",
            target_column,
            problem_type,
            column_type_overrides,
        )
        issues = detect_issues(dataframe, profiles, target_column, problem_type)
        score, breakdown = calculate_readiness_score(issues, get_settings().default_readiness_score)

        analysis = AnalysisRun(
            project_id=project_id,
            single_dataset_file_id=dataset.id,
            target_column=target_column,
            problem_type=problem_type,
            readiness_score=score,
            score_breakdown_json=json.dumps(breakdown),
            status="completed",
        )
        db.add(analysis)
        db.flush()
        _persist_profiles(db, analysis.id, profiles)
        _persist_issues(db, analysis.id, issues)
        db.commit()
        db.refresh(analysis)
        return _analysis_to_out(analysis)

    train_dataset = _latest_dataset(db, project_id, "train")
    test_dataset = _latest_dataset(db, project_id, "test")
    if train_dataset is None or test_dataset is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project must have train and test dataset uploads")

    try:
        train_df = read_csv_file(train_dataset.storage_path)
        test_df = read_csv_file(test_dataset.storage_path)
    except CsvValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    train_df = _apply_missing_value_tokens(train_df, missing_value_tokens)
    test_df = _apply_missing_value_tokens(test_df, missing_value_tokens)
    train_df = _drop_ignored_columns(train_df, ignored_columns)
    test_df = _drop_ignored_columns(test_df, ignored_columns)

    if target_column and target_column not in train_df.columns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target column does not exist in the train dataset")
    if target_column and target_column not in test_df.columns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target column does not exist in the test dataset")

    train_profiles = profile_dataframe(
        train_df,
        "train",
        target_column,
        problem_type,
        column_type_overrides,
    )
    test_profiles = profile_dataframe(
        test_df,
        "test",
        target_column,
        problem_type,
        column_type_overrides,
    )
    issues = detect_issues(train_df, train_profiles, target_column, problem_type)
    drift = detect_train_test_drift(train_df, test_df, train_profiles, target_column)
    issues.extend(drift.issues)
    score, breakdown = calculate_readiness_score(issues, get_settings().default_readiness_score)

    analysis = AnalysisRun(
        project_id=project_id,
        train_dataset_file_id=train_dataset.id,
        test_dataset_file_id=test_dataset.id,
        target_column=target_column,
        problem_type=problem_type,
        readiness_score=score,
        score_breakdown_json=json.dumps(breakdown),
        status="completed",
    )
    db.add(analysis)
    db.flush()

    _persist_profiles(db, analysis.id, train_profiles)
    _persist_profiles(db, analysis.id, test_profiles)
    _persist_issues(db, analysis.id, issues)
    db.add(
        TrainTestComparison(
            analysis_run_id=analysis.id,
            project_id=project_id,
            drift_score=drift.drift_score,
            summary_json=json.dumps(drift.summary, default=str),
        )
    )

    db.commit()
    db.refresh(analysis)
    return _analysis_to_out(analysis)


@router.get("/analysis/{analysis_id}", response_model=AnalysisRunOut)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)) -> AnalysisRunOut:
    analysis = db.get(AnalysisRun, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return _analysis_to_out(analysis)


@router.get("/projects/{project_id}/analysis", response_model=list[AnalysisRunOut])
def list_project_analysis(project_id: int, db: Session = Depends(get_db)) -> list[AnalysisRunOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    runs = db.scalars(
        select(AnalysisRun).where(AnalysisRun.project_id == project_id).order_by(AnalysisRun.created_at.desc())
    ).all()
    return [_analysis_to_out(run) for run in runs]


@router.get("/analysis/{analysis_id}/overview", response_model=AnalysisOverviewOut)
def analysis_overview(analysis_id: int, db: Session = Depends(get_db)) -> AnalysisOverviewOut:
    analysis = db.get(AnalysisRun, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")

    profiles = db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id)).all()
    issues = db.scalars(select(Issue).where(Issue.analysis_run_id == analysis_id)).all()
    dataset = db.get(DatasetFile, analysis.single_dataset_file_id) if analysis.single_dataset_file_id else None
    train_dataset = db.get(DatasetFile, analysis.train_dataset_file_id) if analysis.train_dataset_file_id else None

    issue_counts: dict[str, int] = {}
    for issue in issues:
        issue_counts[issue.severity] = issue_counts.get(issue.severity, 0) + 1

    column_type_counts: dict[str, int] = {}
    target_summary = None
    for profile in profiles:
        column_type_counts[profile.inferred_type] = column_type_counts.get(profile.inferred_type, 0) + 1
        if profile.column_name == analysis.target_column:
            target_summary = _json_loads(profile.summary_json, {})

    return AnalysisOverviewOut(
        analysis_run=_analysis_to_out(analysis),
        row_count=dataset.row_count if dataset else (train_dataset.row_count if train_dataset else None),
        column_count=dataset.column_count if dataset else (train_dataset.column_count if train_dataset else None),
        issue_counts=issue_counts,
        column_type_counts=column_type_counts,
        target_summary=target_summary,
    )


@router.get("/analysis/{analysis_id}/charts", response_model=AnalysisChartsOut)
def analysis_charts(analysis_id: int, db: Session = Depends(get_db)) -> AnalysisChartsOut:
    if db.get(AnalysisRun, analysis_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    profiles = list(db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id)).all())
    issues = list(db.scalars(select(Issue).where(Issue.analysis_run_id == analysis_id)).all())
    comparison = db.scalars(select(TrainTestComparison).where(TrainTestComparison.analysis_run_id == analysis_id)).first()
    return build_analysis_charts(analysis_id, profiles, issues, comparison)


@router.get("/analysis/{analysis_id}/columns", response_model=list[ColumnProfileOut])
def list_columns(analysis_id: int, db: Session = Depends(get_db)) -> list[ColumnProfileOut]:
    if db.get(AnalysisRun, analysis_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    profiles = db.scalars(
        select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id).order_by(ColumnProfile.id)
    ).all()
    return [_column_to_out(profile) for profile in profiles]


@router.get("/analysis/{analysis_id}/columns/{column_name}", response_model=ColumnProfileOut)
def get_column(analysis_id: int, column_name: str, db: Session = Depends(get_db)) -> ColumnProfileOut:
    profile = db.scalars(
        select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id, ColumnProfile.column_name == column_name)
    ).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column profile not found")
    return _column_to_out(profile)


@router.get("/analysis/{analysis_id}/columns/{column_name}/charts", response_model=AnalysisChartsOut)
def get_column_charts(analysis_id: int, column_name: str, db: Session = Depends(get_db)) -> AnalysisChartsOut:
    profile = db.scalars(
        select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id, ColumnProfile.column_name == column_name)
    ).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column profile not found")
    return build_column_charts(analysis_id, profile)


@router.get("/analysis/{analysis_id}/issues", response_model=list[IssueOut])
def list_issues(analysis_id: int, db: Session = Depends(get_db)) -> list[IssueOut]:
    if db.get(AnalysisRun, analysis_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    issues = db.scalars(select(Issue).where(Issue.analysis_run_id == analysis_id).order_by(Issue.id)).all()
    return [_issue_to_out(issue) for issue in issues]


@router.get("/analysis/{analysis_id}/preprocessing-recommendations", response_model=AnalysisPreprocessingRecommendationsOut)
def get_preprocessing_recommendations(analysis_id: int, db: Session = Depends(get_db)) -> AnalysisPreprocessingRecommendationsOut:
    if db.get(AnalysisRun, analysis_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    profiles = list(db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id)).all())
    issues = list(db.scalars(select(Issue).where(Issue.analysis_run_id == analysis_id).order_by(Issue.id)).all())
    recommendations, notes = build_preprocessing_recommendations(analysis_id, issues, profiles)
    return AnalysisPreprocessingRecommendationsOut(analysis_id=analysis_id, recommendations=recommendations, notes=notes)


@router.get("/analysis/{analysis_id}/download/report")
def download_analysis_report(analysis_id: int, db: Session = Depends(get_db)) -> Response:
    analysis = db.get(AnalysisRun, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    project = db.get(Project, analysis.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    profiles = list(db.scalars(select(ColumnProfile).where(ColumnProfile.analysis_run_id == analysis_id)).all())
    issues = list(db.scalars(select(Issue).where(Issue.analysis_run_id == analysis_id).order_by(Issue.id)).all())
    comparison = db.scalars(select(TrainTestComparison).where(TrainTestComparison.analysis_run_id == analysis_id)).first()
    recommendations, notes = build_preprocessing_recommendations(analysis_id, issues, profiles)
    charts = build_analysis_charts(analysis_id, profiles, issues, comparison)

    report = generate_analysis_report(
        project=project,
        analysis=analysis,
        datasets={
            "single": db.get(DatasetFile, analysis.single_dataset_file_id) if analysis.single_dataset_file_id else None,
            "train": db.get(DatasetFile, analysis.train_dataset_file_id) if analysis.train_dataset_file_id else None,
            "test": db.get(DatasetFile, analysis.test_dataset_file_id) if analysis.test_dataset_file_id else None,
        },
        profiles=profiles,
        issues=issues,
        recommendations=AnalysisPreprocessingRecommendationsOut(
            analysis_id=analysis_id,
            recommendations=recommendations,
            notes=notes,
        ),
        charts=charts,
        comparison=comparison,
    )
    return Response(
        content=report,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="analysis_{analysis_id}_report.md"'},
    )


@router.get("/analysis/{analysis_id}/score", response_model=ReadinessScoreOut)
def get_score(analysis_id: int, db: Session = Depends(get_db)) -> ReadinessScoreOut:
    analysis = db.get(AnalysisRun, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return ReadinessScoreOut(score=analysis.readiness_score, breakdown=_json_loads(analysis.score_breakdown_json, {}))


@router.get("/analysis/{analysis_id}/train-test-comparison")
def get_train_test_comparison(analysis_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    comparison = db.scalars(select(TrainTestComparison).where(TrainTestComparison.analysis_run_id == analysis_id)).first()
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Train/test comparison not found")
    return {
        "id": comparison.id,
        "analysis_run_id": comparison.analysis_run_id,
        "project_id": comparison.project_id,
        "drift_score": comparison.drift_score,
        "summary": _json_loads(comparison.summary_json, {}),
        "created_at": comparison.created_at,
    }
