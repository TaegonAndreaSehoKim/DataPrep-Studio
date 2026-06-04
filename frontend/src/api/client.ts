import type {
  AnalysisOverview,
  AnalysisPreprocessingRecommendations,
  AnalysisCharts,
  AnalysisRun,
  ColumnType,
  ColumnProfile,
  Dashboard,
  DatasetConfig,
  DatasetFile,
  DatasetPreview,
  DatasetSetupSuggestion,
  DatasetUploadResponse,
  Issue,
  OperationMetadata,
  Pipeline,
  PipelineValidation,
  PipelineRun,
  PipelineStep,
  PreviewResult,
  Project,
  SuggestedPipelineStep
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers
    },
    ...options
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  health: () => request<{ status: string; app: string }>("/health"),
  dashboard: () => request<Dashboard>("/dashboard"),
  listProjects: () => request<Project[]>("/projects"),
  getProject: (projectId: number) => request<Project>(`/projects/${projectId}`),
  createProject: (payload: { name: string; description?: string }) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteProject: (projectId: number) =>
    request<void>(`/projects/${projectId}`, {
      method: "DELETE"
    }),
  listProjectDatasets: (projectId: number) => request<DatasetFile[]>(`/projects/${projectId}/datasets`),
  getDatasetSetupSuggestions: (datasetId: number) => request<DatasetSetupSuggestion>(`/datasets/${datasetId}/setup-suggestions`),
  listDatasetConfigs: (projectId: number) => request<DatasetConfig[]>(`/projects/${projectId}/dataset-configs`),
  createDatasetConfig: (
    projectId: number,
    payload: {
      name: string;
      dataset_file_id?: number | null;
      target_column?: string | null;
      problem_type: DatasetConfig["problem_type"];
      mode: DatasetConfig["mode"];
      column_type_overrides?: Record<string, ColumnType>;
      missing_value_tokens?: string[];
      ignored_columns?: string[];
    }
  ) =>
    request<DatasetConfig>(`/projects/${projectId}/dataset-configs`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateDatasetConfig: (
    configId: number,
    payload: Partial<{
      name: string;
      dataset_file_id: number | null;
      target_column: string | null;
      problem_type: DatasetConfig["problem_type"];
      mode: DatasetConfig["mode"];
      column_type_overrides: Record<string, ColumnType>;
      missing_value_tokens: string[];
      ignored_columns: string[];
    }>
  ) =>
    request<DatasetConfig>(`/dataset-configs/${configId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteDatasetConfig: (configId: number) =>
    request<void>(`/dataset-configs/${configId}`, {
      method: "DELETE"
    }),
  previewDataset: (datasetId: number, limit = 20) => request<DatasetPreview>(`/datasets/${datasetId}/preview?limit=${limit}`),
  listProjectAnalysis: (projectId: number) => request<AnalysisRun[]>(`/projects/${projectId}/analysis`),
  runAnalysis: (
    projectId: number,
    payload: {
      target_column: string | null;
      problem_type: AnalysisRun["problem_type"];
      mode: Pipeline["mode"];
      dataset_config_id?: number | null;
      column_type_overrides?: Record<string, ColumnType>;
      missing_value_tokens?: string[];
      ignored_columns?: string[];
    }
  ) =>
    request<AnalysisRun>(`/projects/${projectId}/analysis/run`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getAnalysisOverview: (analysisId: number) => request<AnalysisOverview>(`/analysis/${analysisId}/overview`),
  getAnalysisPreprocessingRecommendations: (analysisId: number) =>
    request<AnalysisPreprocessingRecommendations>(`/analysis/${analysisId}/preprocessing-recommendations`),
  getAnalysisCharts: (analysisId: number) => request<AnalysisCharts>(`/analysis/${analysisId}/charts`),
  analysisReportUrl: (analysisId: number) => `${API_BASE_URL}/analysis/${analysisId}/download/report`,
  getAnalysisReport: async (analysisId: number) => {
    const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/download/report`);
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed with status ${response.status}`);
    }
    return response.text();
  },
  listColumns: (analysisId: number) => request<ColumnProfile[]>(`/analysis/${analysisId}/columns`),
  listIssues: (analysisId: number) => request<Issue[]>(`/analysis/${analysisId}/issues`),
  getIssueSuggestedStep: (issueId: number) => request<SuggestedPipelineStep>(`/issues/${issueId}/suggested-step`),
  getTrainTestComparison: (analysisId: number) => request<Record<string, unknown>>(`/analysis/${analysisId}/train-test-comparison`),
  listPipelines: (projectId: number) => request<Pipeline[]>(`/projects/${projectId}/pipelines`),
  createPipeline: (projectId: number, payload: { name: string; description?: string; analysis_run_id?: number | null; mode: Pipeline["mode"] }) =>
    request<Pipeline>(`/projects/${projectId}/pipelines`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createSuggestedPipeline: (projectId: number, analysisId: number, payload: { name?: string } = {}) =>
    request<Pipeline>(`/projects/${projectId}/pipelines/from-analysis/${analysisId}`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createPipelineFromConfig: (
    projectId: number,
    payload: { name?: string; analysis_run_id?: number | null; config: Record<string, unknown> }
  ) =>
    request<Pipeline>(`/projects/${projectId}/pipelines/from-config`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getPipeline: (pipelineId: number) => request<Pipeline>(`/pipelines/${pipelineId}`),
  validatePipeline: (pipelineId: number) =>
    request<PipelineValidation>(`/pipelines/${pipelineId}/validate`, {
      method: "POST",
      body: JSON.stringify({})
    }),
  listOperations: () => request<OperationMetadata[]>("/pipeline/operations"),
  createPipelineStep: (pipelineId: number, payload: { operation_type: string; columns: string[]; params: Record<string, unknown>; enabled?: boolean }) =>
    request<PipelineStep>(`/pipelines/${pipelineId}/steps`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createPipelineStepFromIssue: (pipelineId: number, issueId: number) =>
    request<PipelineStep>(`/pipelines/${pipelineId}/steps/from-issue/${issueId}`, {
      method: "POST",
      body: JSON.stringify({})
    }),
  updatePipelineStep: (pipelineId: number, stepId: number, payload: Partial<{ operation_type: string; columns: string[]; params: Record<string, unknown>; enabled: boolean }>) =>
    request<PipelineStep>(`/pipelines/${pipelineId}/steps/${stepId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deletePipelineStep: (pipelineId: number, stepId: number) =>
    request<void>(`/pipelines/${pipelineId}/steps/${stepId}`, { method: "DELETE" }),
  reorderPipelineSteps: (pipelineId: number, stepIds: number[]) =>
    request<Pipeline>(`/pipelines/${pipelineId}/steps/reorder`, {
      method: "POST",
      body: JSON.stringify({ step_ids: stepIds })
    }),
  togglePipelineStep: (pipelineId: number, stepId: number) =>
    request<PipelineStep>(`/pipelines/${pipelineId}/steps/${stepId}/toggle`, { method: "POST" }),
  previewPipeline: (pipelineId: number, limit = 20) =>
    request<PreviewResult>(`/pipelines/${pipelineId}/preview`, {
      method: "POST",
      body: JSON.stringify({ limit })
    }),
  previewPipelineCharts: (pipelineId: number, limit = 20) =>
    request<AnalysisCharts>(`/pipelines/${pipelineId}/preview/charts`, {
      method: "POST",
      body: JSON.stringify({ limit })
    }),
  getColumnCharts: (analysisId: number, columnName: string) =>
    request<AnalysisCharts>(`/analysis/${analysisId}/columns/${encodeURIComponent(columnName)}/charts`),
  applyPipeline: (pipelineId: number) =>
    request<PipelineRun>(`/pipelines/${pipelineId}/apply`, {
      method: "POST",
      body: JSON.stringify({})
    }),
  getPipelineRun: (pipelineRunId: number) => request<PipelineRun>(`/pipeline-runs/${pipelineRunId}`),
  listProjectPipelineRuns: (projectId: number) => request<PipelineRun[]>(`/projects/${projectId}/pipeline-runs`),
  downloadUrl: (pipelineRunId: number, artifact: "config" | "report" | "code" | "cleaned-single" | "cleaned-train" | "cleaned-test") =>
    `${API_BASE_URL}/pipeline-runs/${pipelineRunId}/download/${artifact}`,
  uploadDataset: async (payload: { projectId: number; role: DatasetFile["role"]; file: File }) => {
    const formData = new FormData();
    formData.append("role", payload.role);
    formData.append("file", payload.file);

    const response = await fetch(`${API_BASE_URL}/projects/${payload.projectId}/datasets/upload`, {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed with status ${response.status}`);
    }

    return (await response.json()) as DatasetUploadResponse;
  }
};
