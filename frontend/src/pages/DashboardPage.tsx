import type { Dashboard } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ScoreCard } from "../components/ScoreCard";

export function DashboardPage({
  dashboard,
  onCreateProject,
  onSelectProject
}: {
  dashboard: Dashboard | null;
  onCreateProject: () => void;
  onSelectProject: (projectId: number) => void;
}) {
  return (
    <div className="page-stack">
      <section className="intro-band">
        <div>
          <h2>DataPrep Studio</h2>
          <p>
            Profile CSV datasets, diagnose ML-readiness issues, build explicit preprocessing pipelines, and export
            reproducible artifacts.
          </p>
        </div>
        <Button onClick={onCreateProject}>Create Project</Button>
      </section>

      <section className="metric-grid">
        <ScoreCard label="Projects" value={dashboard?.project_count ?? 0} />
        <ScoreCard label="Datasets" value={dashboard?.dataset_count ?? 0} />
        <ScoreCard label="Analyses" value={dashboard?.analysis_count ?? 0} />
        <ScoreCard label="Pipelines" value={dashboard?.pipeline_count ?? 0} />
      </section>

      <Card title="Recent Projects">
        {dashboard?.recent_projects.length ? (
          <div className="list">
            {dashboard.recent_projects.map((project) => (
              <button className="list-row list-button" key={project.id} onClick={() => onSelectProject(project.id)}>
                <strong>{project.name}</strong>
                <span>{project.description || "No description"}</span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="No projects yet" message="Create a project to start preparing a CSV dataset." />
        )}
      </Card>

      <section className="two-column">
        <Card title="Recent Analysis Runs">
          {dashboard?.recent_analysis_runs.length ? (
            <div className="list">
              {dashboard.recent_analysis_runs.map((analysis) => (
                <div className="list-row" key={analysis.id}>
                  <strong>Score {analysis.readiness_score.toFixed(1)}</strong>
                  <span>
                    Project {analysis.project_id} / {analysis.problem_type} / target {analysis.target_column || "none"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No analysis runs" message="Run analysis after uploading a dataset." />
          )}
        </Card>

        <Card title="Recent Pipeline Runs">
          {dashboard?.recent_pipeline_runs.length ? (
            <div className="list">
              {dashboard.recent_pipeline_runs.map((run) => (
                <div className="list-row" key={run.id}>
                  <strong>Run #{run.id}</strong>
                  <span>
                    Pipeline {run.pipeline_id} / {run.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No pipeline runs" message="Apply a pipeline to create exports." />
          )}
        </Card>
      </section>
    </div>
  );
}
