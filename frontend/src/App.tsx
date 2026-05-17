import { useCallback, useEffect, useState } from "react";
import { BarChart3, Columns3, FileUp, Home, ListChecks, PackageOpen, Play, SlidersHorizontal } from "lucide-react";

import { apiClient } from "./api/client";
import type { Dashboard, DatasetFile } from "./api/types";
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

export default function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<number | null>(null);
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const [selectedPipelineRunId, setSelectedPipelineRunId] = useState<number | null>(null);
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
