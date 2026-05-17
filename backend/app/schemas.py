from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProjectMode = Literal["single", "train_test"]
ProblemType = Literal["classification", "regression", "unknown"]
ColumnType = Literal["numeric", "categorical", "boolean", "datetime", "text", "unknown"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetFileOut(BaseModel):
    id: int
    project_id: int
    role: Literal["single", "train", "test"]
    filename: str
    storage_path: str
    row_count: int
    column_count: int
    columns: list[str]
    file_size_bytes: int
    created_at: datetime


class DatasetUploadResponse(BaseModel):
    dataset: DatasetFileOut


class DatasetPreviewOut(BaseModel):
    dataset_file_id: int
    columns: list[str]
    rows: list[dict[str, object]]
    row_count: int
    limit: int


class TargetCandidateOut(BaseModel):
    column_name: str
    score: float
    inferred_type: ColumnType
    unique_count: int
    reason: str


class DatasetSetupSuggestionOut(BaseModel):
    dataset_file_id: int
    recommended_target_column: str | None
    recommended_problem_type: ProblemType
    target_candidates: list[TargetCandidateOut]
    missing_value_tokens: list[str]
    column_type_overrides: dict[str, ColumnType]
    ignored_columns: list[str]
    notes: list[str] = Field(default_factory=list)


class DatasetConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dataset_file_id: int | None = None
    target_column: str | None = None
    problem_type: ProblemType = "unknown"
    mode: ProjectMode = "single"
    column_type_overrides: dict[str, ColumnType] = Field(default_factory=dict)
    missing_value_tokens: list[str] = Field(default_factory=list)
    ignored_columns: list[str] = Field(default_factory=list)


class DatasetConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dataset_file_id: int | None = None
    target_column: str | None = None
    problem_type: ProblemType | None = None
    mode: ProjectMode | None = None
    column_type_overrides: dict[str, ColumnType] | None = None
    missing_value_tokens: list[str] | None = None
    ignored_columns: list[str] | None = None


class DatasetConfigOut(BaseModel):
    id: int
    project_id: int
    dataset_file_id: int | None
    name: str
    target_column: str | None
    problem_type: ProblemType
    mode: ProjectMode
    column_type_overrides: dict[str, ColumnType]
    missing_value_tokens: list[str]
    ignored_columns: list[str]
    created_at: datetime
    updated_at: datetime


class AnalysisRunCreate(BaseModel):
    dataset_config_id: int | None = None
    target_column: str | None = None
    problem_type: ProblemType = "unknown"
    mode: ProjectMode = "single"
    column_type_overrides: dict[str, ColumnType] = Field(default_factory=dict)
    missing_value_tokens: list[str] = Field(default_factory=list)
    ignored_columns: list[str] = Field(default_factory=list)


class AnalysisRunOut(BaseModel):
    id: int
    project_id: int
    target_column: str | None
    problem_type: ProblemType
    readiness_score: float
    score_breakdown: dict[str, float | int | str]
    status: Literal["completed", "error"]
    created_at: datetime


class ReadinessScoreOut(BaseModel):
    score: float
    breakdown: dict[str, float | int | str]


class ColumnProfileOut(BaseModel):
    id: int
    analysis_run_id: int
    dataset_role: Literal["single", "train", "test"]
    column_name: str
    inferred_type: Literal["numeric", "categorical", "boolean", "datetime", "text", "unknown"]
    missing_count: int
    missing_rate: float
    unique_count: int
    cardinality_ratio: float
    summary: dict[str, object]
    warnings: list[str]


class IssueOut(BaseModel):
    id: int
    analysis_run_id: int
    severity: Literal["critical", "warning", "info"]
    category: str
    title: str
    explanation: str
    affected_columns: list[str]
    suggested_actions: list[str]
    created_at: datetime


class AnalysisOverviewOut(BaseModel):
    analysis_run: AnalysisRunOut
    row_count: int | None = None
    column_count: int | None = None
    issue_counts: dict[str, int]
    column_type_counts: dict[str, int]
    target_summary: dict[str, object] | None = None


class ChartData(BaseModel):
    chart_type: Literal["bar", "horizontal_bar", "summary"]
    title: str
    description: str | None = None
    data: list[dict[str, str | int | float | None]]


class AnalysisChartsOut(BaseModel):
    analysis_id: int
    charts: dict[str, ChartData]


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    analysis_run_id: int | None = None
    mode: ProjectMode = "single"


class SuggestedPipelineCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class PipelineStepCreate(BaseModel):
    operation_type: str = Field(min_length=1, max_length=80)
    columns: list[str] = Field(default_factory=list)
    params: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True


class PipelineStepUpdate(BaseModel):
    operation_type: str | None = Field(default=None, min_length=1, max_length=80)
    columns: list[str] | None = None
    params: dict[str, object] | None = None
    enabled: bool | None = None


class PipelineStepReorder(BaseModel):
    step_ids: list[int] = Field(min_length=1)


class PipelineStepOut(BaseModel):
    id: int
    pipeline_id: int
    order_index: int
    enabled: bool
    operation_type: str
    columns: list[str]
    params: dict[str, object]
    created_at: datetime
    updated_at: datetime


class SuggestedPipelineStepOut(BaseModel):
    operation_type: str
    columns: list[str]
    params: dict[str, object] = Field(default_factory=dict)
    reason: str


class PipelineValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    step_id: int | None = None
    operation_type: str | None = None
    message: str


class PipelineValidationOut(BaseModel):
    valid: bool
    issues: list[PipelineValidationIssue] = Field(default_factory=list)


class PipelineOut(BaseModel):
    id: int
    project_id: int
    analysis_run_id: int | None
    name: str
    description: str | None
    mode: ProjectMode
    status: Literal["draft", "applied"]
    steps: list[PipelineStepOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PreviewRequest(BaseModel):
    limit: int | None = None


class ColumnDiffOut(BaseModel):
    column_name: str
    status: Literal["added", "removed", "changed", "unchanged"]
    before_missing_count: int | None = None
    after_missing_count: int | None = None
    before_non_null_count: int | None = None
    after_non_null_count: int | None = None
    changed_sample_count: int | None = None
    before_dtype: str | None = None
    after_dtype: str | None = None


class PreviewOut(BaseModel):
    before_summary: dict[str, object]
    after_summary: dict[str, object]
    affected_columns: list[str]
    before_sample_rows: list[dict[str, object]] = Field(default_factory=list)
    sample_rows: list[dict[str, object]]
    column_diffs: list[ColumnDiffOut] = Field(default_factory=list)
    step_effects: list[dict[str, object]]
    warnings: list[str]
    fitted_params: list[dict[str, object]] = Field(default_factory=list)


class PipelineRunOut(BaseModel):
    id: int
    pipeline_id: int
    project_id: int
    status: Literal["completed", "error"]
    before_summary: dict[str, object]
    after_summary: dict[str, object]
    output_paths: dict[str, str]
    report_path: str | None
    config_path: str | None
    code_path: str | None
    created_at: datetime


class ExportOut(BaseModel):
    pipeline_run: PipelineRunOut
    download_links: dict[str, str]


class OperationParamMetadata(BaseModel):
    name: str
    type: Literal["string", "number", "boolean", "select", "list", "object"]
    required: bool = False
    default: object | None = None
    options: list[str] | None = None
    description: str


class OperationMetadata(BaseModel):
    operation_type: str
    label: str
    description: str
    supported_column_types: list[str]
    params: list[OperationParamMetadata]


class DashboardOut(BaseModel):
    project_count: int
    dataset_count: int
    analysis_count: int
    pipeline_count: int
    recent_projects: list[ProjectOut]
    recent_analysis_runs: list[AnalysisRunOut]
    recent_pipeline_runs: list[PipelineRunOut]
