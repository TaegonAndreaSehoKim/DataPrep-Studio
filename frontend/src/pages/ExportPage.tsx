import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { PipelineRun } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

export function ExportPage({
  projectId,
  pipelineRunId,
  onRunSelected
}: {
  projectId: number | null;
  pipelineRunId: number | null;
  onRunSelected: (run: PipelineRun) => void;
}) {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selected, setSelected] = useState<PipelineRun | null>(null);
  const [loading, setLoading] = useState(Boolean(projectId || pipelineRunId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const loader = pipelineRunId
      ? apiClient.getPipelineRun(pipelineRunId).then((run) => {
          setSelected(run);
          onRunSelected(run);
          return projectId ? apiClient.listProjectPipelineRuns(projectId).then(setRuns) : undefined;
        })
      : projectId
        ? apiClient.listProjectPipelineRuns(projectId).then((items) => {
          setRuns(items);
          const firstRun = items[0] ?? null;
          setSelected(firstRun);
          if (firstRun) {
            onRunSelected(firstRun);
          }
        })
        : Promise.resolve();

    loader.catch((err: Error) => setError(err.message)).finally(() => setLoading(false));
  }, [onRunSelected, projectId, pipelineRunId]);

  if (!projectId && !pipelineRunId) {
    return <EmptyState title="No project selected" message="Apply a pipeline to create export artifacts." />;
  }

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  return (
    <div className="page-stack">
      <Card title="Pipeline Runs">
        {runs.length ? (
          <div className="list">
            {runs.map((run) => (
              <button
                className="list-row list-button"
                key={run.id}
                onClick={() => {
                  setSelected(run);
                  onRunSelected(run);
                }}
              >
                <strong>Run #{run.id}</strong>
                <span>{run.status}</span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="No pipeline runs" message="Apply a pipeline to create cleaned CSVs, config, report, and code." />
        )}
      </Card>

      {selected ? (
        <Card title={`Downloads for Run #${selected.id}`}>
          <div className="toolbar wrap">
            <a className="button button-secondary" href={apiClient.downloadUrl(selected.id, "config")}>Config</a>
            <a className="button button-secondary" href={apiClient.downloadUrl(selected.id, "report")}>Report</a>
            <a className="button button-secondary" href={apiClient.downloadUrl(selected.id, "code")}>Code</a>
            {selected.output_paths.cleaned_single ? <a className="button button-secondary" href={apiClient.downloadUrl(selected.id, "cleaned-single")}>Cleaned CSV</a> : null}
            {selected.output_paths.cleaned_train ? <a className="button button-secondary" href={apiClient.downloadUrl(selected.id, "cleaned-train")}>Clean Train</a> : null}
            {selected.output_paths.cleaned_test ? <a className="button button-secondary" href={apiClient.downloadUrl(selected.id, "cleaned-test")}>Clean Test</a> : null}
          </div>
          <pre>{JSON.stringify(selected.output_paths, null, 2)}</pre>
        </Card>
      ) : null}
    </div>
  );
}
