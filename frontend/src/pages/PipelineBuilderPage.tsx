import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiClient } from "../api/client";
import type { AnalysisRun, ColumnProfile, OperationMetadata, Pipeline, PipelineValidation } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { defaultParamsForOperation, OperationEditor } from "../components/OperationEditor";
import { PipelineStepCard } from "../components/PipelineStepCard";

const OPERATIONS_ALLOW_EMPTY_COLUMNS = new Set(["remove_duplicate_rows", "rename_columns", "reorder_columns"]);

export function PipelineBuilderPage({
  projectId,
  analysisId,
  pipelineId,
  onPipelineSelected,
  onPreview,
  onApplied
}: {
  projectId: number | null;
  analysisId: number | null;
  pipelineId: number | null;
  onPipelineSelected: (pipelineId: number) => void;
  onPreview: (pipelineId: number) => void;
  onApplied: (runId: number) => void;
}) {
  const [analyses, setAnalyses] = useState<AnalysisRun[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [operations, setOperations] = useState<OperationMetadata[]>([]);
  const [columnProfiles, setColumnProfiles] = useState<ColumnProfile[]>([]);
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);
  const [validation, setValidation] = useState<PipelineValidation | null>(null);
  const [name, setName] = useState("baseline preprocessing");
  const [mode, setMode] = useState<Pipeline["mode"]>("single");
  const [selectedAnalysis, setSelectedAnalysis] = useState<string>(analysisId ? String(analysisId) : "");
  const [operationType, setOperationType] = useState("");
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(Boolean(projectId));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const operation = useMemo(
    () => operations.find((item) => item.operation_type === operationType) ?? null,
    [operations, operationType]
  );
  const operationAllowsEmptyColumns = operation ? OPERATIONS_ALLOW_EMPTY_COLUMNS.has(operation.operation_type) : false;

  const availableColumns = useMemo(() => {
    const preferredRole = mode === "train_test" ? "train" : "single";
    const preferred = columnProfiles.filter((column) => column.dataset_role === preferredRole);
    const source = preferred.length ? preferred : columnProfiles;
    return source.map((column) => ({
      name: column.column_name,
      type: column.inferred_type,
      missingRate: column.missing_rate
    }));
  }, [columnProfiles, mode]);

  function refresh() {
    if (!projectId) {
      return Promise.resolve();
    }
    return Promise.all([apiClient.listProjectAnalysis(projectId), apiClient.listPipelines(projectId), apiClient.listOperations()])
      .then(([analysisResult, pipelineResult, operationResult]) => {
        setAnalyses(analysisResult);
        setPipelines(pipelineResult);
        setOperations(operationResult);
        const nextPipeline = pipelineId ? pipelineResult.find((item) => item.id === pipelineId) : pipelineResult[0];
        setSelectedPipeline(nextPipeline ?? null);
        if (nextPipeline) {
          onPipelineSelected(nextPipeline.id);
          setMode(nextPipeline.mode);
          setSelectedAnalysis(nextPipeline.analysis_run_id ? String(nextPipeline.analysis_run_id) : "");
        }
        if (!operationType && operationResult.length) {
          setOperationType(operationResult[0].operation_type);
          setParams(defaultParamsForOperation(operationResult[0]));
        }
      });
  }

  useEffect(() => {
    if (!projectId) {
      return;
    }
    setLoading(true);
    refresh()
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId, pipelineId]);

  useEffect(() => {
    if (!selectedAnalysis) {
      setColumnProfiles([]);
      return;
    }
    apiClient
      .listColumns(Number(selectedAnalysis))
      .then(setColumnProfiles)
      .catch((err: Error) => setError(err.message));
  }, [selectedAnalysis]);

  useEffect(() => {
    setParams(defaultParamsForOperation(operation));
    setSelectedColumns([]);
  }, [operation]);

  async function createPipeline(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const pipeline = await apiClient.createPipeline(projectId, {
        name,
        mode,
        analysis_run_id: selectedAnalysis ? Number(selectedAnalysis) : null
      });
      setSelectedPipeline(pipeline);
      setValidation(null);
      onPipelineSelected(pipeline.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create pipeline");
    } finally {
      setSaving(false);
    }
  }

  async function addStep(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPipeline) {
      setError("Create or select a pipeline first.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiClient.createPipelineStep(selectedPipeline.id, {
        operation_type: operationType,
        columns: selectedColumns,
        params
      });
      const updated = await apiClient.getPipeline(selectedPipeline.id);
      setSelectedPipeline(updated);
      setPipelines((current) => [updated, ...current.filter((item) => item.id !== updated.id)]);
      setValidation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add step");
    } finally {
      setSaving(false);
    }
  }

  async function reloadPipeline(id: number) {
    const updated = await apiClient.getPipeline(id);
    setSelectedPipeline(updated);
    setPipelines((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    setValidation(null);
  }

  async function validateSelectedPipeline() {
    if (!selectedPipeline) {
      return;
    }
    try {
      const result = await apiClient.validatePipeline(selectedPipeline.id);
      setValidation(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to validate pipeline");
    }
  }

  async function reorder(index: number, direction: -1 | 1) {
    if (!selectedPipeline) {
      return;
    }
    const steps = [...selectedPipeline.steps];
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= steps.length) {
      return;
    }
    [steps[index], steps[nextIndex]] = [steps[nextIndex], steps[index]];
    const updated = await apiClient.reorderPipelineSteps(selectedPipeline.id, steps.map((step) => step.id));
    setSelectedPipeline(updated);
    setValidation(null);
  }

  if (!projectId) {
    return <EmptyState title="No project selected" message="Choose a project before building a pipeline." />;
  }

  if (loading) {
    return <LoadingState />;
  }

  return (
    <div className="page-stack">
      {error ? <ErrorState message={error} /> : null}
      <Card title="Pipeline Builder">
        <form className="form compact-form" onSubmit={createPipeline}>
          <label>
            <span>Pipeline Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            <span>Analysis</span>
            <select value={selectedAnalysis} onChange={(event) => setSelectedAnalysis(event.target.value)}>
              <option value="">No analysis</option>
              {analyses.map((analysis) => (
                <option key={analysis.id} value={analysis.id}>
                  #{analysis.id} score {analysis.readiness_score.toFixed(1)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value as Pipeline["mode"])}>
              <option value="single">Single</option>
              <option value="train_test">Train/test</option>
            </select>
          </label>
          <Button type="submit" disabled={saving}>{saving ? "Saving" : "Create Pipeline"}</Button>
        </form>

        {pipelines.length ? (
          <div className="toolbar">
            <select value={selectedPipeline?.id ?? ""} onChange={(event) => {
              const pipeline = pipelines.find((item) => item.id === Number(event.target.value)) ?? null;
              setSelectedPipeline(pipeline);
              setValidation(null);
              if (pipeline) onPipelineSelected(pipeline.id);
            }}>
              {pipelines.map((pipeline) => (
                <option key={pipeline.id} value={pipeline.id}>{pipeline.name}</option>
              ))}
            </select>
            <Button variant="secondary" disabled={!selectedPipeline} onClick={() => selectedPipeline && onPreview(selectedPipeline.id)}>Preview</Button>
            <Button variant="secondary" disabled={!selectedPipeline} onClick={validateSelectedPipeline}>Validate</Button>
            <Button disabled={!selectedPipeline} onClick={async () => {
              if (!selectedPipeline) return;
              const run = await apiClient.applyPipeline(selectedPipeline.id);
              onApplied(run.id);
            }}>Apply</Button>
          </div>
        ) : null}

        {selectedPipeline?.steps.length ? (
          <div className="list">
            {selectedPipeline.steps.map((step, index) => (
              <PipelineStepCard
                key={step.id}
                step={step}
                onMoveUp={() => reorder(index, -1)}
                onMoveDown={() => reorder(index, 1)}
                onToggle={async () => {
                  await apiClient.togglePipelineStep(selectedPipeline.id, step.id);
                  await reloadPipeline(selectedPipeline.id);
                }}
                onDelete={async () => {
                  await apiClient.deletePipelineStep(selectedPipeline.id, step.id);
                  await reloadPipeline(selectedPipeline.id);
                }}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="No steps" message="Add preprocessing steps to the selected pipeline." />
        )}
        {validation ? (
          <div className={`state ${validation.valid ? "" : "state-error"}`}>
            <strong>{validation.valid ? "Pipeline is valid" : "Pipeline needs attention"}</strong>
            {validation.issues.length ? (
              <ul className="validation-list">
                {validation.issues.map((issue, index) => (
                  <li key={index}>
                    {issue.severity}: {issue.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </Card>

      <Card title="Add Step">
        <form className="form" onSubmit={addStep}>
          <label>
            <span>Operation</span>
            <select value={operationType} onChange={(event) => setOperationType(event.target.value)}>
              {operations.map((item) => (
                <option key={item.operation_type} value={item.operation_type}>{item.label}</option>
              ))}
            </select>
          </label>
          <div className="column-picker">
            <div className="field-label">Columns</div>
            {availableColumns.length ? (
              <div className="checkbox-grid">
                {availableColumns.map((column) => {
                  const isSupported = !operation || operation.supported_column_types.includes("any") || operation.supported_column_types.includes(column.type);
                  return (
                    <label className="checkbox-row" key={column.name}>
                      <input
                        type="checkbox"
                        disabled={!isSupported}
                        checked={selectedColumns.includes(column.name)}
                        onChange={(event) => {
                          setSelectedColumns((current) =>
                            event.target.checked ? [...current, column.name] : current.filter((item) => item !== column.name)
                          );
                        }}
                      />
                      <span>{column.name}</span>
                      <small>{isSupported ? column.type : `${column.type} not supported`}</small>
                    </label>
                  );
                })}
              </div>
            ) : (
              <div className="state">Select an analysis to choose columns, or add an operation that does not require columns.</div>
            )}
          </div>
          <OperationEditor operation={operation} params={params} onParamsChange={setParams} />
          <Button type="submit" disabled={saving || !selectedPipeline || (!operationAllowsEmptyColumns && selectedColumns.length === 0)}>Add Step</Button>
        </form>
      </Card>
    </div>
  );
}
