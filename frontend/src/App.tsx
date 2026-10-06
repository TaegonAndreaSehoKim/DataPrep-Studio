import { useCallback, useEffect, useRef, useState } from "react";
import { BarChart3, Columns3, FileUp, Home, ListChecks, PackageOpen, Play, SlidersHorizontal } from "lucide-react";

import { apiClient } from "./api/client";
import type { AnalysisOverview, Dashboard, DatasetFile, Pipeline, PipelineRun, SuggestedPipelineStep } from "./api/types";
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
  const [selectedAnalysisOverview, setSelectedAnalysisOverview] = useState<AnalysisOverview | null>(null);
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const projectRef = useRef<number | null>(null);
  const pipelineRef = useRef<number | null>(null);
  const datasetRequestRef = useRef(0);

  useEffect(() => {
    apiClient
      .dashboard()
      .then(setDashboard)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const selectProject = useCallback((projectId: number | null) => {
    if (projectRef.current !== projectId) {
      projectRef.current = projectId;
      pipelineRef.current = null;
      datasetRequestRef.current += 1;
      setSelectedAnalysisId(null);
      setSelectedPipelineId(null);
      setSelectedPipelineRunId(null);
      setPendingStepDraft(null);
      setLoadedDatasets([]);
      setSelectedAnalysisOverview(null);
      setSelectedPipeline(null);
      setError(null);
    }
    setSelectedProjectId(projectId);
  }, []);

  const chooseProject = useCallback((projectId: number, nextPage: PageKey = "project") => {
    selectProject(projectId);
    setPage(nextPage);
  }, [selectProject]);

  const selectAnalysis = useCallback((analysisId: number | null) => {
    if (projectRef.current !== selectedProjectId) return;
    if (analysisId !== selectedAnalysisId) {
      pipelineRef.current = null;
      setSelectedPipelineId(null);
      setSelectedPipelineRunId(null);
      setSelectedPipeline(null);
      setPendingStepDraft(null);
      setSelectedAnalysisOverview(null);
    }
    setSelectedAnalysisId(analysisId);
  }, [selectedProjectId, selectedAnalysisId]);

  const selectPipeline = useCallback((pipelineId: number) => {
    if (projectRef.current !== selectedProjectId) return;
    if (pipelineRef.current !== pipelineId) {
      pipelineRef.current = pipelineId;
      setSelectedPipelineRunId(null);
      setSelectedPipeline(null);
    }
    setSelectedPipelineId(pipelineId);
  }, [selectedProjectId]);

  const refreshDashboard = useCallback(() => {
    setError(null);
    apiClient.dashboard().then(setDashboard).catch((err: Error) => setError(err.message));
  }, []);

  const refreshLoadedDatasets = useCallback((projectId: number | null) => {
    const requestId = ++datasetRequestRef.current;
    if (!projectId) {
      setLoadedDatasets([]);
      return Promise.resolve();
    }
    return apiClient
      .listProjectDatasets(projectId)
      .then((datasets) => { if (projectRef.current === projectId && datasetRequestRef.current === requestId) setLoadedDatasets(datasets); })
      .catch((err: Error) => { if (projectRef.current === projectId && datasetRequestRef.current === requestId) setError(err.message); });
  }, []);

  const handleProjectDeleted = useCallback((projectId: number) => {
    if (selectedProjectId === projectId) {
      selectProject(null);
      setSelectedAnalysisId(null);
      setSelectedPipelineId(null);
      setSelectedPipelineRunId(null);
      setPendingStepDraft(null);
      setLoadedDatasets([]);
      setSelectedAnalysisOverview(null);
      setSelectedPipeline(null);
      setPage("projects");
    }
    refreshDashboard();
  }, [refreshDashboard, selectedProjectId, selectProject]);

  useEffect(() => {
    refreshLoadedDatasets(selectedProjectId);
  }, [refreshLoadedDatasets, selectedProjectId]);

  useEffect(() => {
    if (!selectedAnalysisId) {
      setSelectedAnalysisOverview(null);
      return;
    }
    let active = true;
    apiClient
      .getAnalysisOverview(selectedAnalysisId)
      .then((overview) => { if (active) setSelectedAnalysisOverview(overview); })
      .catch(() => { if (active) setSelectedAnalysisOverview(null); });
    return () => { active = false; };
  }, [selectedAnalysisId]);

  useEffect(() => {
    if (!selectedPipelineId) {
      setSelectedPipeline(null);
      return;
    }
    let active = true;
    apiClient
      .getPipeline(selectedPipelineId)
      .then((pipeline) => { if (active) setSelectedPipeline(pipeline); })
      .catch(() => { if (active) setSelectedPipeline(null); });
    return () => { active = false; };
  }, [selectedPipelineId]);

  useEffect(() => {
    if (selectedPipeline?.id === selectedPipelineId && selectedPipeline?.analysis_run_id && selectedPipeline.analysis_run_id !== selectedAnalysisId) {
      setSelectedAnalysisId(selectedPipeline.analysis_run_id);
    }
  }, [selectedAnalysisId, selectedPipeline, selectedPipelineId]);

  const handlePipelineRunSelected = useCallback((run: PipelineRun) => {
    if (projectRef.current !== null && projectRef.current !== run.project_id) return;
    selectProject(run.project_id);
    pipelineRef.current = run.pipeline_id;
    setSelectedPipelineId(run.pipeline_id);
    setSelectedPipelineRunId(run.id);
  }, [selectProject]);

  const latestByRole = (role: DatasetFile["role"]) => loadedDatasets.find((dataset) => dataset.role === role) ?? null;

  const hasDataset = Boolean(latestByRole("single") || (latestByRole("train") && latestByRole("test")));
  const hasAnalysis = Boolean(selectedAnalysisId);
  const hasPipeline = Boolean(selectedPipelineId);
  const hasExport = Boolean(selectedPipelineRunId);
  const selectedProject = dashboard?.recent_projects.find((project) => project.id === selectedProjectId) ?? null;
  const activeWorkflowIndex = Math.max(
    0,
    workflowSteps.findIndex((step) => step.key === page)
  );
  const nextAction = (() => {
    if (!selectedProjectId) {
      return "Create or select a project to start.";
    }
    if (hasExport) {
      return "Exports are ready. Download the cleaned data and reproducible artifacts.";
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

    switch (page) {
      case "dashboard":
        return <DashboardPage dashboard={dashboard} onCreateProject={() => setPage("create")} onSelectProject={chooseProject} />;
      case "projects":
        return <ProjectListPage onCreateProject={() => setPage("create")} onSelectProject={chooseProject} onProjectDeleted={handleProjectDeleted} />;
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
            key={selectedProjectId}
            projectId={selectedProjectId}
            onUpload={() => setPage("upload")}
            onAnalyze={(analysisId) => {
              selectAnalysis(analysisId);
              setPage("analysis");
            }}
            onPipeline={(pipelineId) => {
              selectPipeline(pipelineId);
              setPage("pipeline");
            }}
            onProjectDeleted={handleProjectDeleted}
          />
        );
      case "upload":
        return (
          <UploadPage
            key={selectedProjectId}
            selectedProjectId={selectedProjectId}
            onProjectSelected={selectProject}
            onUploaded={(projectId, dataset) => {
              selectProject(projectId);
              datasetRequestRef.current += 1;
              setLoadedDatasets((current) => [dataset, ...current.filter((item) => item.id !== dataset.id)]);
              refreshDashboard();
            }}
            onAnalyzeReady={(projectId) => {
              selectProject(projectId);
              selectAnalysis(null);
              pipelineRef.current = null;
              setSelectedPipelineId(null);
              setSelectedPipeline(null);
              setSelectedPipelineRunId(null);
              setPage("analysis");
            }}
          />
        );
      case "analysis":
        return (
          <AnalysisPage
            key={selectedProjectId}
            projectId={selectedProjectId}
            analysisId={selectedAnalysisId}
            onAnalysisSelected={selectAnalysis}
            onOpenIssues={() => setPage("issues")}
            onOpenColumns={() => setPage("columns")}
            onBuildPipeline={(analysisId) => {
              selectAnalysis(analysisId);
              setPage("pipeline");
            }}
            onPipelineCreated={(pipelineId) => {
              selectPipeline(pipelineId);
              setPendingStepDraft(null);
              setPage("pipeline");
            }}
            onUseRecommendation={(analysisId, step) => {
              selectAnalysis(analysisId);
              setPendingStepDraft(step);
              setPage("pipeline");
            }}
          />
        );
      case "issues":
        return <IssuesPage key={selectedAnalysisId} analysisId={selectedAnalysisId} pipelineId={selectedPipelineId} />;
      case "columns":
        return <ColumnsPage key={selectedAnalysisId} analysisId={selectedAnalysisId} />;
      case "pipeline":
        return (
          <PipelineBuilderPage
            key={selectedProjectId}
            projectId={selectedProjectId}
            analysisId={selectedAnalysisId}
            pipelineId={selectedPipelineId}
            initialStepDraft={pendingStepDraft}
            onInitialStepDraftConsumed={() => setPendingStepDraft(null)}
            onPipelineSelected={selectPipeline}
            onPreview={(pipelineId) => {
              selectPipeline(pipelineId);
              setPage("preview");
            }}
            onApplied={(runId) => {
              if (projectRef.current !== selectedProjectId || pipelineRef.current !== selectedPipelineId) return;
              setSelectedPipelineRunId(runId);
              setPage("exports");
            }}
          />
        );
      case "preview":
        return (
          <PreviewPage
            key={selectedPipelineId}
            pipelineId={selectedPipelineId}
            onApplied={(runId) => {
              if (projectRef.current !== selectedProjectId || pipelineRef.current !== selectedPipelineId) return;
              setSelectedPipelineRunId(runId);
              setPage("exports");
            }}
          />
        );
      case "exports":
        return <ExportPage key={selectedProjectId} projectId={selectedProjectId} pipelineRunId={selectedPipelineRunId} onRunSelected={handlePipelineRunSelected} />;
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
          <section className="loaded-data-bar context-bar" aria-label="Current workspace context">
            <div>
              <span className="field-label">Project</span>
              <strong>{selectedProject?.name ?? `Project #${selectedProjectId}`}</strong>
              <small>{hasExport ? `Export run #${selectedPipelineRunId}` : "Local preprocessing workspace"}</small>
            </div>
            <div>
              <span className="field-label">Data</span>
              <strong>{latestByRole("single")?.filename ?? latestByRole("train")?.filename ?? "No dataset loaded"}</strong>
              <small>
                {latestByRole("single")
                  ? `${latestByRole("single")?.row_count} rows / ${latestByRole("single")?.column_count} columns`
                  : latestByRole("train") && latestByRole("test")
                    ? `train ${latestByRole("train")?.row_count} rows / test ${latestByRole("test")?.row_count} rows`
                    : "Upload CSV data to continue."}
              </small>
            </div>
            <div>
              <span className="field-label">Analysis</span>
              <strong>
                {selectedAnalysisOverview
                  ? `Score ${selectedAnalysisOverview.analysis_run.readiness_score.toFixed(1)}`
                  : selectedAnalysisId
                    ? `Analysis #${selectedAnalysisId}`
                    : "Not selected"}
              </strong>
              <small>
                {selectedAnalysisOverview
                  ? `${selectedAnalysisOverview.column_count ?? 0} columns / target ${selectedAnalysisOverview.analysis_run.target_column || "none"}`
                  : "Run or select an analysis."}
              </small>
            </div>
            <div>
              <span className="field-label">Pipeline</span>
              <strong>{selectedPipeline?.name ?? (selectedPipelineId ? `Pipeline #${selectedPipelineId}` : "Not selected")}</strong>
              <small>{selectedPipeline ? `${selectedPipeline.steps.length} steps / ${selectedPipeline.status}` : "Create from recommendations or manually."}</small>
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
        {error ? <ErrorState message={error} onRetry={() => { refreshDashboard(); refreshLoadedDatasets(selectedProjectId); }} /> : null}
        {renderPage()}
      </main>
    </div>
  );
}
