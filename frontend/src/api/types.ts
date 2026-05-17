export interface Project {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface DatasetFile {
  id: number;
  project_id: number;
  role: "single" | "train" | "test";
  filename: string;
  storage_path: string;
  row_count: number;
  column_count: number;
  columns: string[];
  file_size_bytes: number;
  created_at: string;
}

export interface DatasetUploadResponse {
  dataset: DatasetFile;
}

export interface DatasetPreview {
  dataset_file_id: number;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  limit: number;
}

export interface TargetCandidate {
  column_name: string;
  score: number;
  inferred_type: ColumnType;
  unique_count: number;
  reason: string;
}

export interface DatasetSetupSuggestion {
  dataset_file_id: number;
  recommended_target_column: string | null;
  recommended_problem_type: AnalysisRun["problem_type"];
  target_candidates: TargetCandidate[];
  missing_value_tokens: string[];
  column_type_overrides: Record<string, ColumnType>;
  ignored_columns: string[];
  notes: string[];
}

export interface AnalysisRun {
  id: number;
  project_id: number;
  target_column: string | null;
  problem_type: "classification" | "regression" | "unknown";
  readiness_score: number;
  score_breakdown: Record<string, number | string>;
  status: "completed" | "error";
  created_at: string;
}

export interface AnalysisOverview {
  analysis_run: AnalysisRun;
  row_count: number | null;
  column_count: number | null;
  issue_counts: Record<string, number>;
  column_type_counts: Record<string, number>;
  target_summary: Record<string, unknown> | null;
}

export interface ColumnProfile {
  id: number;
  analysis_run_id: number;
  dataset_role: "single" | "train" | "test";
  column_name: string;
  inferred_type: "numeric" | "categorical" | "boolean" | "datetime" | "text" | "unknown";
  missing_count: number;
  missing_rate: number;
  unique_count: number;
  cardinality_ratio: number;
  summary: Record<string, unknown>;
  warnings: string[];
}

export type ColumnType = ColumnProfile["inferred_type"];

export interface DatasetConfig {
  id: number;
  project_id: number;
  dataset_file_id: number | null;
  name: string;
  target_column: string | null;
  problem_type: AnalysisRun["problem_type"];
  mode: Pipeline["mode"];
  column_type_overrides: Record<string, ColumnType>;
  missing_value_tokens: string[];
  ignored_columns: string[];
  created_at: string;
  updated_at: string;
}

export interface Issue {
  id: number;
  analysis_run_id: number;
  severity: "critical" | "warning" | "info";
  category: string;
  title: string;
  explanation: string;
  affected_columns: string[];
  suggested_actions: string[];
  created_at: string;
}

export interface PipelineStep {
  id: number;
  pipeline_id: number;
  order_index: number;
  enabled: boolean;
  operation_type: string;
  columns: string[];
  params: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SuggestedPipelineStep {
  operation_type: string;
  columns: string[];
  params: Record<string, unknown>;
  reason: string;
}

export interface PipelineValidationIssue {
  severity: "error" | "warning";
  step_id: number | null;
  operation_type: string | null;
  message: string;
}

export interface PipelineValidation {
  valid: boolean;
  issues: PipelineValidationIssue[];
}

export interface Pipeline {
  id: number;
  project_id: number;
  analysis_run_id: number | null;
  name: string;
  description: string | null;
  mode: "single" | "train_test";
  status: "draft" | "applied";
  steps: PipelineStep[];
  created_at: string;
  updated_at: string;
}

export interface PipelineRun {
  id: number;
  pipeline_id: number;
  project_id: number;
  status: "completed" | "error";
  before_summary: Record<string, unknown>;
  after_summary: Record<string, unknown>;
  output_paths: Record<string, string>;
  report_path: string | null;
  config_path: string | null;
  code_path: string | null;
  created_at: string;
}

export interface OperationParamMetadata {
  name: string;
  type: "string" | "number" | "boolean" | "select" | "list" | "object";
  required: boolean;
  default: unknown;
  options: string[] | null;
  description: string;
}

export interface OperationMetadata {
  operation_type: string;
  label: string;
  description: string;
  supported_column_types: string[];
  params: OperationParamMetadata[];
}

export interface ColumnDiff {
  column_name: string;
  status: "added" | "removed" | "changed" | "unchanged";
  before_missing_count: number | null;
  after_missing_count: number | null;
  before_non_null_count: number | null;
  after_non_null_count: number | null;
  changed_sample_count: number | null;
  before_dtype: string | null;
  after_dtype: string | null;
}

export interface PreviewResult {
  before_summary: Record<string, unknown>;
  after_summary: Record<string, unknown>;
  affected_columns: string[];
  before_sample_rows: Record<string, unknown>[];
  sample_rows: Record<string, unknown>[];
  column_diffs: ColumnDiff[];
  step_effects: Record<string, unknown>[];
  warnings: string[];
  fitted_params: Record<string, unknown>[];
}

export interface ChartData {
  chart_type: "bar" | "horizontal_bar" | "summary";
  title: string;
  description: string | null;
  data: Array<Record<string, string | number | null>>;
}

export interface AnalysisCharts {
  analysis_id: number;
  charts: Record<string, ChartData>;
}

export interface Dashboard {
  project_count: number;
  dataset_count: number;
  analysis_count: number;
  pipeline_count: number;
  recent_projects: Project[];
  recent_analysis_runs: AnalysisRun[];
  recent_pipeline_runs: PipelineRun[];
}
