import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { apiClient } from "../api/client";
import type { AnalysisRun, ColumnProfile, OperationMetadata, Pipeline, PipelineValidation, SuggestedPipelineStep } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { defaultParamsForOperation, OperationEditor } from "../components/OperationEditor";
import { PipelineStepCard, validationFix } from "../components/PipelineStepCard";

const OPERATIONS_ALLOW_EMPTY_COLUMNS = new Set(["remove_duplicate_rows", "rename_columns", "reorder_columns"]);
const SOURCE_PARAM_KEY = "__dataprep_source";

type StepSource = {
  type?: string;
  title?: string;
  category?: string;
  reason?: string;
  issue_id?: number;
};

function stepSource(step: Pipeline["steps"][number]): StepSource | null {
  const raw = step.params[SOURCE_PARAM_KEY];
  return raw && typeof raw === "object" && !Array.isArray(raw) ? raw as StepSource : null;
}

function userParams(params: Record<string, unknown>) {
  const { [SOURCE_PARAM_KEY]: _source, ...rest } = params;
  return rest;
}

export function PipelineBuilderPage({
  projectId,
  analysisId,
  pipelineId,
  initialStepDraft,
  onInitialStepDraftConsumed,
  onPipelineSelected,
  onPreview,
  onApplied
}: {
  projectId: number | null;
  analysisId: number | null;
  pipelineId: number | null;
  initialStepDraft: SuggestedPipelineStep | null;
  onInitialStepDraftConsumed: () => void;
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
  const [configText, setConfigText] = useState("");
  const [draftNotice, setDraftNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(projectId));
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const consumedDraftRef = useRef<SuggestedPipelineStep | null>(null);

  const operation = useMemo(
    () => operations.find((item) => item.operation_type === operationType) ?? null,
    [operations, operationType]
  );
  const operationsByType = useMemo(() => new Map(operations.map((item) => [item.operation_type, item])), [operations]);
  const operationAllowsEmptyColumns = operation ? OPERATIONS_ALLOW_EMPTY_COLUMNS.has(operation.operation_type) : false;
  const validationIssuesByStep = useMemo(() => {
    const grouped = new Map<number, PipelineValidation["issues"]>();
    for (const issue of validation?.issues ?? []) {
      if (issue.step_id === null) {
        continue;
      }
      grouped.set(issue.step_id, [...(grouped.get(issue.step_id) ?? []), issue]);
    }
    return grouped;
  }, [validation]);
  const sourcedSteps = useMemo(() => selectedPipeline?.steps.filter((step) => stepSource(step)) ?? [], [selectedPipeline]);

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
    if (!initialStepDraft) {
      consumedDraftRef.current = null;
      return;
    }
    if (consumedDraftRef.current === initialStepDraft) {
      return;
    }
    if (!operations.length) {
      return;
    }
    consumedDraftRef.current = initialStepDraft;
    const draftOperation = operations.find((item) => item.operation_type === initialStepDraft.operation_type);
    if (!draftOperation) {
      setError(`Recommended operation is not available: ${initialStepDraft.operation_type}`);
      onInitialStepDraftConsumed();
      return;
    }
    const nextParams = {
      ...defaultParamsForOperation(draftOperation),
      ...initialStepDraft.params,
      [SOURCE_PARAM_KEY]: {
        type: "recommendation",
        title: initialStepDraft.source_title || initialStepDraft.operation_type,
        category: initialStepDraft.source_category,
        reason: initialStepDraft.reason
      }
    };
    const ensurePipeline = selectedPipeline
      ? Promise.resolve(selectedPipeline)
      : projectId
        ? apiClient.createPipeline(projectId, {
          name: `Recommended preprocessing #${selectedAnalysis || "draft"}`,
          mode,
          analysis_run_id: selectedAnalysis ? Number(selectedAnalysis) : null
        })
        : Promise.resolve(null);
    setSaving(true);
    setError(null);
    ensurePipeline
      .then(async (pipeline) => {
        if (!pipeline) {
          throw new Error("Choose a project before adding a recommendation.");
        }
        setSelectedPipeline(pipeline);
        setPipelines((current) => [pipeline, ...current.filter((item) => item.id !== pipeline.id)]);
        onPipelineSelected(pipeline.id);
        await apiClient.createPipelineStep(pipeline.id, {
          operation_type: initialStepDraft.operation_type,
          columns: initialStepDraft.columns,
          params: nextParams
        });
        const updated = await apiClient.getPipeline(pipeline.id);
        setSelectedPipeline(updated);
        setPipelines((current) => [updated, ...current.filter((item) => item.id !== updated.id)]);
        setValidation(null);
        setDraftNotice(`Added recommendation to pipeline: ${initialStepDraft.operation_type}.`);
      })
      .catch((err: Error) => {
        setOperationType(initialStepDraft.operation_type);
        setSelectedColumns(initialStepDraft.columns);
        setParams(userParams(nextParams));
        setError(err.message);
      })
      .finally(() => setSaving(false));
    onInitialStepDraftConsumed();
  }, [initialStepDraft, mode, onInitialStepDraftConsumed, onPipelineSelected, operations, projectId, selectedAnalysis, selectedPipeline]);

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

  function changeOperation(nextOperationType: string) {
    const nextOperation = operations.find((item) => item.operation_type === nextOperationType) ?? null;
    setOperationType(nextOperationType);
    setParams(defaultParamsForOperation(nextOperation));
    setSelectedColumns([]);
    setDraftNotice(null);
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
      setDraftNotice(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add step");
    } finally {
      setSaving(false);
    }
  }

  async function importConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      return;
    }
    setImporting(true);
    setError(null);
    try {
      const parsed = JSON.parse(configText) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Config JSON must be an object.");
      }
      const pipeline = await apiClient.createPipelineFromConfig(projectId, {
        name: name || "imported preprocessing config",
        analysis_run_id: selectedAnalysis ? Number(selectedAnalysis) : null,
        config: parsed as Record<string, unknown>
      });
      setSelectedPipeline(pipeline);
      setValidation(null);
      setConfigText("");
      onPipelineSelected(pipeline.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import config");
    } finally {
      setImporting(false);
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
      <Card title="Pipeline Overview">
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

        {selectedPipeline ? (
          <div className="pipeline-summary">
            <div>
              <span className="field-label">Selected Pipeline</span>
              <strong>{selectedPipeline.name}</strong>
              <small>
                {selectedPipeline.mode} / {selectedPipeline.status} / {selectedPipeline.steps.length} steps
              </small>
            </div>
            <div>
              <span className="field-label">Recommendation/Issue Steps</span>
              <strong>{sourcedSteps.length}</strong>
              <small>{sourcedSteps.length ? "Review the added items below." : "No recommendation-backed steps yet."}</small>
            </div>
          </div>
        ) : null}

        {draftNotice ? (
          <div className="state state-success action-state">
            <strong>{draftNotice}</strong>
            <span>Next: validate the pipeline, preview changes, or add another manual step.</span>
            <div className="toolbar no-margin">
              <Button variant="secondary" disabled={!selectedPipeline} onClick={validateSelectedPipeline}>Validate Pipeline</Button>
              <Button disabled={!selectedPipeline} onClick={() => selectedPipeline && onPreview(selectedPipeline.id)}>Preview Changes</Button>
            </div>
          </div>
        ) : null}
      </Card>

      <Card title="Pipeline Steps">
        {selectedPipeline?.steps.length ? (
          <div className="list">
            {selectedPipeline.steps.map((step, index) => (
              <PipelineStepCard
                key={step.id}
                step={step}
                operation={operationsByType.get(step.operation_type)}
                source={stepSource(step)}
                validationIssues={validationIssuesByStep.get(step.id) ?? []}
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
                    <strong>{issue.severity}: {issue.message}</strong>
                    <span>Fix: {validationFix(issue)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </Card>

      {sourcedSteps.length ? (
        <Card title="Added From Recommendations">
          <div className="list">
            {sourcedSteps.map((step) => {
              const source = stepSource(step);
              return (
                <div className="suggestion-box" key={step.id}>
                  <strong>{source?.title || step.operation_type}</strong>
                  <span>
                    {source?.type === "issue" ? "Issue suggestion" : "Analysis recommendation"} / {step.operation_type} / {step.columns.length ? step.columns.join(", ") : "all rows"}
                  </span>
                  {source?.reason ? <small>{source.reason}</small> : null}
                </div>
              );
            })}
          </div>
        </Card>
      ) : null}

      <Card title="Import Config">
        <form className="form" onSubmit={importConfig}>
          <label>
            <span>preprocessing_config.json</span>
            <textarea
              value={configText}
              onChange={(event) => setConfigText(event.target.value)}
              placeholder='{"mode":"single","steps":[...]}'
            />
            <small>Paste a DataPrep Studio exported config to create a new editable pipeline draft.</small>
          </label>
          <Button type="submit" variant="secondary" disabled={importing || !configText.trim()}>
            {importing ? "Importing" : "Import Config"}
          </Button>
        </form>
      </Card>

      <div>
        <Card title="Add Manual Step">
          <form className="form manual-builder" onSubmit={addStep}>
            <section className="builder-stage">
              <div className="stage-number">1</div>
              <div>
                <label>
                  <span>Choose Operation</span>
                  <select value={operationType} onChange={(event) => changeOperation(event.target.value)}>
                    {operations.map((item) => (
                      <option key={item.operation_type} value={item.operation_type}>{item.label}</option>
                    ))}
                  </select>
                </label>
                {operation ? <small>{operation.description}</small> : null}
              </div>
            </section>
            <section className="builder-stage">
              <div className="stage-number">2</div>
              <div className="column-picker">
                <div>
                  <div className="field-label">Choose Columns</div>
                  <small>Select only compatible columns. Disabled columns have an unsupported inferred type.</small>
                </div>
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
            </section>
            <section className="builder-stage">
              <div className="stage-number">3</div>
              <div>
                <div className="field-label">Tune Parameters</div>
                <details className="advanced-panel" open>
                  <summary>Operation parameters</summary>
                  <OperationEditor operation={operation} params={params} onParamsChange={setParams} />
                </details>
              </div>
            </section>
            <div className="toolbar no-margin">
              <Button type="submit" disabled={saving || !selectedPipeline || (!operationAllowsEmptyColumns && selectedColumns.length === 0)}>Add Manual Step</Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
