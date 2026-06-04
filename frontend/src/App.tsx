import { useCallback, useEffect, useState } from "react";
import { BarChart3, Columns3, FileUp, Home, ListChecks, PackageOpen, Play, SlidersHorizontal } from "lucide-react";

import { apiClient } from "./api/client";
import type { Dashboard, DatasetFile, SuggestedPipelineStep } from "./api/types";
import { Button } from "./components/Button";
import { ErrorState } from "./components/ErrorState";
import { LoadingState } from "./components/LoadingState";
import { AnalysisPage } from "./pages/AnalysisPage";
import { ColumnsPage } from "./pages/ColumnsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ExportPage } from "./pages/ExportPage";
import { IssuesPage } from "./pages/IssuesPage";
import { PipelineBuilderPage } from "./pages/PipelineBuilderPage";
import { PreviewPage } from "./pages/PreviewPage";
import { ProjectCreatePage } from "./pages/ProjectCreatePage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { ProjectListPage } from "./pages/ProjectListPage";
import { UploadPage } from "./pages/UploadPage";

type PageKey =
  | "dashboard"
  | "projects"
  | "create"
  | "project"
  | "upload"
  | "analysis"
  | "issues"
  | "columns"
  | "pipeline"
  | "preview"
  | "exports";

const navItems: { key: PageKey; label: string; icon: typeof Home }[] = [
  { key: "dashboard", label: "Dashboard", icon: Home },
  { key: "projects", label: "Projects", icon: ListChecks },
  { key: "upload", label: "Upload", icon: FileUp },
  { key: "analysis", label: "Analysis", icon: BarChart3 },
  { key: "issues", label: "Issues", icon: Play },
  { key: "columns", label: "Columns", icon: Columns3 },
  { key: "pipeline", label: "Pipeline", icon: SlidersHorizontal },
  { key: "preview", label: "Preview", icon: PackageOpen },
  { key: "exports", label: "Exports", icon: PackageOpen }
];

const workflowSteps: Array<{ key: PageKey; label: string; description: string }> = [
  { key: "project", label: "Project", description: "Choose a workspace" },
  { key: "upload", label: "Upload", description: "Load CSV data" },
  { key: "analysis", label: "Analyze", description: "Profile and score" },
  { key: "issues", label: "Review", description: "Inspect findings" },
  { key: "pipeline", label: "Pipeline", description: "Build fixes" },
  { key: "preview", label: "Preview", description: "Check effects" },
  { key: "exports", label: "Export", description: "Download outputs" }
];

export default function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<number | null>(null);
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const [selectedPipelineRunId, setSelectedPipelineRunId] = useState<number | null>(null);
  const [pendingStepDraft, setPendingStepDraft] = useState<SuggestedPipelineStep | null>(null);
  const [loadedDatasets, setLoadedDatasets] = useState<DatasetFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .dashboard()
      .then(setDashboard)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const chooseProject = useCallback((projectId: number, nextPage: PageKey = "project") => {
    setSelectedProjectId(projectId);
    setPage(nextPage);
  }, []);

  const refreshDashboard = useCallback(() => {
    apiClient.dashboard().then(setDashboard).catch((err: Error) => setError(err.message));
  }, []);

  const refreshLoadedDatasets = useCallback((projectId: number | null) => {
    if (!projectId) {
      setLoadedDatasets([]);
      return Promise.resolve();
    }
    return apiClient
      .listProjectDatasets(projectId)
      .then(setLoadedDatasets)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    refreshLoadedDatasets(selectedProjectId);
  }, [refreshLoadedDatasets, selectedProjectId]);

  const latestByRole = (role: DatasetFile["role"]) => loadedDatasets.find((dataset) => dataset.role === role) ?? null;

  const hasDataset = Boolean(latestByRole("single") || (latestByRole("train") && latestByRole("test")));
  const hasAnalysis = Boolean(selectedAnalysisId);
  const hasPipeline = Boolean(selectedPipelineId);
  const hasExport = Boolean(selectedPipelineRunId);
  const activeWorkflowIndex = Math.max(
    0,
    workflowSteps.findIndex((step) => step.key === page)
  );
  const nextAction = (() => {
    if (!selectedProjectId) {
      return "Create or select a project to start.";
    }
    if (!hasDataset) {
      return "Upload a single CSV or a train/test pair.";
    }
    if (!hasAnalysis) {
      return "Run analysis on the loaded data.";
    }
    if (!hasPipeline) {
      return "Review recommendations and build a preprocessing pipeline.";
    }
    if (!hasExport) {
      return "Preview the pipeline, then apply it to create exports.";
    }
    return "Exports are ready. Download the cleaned data and reproducible artifacts.";
  })();

  function workflowStatus(index: number, key: PageKey) {
    if (key === "project") {
      return selectedProjectId ? "complete" : index === activeWorkflowIndex ? "active" : "pending";
    }
    if (key === "upload") {
      return hasDataset ? "complete" : index === activeWorkflowIndex ? "active" : "pending";
    }
    if (key === "analysis" || key === "issues" || key === "columns") {
      return hasAnalysis ? "complete" : index === activeWorkflowIndex ? "active" : "pending";
    }
    if (key === "pipeline" || key === "preview") {
      return hasPipeline ? "complete" : index === activeWorkflowIndex ? "active" : "pending";
    }
    if (key === "exports") {
      return hasExport ? "complete" : index === activeWorkflowIndex ? "active" : "pending";
    }
    return index === activeWorkflowIndex ? "active" : "pending";
  }

  function renderPage() {
    if (loading) {
      return <LoadingState message="Connecting to backend" />;
    }

    if (error) {
      return <ErrorState message={error} />;
    }

    switch (page) {
      case "dashboard":
        return <DashboardPage dashboard={dashboard} onCreateProject={() => setPage("create")} onSelectProject={chooseProject} />;
      case "projects":
        return <ProjectListPage onCreateProject={() => setPage("create")} onSelectProject={chooseProject} />;
      case "create":
        return (
          <ProjectCreatePage
            onCreated={(project) => {
              refreshDashboard();
              chooseProject(project.id);
            }}
          />
        );
      case "project":
        return (
          <ProjectDetailPage
            projectId={selectedProjectId}
            onUpload={() => setPage("upload")}
            onAnalyze={(analysisId) => {
              setSelectedAnalysisId(analysisId);
              setPage("analysis");
            }}
            onPipeline={(pipelineId) => {
              setSelectedPipelineId(pipelineId);
              setPage("pipeline");
            }}
          />
        );
      case "upload":
        return (
          <UploadPage
            selectedProjectId={selectedProjectId}
            onUploaded={(projectId, dataset) => {
              setSelectedProjectId(projectId);
              setLoadedDatasets((current) => [dataset, ...current.filter((item) => item.id !== dataset.id)]);
              refreshDashboard();
            }}
            onAnalyzeReady={(projectId) => {
              setSelectedProjectId(projectId);
              setSelectedAnalysisId(null);
              setPage("analysis");
            }}
          />
        );
      case "analysis":
        return (
          <AnalysisPage
            projectId={selectedProjectId}
            analysisId={selectedAnalysisId}
            onAnalysisSelected={setSelectedAnalysisId}
            onOpenIssues={() => setPage("issues")}
            onOpenColumns={() => setPage("columns")}
            onBuildPipeline={(analysisId) => {
              setSelectedAnalysisId(analysisId);
              setPage("pipeline");
            }}
            onPipelineCreated={(pipelineId) => {
              setSelectedPipelineId(pipelineId);
              setPendingStepDraft(null);
              setPage("pipeline");
            }}
            onUseRecommendation={(analysisId, step) => {
              setSelectedAnalysisId(analysisId);
              setPendingStepDraft(step);
              setPage("pipeline");
            }}
          />
        );
      case "issues":
        return <IssuesPage analysisId={selectedAnalysisId} pipelineId={selectedPipelineId} />;
      case "columns":
        return <ColumnsPage analysisId={selectedAnalysisId} />;
      case "pipeline":
        return (
          <PipelineBuilderPage
            projectId={selectedProjectId}
            analysisId={selectedAnalysisId}
            pipelineId={selectedPipelineId}
            initialStepDraft={pendingStepDraft}
            onInitialStepDraftConsumed={() => setPendingStepDraft(null)}
            onPipelineSelected={setSelectedPipelineId}
            onPreview={(pipelineId) => {
              setSelectedPipelineId(pipelineId);
              setPage("preview");
            }}
            onApplied={(runId) => {
              setSelectedPipelineRunId(runId);
              setPage("exports");
            }}
          />
        );
      case "preview":
        return (
          <PreviewPage
            pipelineId={selectedPipelineId}
            onApplied={(runId) => {
              setSelectedPipelineRunId(runId);
              setPage("exports");
            }}
          />
        );
      case "exports":
        return <ExportPage projectId={selectedProjectId} pipelineRunId={selectedPipelineRunId} onRunSelected={setSelectedPipelineRunId} />;
      default:
        return <DashboardPage dashboard={dashboard} onCreateProject={() => setPage("create")} onSelectProject={chooseProject} />;
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">DS</span>
          <div>
            <strong>DataPrep Studio</strong>
            <span>ML preprocessing workbench</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.key} className={page === item.key ? "active" : ""} onClick={() => setPage(item.key)}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">Local MVP</p>
            <h1>Configurable preprocessing for tabular ML</h1>
          </div>
          <Button variant="secondary" onClick={() => setPage("create")}>
            New Project
          </Button>
        </header>
        <section className="workflow-panel" aria-label="Workflow progress">
          <div className="workflow-summary">
            <span className="field-label">Workflow</span>
            <strong>{nextAction}</strong>
          </div>
          <ol className="workflow-steps">
            {workflowSteps.map((step, index) => {
              const status = workflowStatus(index, step.key);
              const isNavigable =
                step.key === "project" ||
                step.key === "upload" ||
                (step.key === "analysis" && hasDataset) ||
                ((step.key === "issues" || step.key === "pipeline") && hasAnalysis) ||
                (step.key === "preview" && hasPipeline) ||
                (step.key === "exports" && hasExport);
              return (
                <li className={`workflow-step workflow-${status}`} key={step.key}>
                  <button type="button" disabled={!isNavigable} onClick={() => setPage(step.key)}>
                    <span>{index + 1}</span>
                    <strong>{step.label}</strong>
                    <small>{step.description}</small>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
        {selectedProjectId ? (
          <section className="loaded-data-bar">
            <div>
              <span className="field-label">Loaded Data</span>
              <strong>{latestByRole("single")?.filename ?? "No single dataset"}</strong>
              <small>
                {latestByRole("single")
                  ? `${latestByRole("single")?.row_count} rows / ${latestByRole("single")?.column_count} columns`
                  : "Upload a single CSV to run standard analysis."}
              </small>
            </div>
            <div>
              <span className="field-label">Train</span>
              <strong>{latestByRole("train")?.filename ?? "Not loaded"}</strong>
              <small>{latestByRole("train") ? `${latestByRole("train")?.row_count} rows` : "Optional train/test mode"}</small>
            </div>
            <div>
              <span className="field-label">Test</span>
              <strong>{latestByRole("test")?.filename ?? "Not loaded"}</strong>
              <small>{latestByRole("test") ? `${latestByRole("test")?.row_count} rows` : "Optional train/test mode"}</small>
            </div>
            <div className="toolbar no-margin">
              <Button variant="secondary" onClick={() => setPage("upload")}>
                Upload
              </Button>
              <Button disabled={!latestByRole("single") && !(latestByRole("train") && latestByRole("test"))} onClick={() => setPage("analysis")}>
                Analyze
              </Button>
            </div>
          </section>
        ) : null}
        {renderPage()}
      </main>
    </div>
  );
}
