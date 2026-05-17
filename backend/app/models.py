from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    dataset_files: Mapped[list["DatasetFile"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    dataset_configs: Mapped[list["DatasetConfig"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    pipelines: Mapped[list["Pipeline"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class DatasetFile(Base):
    __tablename__ = "dataset_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="dataset_files")


class DatasetConfig(Base):
    __tablename__ = "dataset_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    dataset_file_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_files.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    problem_type: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="single")
    column_type_overrides_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    missing_value_tokens_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ignored_columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="dataset_configs")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    single_dataset_file_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_files.id"), nullable=True)
    train_dataset_file_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_files.id"), nullable=True)
    test_dataset_file_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_files.id"), nullable=True)
    target_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    problem_type: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    readiness_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    score_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="analysis_runs")
    column_profiles: Mapped[list["ColumnProfile"]] = relationship(cascade="all, delete-orphan")
    issues: Mapped[list["Issue"]] = relationship(cascade="all, delete-orphan")


class ColumnProfile(Base):
    __tablename__ = "column_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False, index=True)
    dataset_role: Mapped[str] = mapped_column(String(20), nullable=False)
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    inferred_type: Mapped[str] = mapped_column(String(30), nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_rate: Mapped[float] = mapped_column(Float, nullable=False)
    unique_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cardinality_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    affected_columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    suggested_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    analysis_run_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="single")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="pipelines")
    steps: Mapped[list["PipelineStep"]] = relationship(back_populates="pipeline", cascade="all, delete-orphan")


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    operation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    pipeline: Mapped["Pipeline"] = relationship(back_populates="steps")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    before_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    after_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    output_paths_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    code_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TrainTestComparison(Base):
    __tablename__ = "train_test_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    drift_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
