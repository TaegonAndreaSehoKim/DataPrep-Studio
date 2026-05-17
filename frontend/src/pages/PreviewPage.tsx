import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { AnalysisCharts as AnalysisChartsData, PreviewResult } from "../api/types";
import { AnalysisCharts } from "../components/AnalysisCharts";
import { BeforeAfterPanel } from "../components/BeforeAfterPanel";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

function formatCount(value: number | null) {
  return value === null ? "-" : value;
}

export function PreviewPage({
  pipelineId,
  onApplied
}: {
  pipelineId: number | null;
  onApplied: (runId: number) => void;
}) {
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [charts, setCharts] = useState<AnalysisChartsData | null>(null);
  const [loading, setLoading] = useState(Boolean(pipelineId));
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pipelineId) {
      return;
    }
    setLoading(true);
    Promise.all([apiClient.previewPipeline(pipelineId), apiClient.previewPipelineCharts(pipelineId)])
      .then(([nextPreview, nextCharts]) => {
        setPreview(nextPreview);
        setCharts(nextCharts);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [pipelineId]);

  async function apply() {
    if (!pipelineId) {
      return;
    }
    setApplying(true);
    setError(null);
    try {
      const run = await apiClient.applyPipeline(pipelineId);
      onApplied(run.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Apply failed");
    } finally {
      setApplying(false);
    }
  }

  if (!pipelineId) {
    return <EmptyState title="No pipeline selected" message="Select a pipeline before previewing." />;
  }

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!preview) {
    return <EmptyState title="No preview" message="Preview did not return a result." />;
  }

  return (
    <div className="page-stack">
      <Card title="Pipeline Preview">
        <div className="toolbar">
          <Button onClick={apply} disabled={applying}>{applying ? "Applying" : "Apply Pipeline"}</Button>
        </div>
        <BeforeAfterPanel before={preview.before_summary} after={preview.after_summary} />
      </Card>
      <AnalysisCharts charts={charts} />
      <Card title="Column Changes">
        {preview.column_diffs.length ? (
          <div className="preview-table-wrap no-margin">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Status</th>
                  <th>Missing Before</th>
                  <th>Missing After</th>
                  <th>Changed Sample Rows</th>
                  <th>Type Before</th>
                  <th>Type After</th>
                </tr>
              </thead>
              <tbody>
                {preview.column_diffs.map((diff) => (
                  <tr key={diff.column_name}>
                    <td>{diff.column_name}</td>
                    <td><span className={`diff-status diff-${diff.status}`}>{diff.status}</span></td>
                    <td>{formatCount(diff.before_missing_count)}</td>
                    <td>{formatCount(diff.after_missing_count)}</td>
                    <td>{formatCount(diff.changed_sample_count)}</td>
                    <td>{diff.before_dtype ?? "-"}</td>
                    <td>{diff.after_dtype ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No column changes" message="Preview did not report column-level changes." />
        )}
      </Card>
      <Card title="Step Effects">
        {preview.step_effects.length ? (
          <div className="list">
            {preview.step_effects.map((effect, index) => (
              <div className="list-row" key={index}>
                <strong>{String(effect.operation_type)}</strong>
                <span>{String(effect.summary)}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No enabled steps" message="Add enabled steps to see preview effects." />
        )}
      </Card>
      <Card title="Sample Rows">
        <div className="summary-grid">
          <div>
            <h3>Before</h3>
            <pre>{JSON.stringify(preview.before_sample_rows, null, 2)}</pre>
          </div>
          <div>
            <h3>After</h3>
            <pre>{JSON.stringify(preview.sample_rows, null, 2)}</pre>
          </div>
        </div>
      </Card>
    </div>
  );
}
