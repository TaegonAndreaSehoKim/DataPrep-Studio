import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { AnalysisRun, DatasetFile, Pipeline, Project } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

export function ProjectDetailPage({
  projectId,
  onUpload,
  onAnalyze,
  onPipeline
}: {
  projectId: number | null;
  onUpload: () => void;
  onAnalyze: (analysisId: number) => void;
  onPipeline: (pipelineId: number) => void;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<DatasetFile[]>([]);
  const [analyses, setAnalyses] = useState<AnalysisRun[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(Boolean(projectId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    setLoading(true);
    Promise.all([
      apiClient.getProject(projectId),
      apiClient.listProjectDatasets(projectId),
      apiClient.listProjectAnalysis(projectId),
      apiClient.listPipelines(projectId)
    ])
      .then(([projectResult, datasetResult, analysisResult, pipelineResult]) => {
        setProject(projectResult);
        setDatasets(datasetResult);
        setAnalyses(analysisResult);
        setPipelines(pipelineResult);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (!projectId) {
    return <EmptyState title="No project selected" message="Choose or create a project to continue." />;
  }

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  return (
    <div className="page-stack">
      <section className="intro-band">
        <div>
          <h2>{project?.name}</h2>
          <p>{project?.description || "No description"}</p>
        </div>
        <div className="toolbar no-margin">
          <Button onClick={onUpload}>Upload Dataset</Button>
        </div>
      </section>

      <section className="two-column">
        <Card title="Datasets">
          {datasets.length ? (
            <div className="list">
              {datasets.map((dataset) => (
                <div className="list-row" key={dataset.id}>
                  <strong>{dataset.filename}</strong>
                  <span>
                    {dataset.role} · {dataset.row_count} rows · {dataset.column_count} columns
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No datasets" message="Upload a single CSV or train/test pair." />
          )}
        </Card>

        <Card title="Analysis Runs">
          {analyses.length ? (
            <div className="list">
              {analyses.map((analysis) => (
                <button className="list-row list-button" key={analysis.id} onClick={() => onAnalyze(analysis.id)}>
                  <strong>Score {analysis.readiness_score.toFixed(1)}</strong>
                  <span>
                    {analysis.problem_type} · target {analysis.target_column || "none"}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="No analysis" message="Run analysis from the Analysis page after uploading data." />
          )}
        </Card>
      </section>

      <Card title="Pipelines">
        {pipelines.length ? (
          <div className="list">
            {pipelines.map((pipeline) => (
              <button className="list-row list-button" key={pipeline.id} onClick={() => onPipeline(pipeline.id)}>
                <strong>{pipeline.name}</strong>
                <span>
                  {pipeline.mode} · {pipeline.status} · {pipeline.steps.length} steps
                </span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="No pipelines" message="Build a preprocessing pipeline after analysis." />
        )}
      </Card>
    </div>
  );
}
