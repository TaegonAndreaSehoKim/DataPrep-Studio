import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiClient } from "../api/client";
import type {
  AnalysisCharts as AnalysisChartsData,
  AnalysisOverview,
  AnalysisPreprocessingRecommendations,
  AnalysisRun,
  ColumnType,
  DatasetConfig,
  DatasetFile,
  DatasetSetupSuggestion,
  Pipeline,
  SuggestedPipelineStep
} from "../api/types";
import { AnalysisCharts } from "../components/AnalysisCharts";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { ScoreCard } from "../components/ScoreCard";

export function AnalysisPage({
  projectId,
  analysisId,
  onAnalysisSelected,
  onOpenIssues,
  onOpenColumns,
  onBuildPipeline,
  onPipelineCreated,
  onUseRecommendation
}: {
  projectId: number | null;
  analysisId: number | null;
  onAnalysisSelected: (analysisId: number) => void;
  onOpenIssues: () => void;
  onOpenColumns: () => void;
  onBuildPipeline: (analysisId: number) => void;
  onPipelineCreated: (pipelineId: number) => void;
  onUseRecommendation: (analysisId: number, step: SuggestedPipelineStep) => void;
}) {
  const [datasets, setDatasets] = useState<DatasetFile[]>([]);
  const [datasetConfigs, setDatasetConfigs] = useState<DatasetConfig[]>([]);
  const [setupSuggestion, setSetupSuggestion] = useState<DatasetSetupSuggestion | null>(null);
  const [suggestionAppliedForDatasetId, setSuggestionAppliedForDatasetId] = useState<number | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisRun[]>([]);
  const [overview, setOverview] = useState<AnalysisOverview | null>(null);
  const [preprocessingRecommendations, setPreprocessingRecommendations] = useState<AnalysisPreprocessingRecommendations | null>(null);
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [charts, setCharts] = useState<AnalysisChartsData | null>(null);
  const [mode, setMode] = useState<Pipeline["mode"]>("single");
  const [target, setTarget] = useState("");
  const [problemType, setProblemType] = useState<AnalysisRun["problem_type"]>("classification");
  const [selectedConfigId, setSelectedConfigId] = useState("");
  const [configName, setConfigName] = useState("default analysis setup");
  const [missingTokens, setMissingTokens] = useState("?,NA,N/A,unknown");
  const [ignoredColumns, setIgnoredColumns] = useState("");
  const [columnTypeOverrides, setColumnTypeOverrides] = useState<Record<string, ColumnType | "">>({});
  const [loading, setLoading] = useState(Boolean(projectId));
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const preferredDataset = useMemo(() => {
    return mode === "single" ? datasets.find((dataset) => dataset.role === "single") ?? null : datasets.find((dataset) => dataset.role === "train") ?? null;
  }, [datasets, mode]);

  const availableColumns = useMemo(() => {
    return preferredDataset?.columns ?? [];
  }, [preferredDataset]);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    setLoading(true);
    Promise.all([apiClient.listProjectDatasets(projectId), apiClient.listProjectAnalysis(projectId), apiClient.listDatasetConfigs(projectId)])
      .then(([datasetResult, analysisResult, configResult]) => {
        setDatasets(datasetResult);
        setAnalyses(analysisResult);
        setDatasetConfigs(configResult);
        const nextAnalysis = analysisId ? analysisResult.find((item) => item.id === analysisId) : analysisResult[0];
        if (nextAnalysis) {
          onAnalysisSelected(nextAnalysis.id);
          return Promise.all([
            apiClient.getAnalysisOverview(nextAnalysis.id),
            apiClient.getAnalysisPreprocessingRecommendations(nextAnalysis.id),
            apiClient.getTrainTestComparison(nextAnalysis.id).catch(() => null),
            apiClient.getAnalysisCharts(nextAnalysis.id)
          ]).then(([nextOverview, nextRecommendations, nextComparison, nextCharts]) => {
            setOverview(nextOverview);
            setPreprocessingRecommendations(nextRecommendations);
            setComparison(nextComparison);
            setCharts(nextCharts);
          });
        }
        setOverview(null);
        setPreprocessingRecommendations(null);
        setComparison(null);
        setCharts(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId, analysisId, onAnalysisSelected]);

  useEffect(() => {
    if (!target && availableColumns.length) {
      setTarget(availableColumns[availableColumns.length - 1]);
    }
  }, [availableColumns, target]);

  useEffect(() => {
    setColumnTypeOverrides((current) => {
      const next: Record<string, ColumnType | ""> = {};
      for (const column of availableColumns) {
        next[column] = current[column] ?? "";
      }
      return next;
    });
  }, [availableColumns]);

  useEffect(() => {
    if (!selectedConfigId) {
      return;
    }
    const config = datasetConfigs.find((item) => item.id === Number(selectedConfigId));
    if (!config) {
      return;
    }
    setConfigName(config.name);
    setMode(config.mode);
    setTarget(config.target_column ?? "");
    setProblemType(config.problem_type);
    setMissingTokens(config.missing_value_tokens.join(","));
    setIgnoredColumns(config.ignored_columns.join(","));
    setColumnTypeOverrides((current) => {
      const next = { ...current };
      for (const [column, type] of Object.entries(config.column_type_overrides)) {
        next[column] = type;
      }
      return next;
    });
  }, [datasetConfigs, selectedConfigId]);

  function applySuggestion(suggestion: DatasetSetupSuggestion) {
    if (suggestion.recommended_target_column) {
      setTarget(suggestion.recommended_target_column);
    }
    setProblemType(suggestion.recommended_problem_type);
    setMissingTokens(suggestion.missing_value_tokens.join(","));
    setIgnoredColumns(suggestion.ignored_columns.join(","));
    setColumnTypeOverrides((current) => {
      const next: Record<string, ColumnType | ""> = { ...current };
      for (const column of availableColumns) {
        next[column] = suggestion.column_type_overrides[column] ?? current[column] ?? "";
      }
      return next;
    });
    setNotice("Suggested setup applied from the loaded dataset.");
  }

  useEffect(() => {
    if (!preferredDataset) {
      setSetupSuggestion(null);
      return;
    }
    apiClient
      .getDatasetSetupSuggestions(preferredDataset.id)
      .then((suggestion) => {
        setSetupSuggestion(suggestion);
        if (!selectedConfigId && suggestionAppliedForDatasetId !== preferredDataset.id) {
          applySuggestion(suggestion);
          setSuggestionAppliedForDatasetId(preferredDataset.id);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [preferredDataset, selectedConfigId, suggestionAppliedForDatasetId]);

  function normalizedTypeOverrides() {
    return Object.fromEntries(
      Object.entries(columnTypeOverrides).filter((entry): entry is [string, ColumnType] => Boolean(entry[1]))
    );
  }

  function normalizedMissingTokens() {
    return missingTokens
      .split(",")
      .map((token) => token.trim())
      .filter(Boolean);
  }

  function normalizedIgnoredColumns() {
    return ignoredColumns
      .split(",")
      .map((column) => column.trim())
      .filter(Boolean);
  }

  async function handleSaveConfig() {
    if (!projectId) {
      return;
    }
    setRunning(true);
    setError(null);
    setNotice(null);
    try {
      const dataset = mode === "single" ? datasets.find((item) => item.role === "single") : undefined;
      const payload = {
        name: configName,
        dataset_file_id: dataset?.id ?? null,
        target_column: target || null,
        problem_type: problemType,
        mode,
        column_type_overrides: normalizedTypeOverrides(),
        missing_value_tokens: normalizedMissingTokens(),
        ignored_columns: normalizedIgnoredColumns()
      };
      const config = selectedConfigId
        ? await apiClient.updateDatasetConfig(Number(selectedConfigId), payload)
        : await apiClient.createDatasetConfig(projectId, payload);
      setDatasetConfigs((current) => [config, ...current.filter((item) => item.id !== config.id)]);
      setSelectedConfigId(String(config.id));
      setNotice(selectedConfigId ? "Setup updated." : "Setup saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save setup");
    } finally {
      setRunning(false);
    }
  }

  async function handleDeleteConfig() {
    if (!selectedConfigId) {
      return;
    }
    setRunning(true);
    setError(null);
    setNotice(null);
    try {
      await apiClient.deleteDatasetConfig(Number(selectedConfigId));
      setDatasetConfigs((current) => current.filter((item) => item.id !== Number(selectedConfigId)));
      setSelectedConfigId("");
      setConfigName("default analysis setup");
      setNotice("Setup deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete setup");
    } finally {
      setRunning(false);
    }
  }

  async function handleRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      return;
    }
    setRunning(true);
    setError(null);
    setNotice(null);
    try {
      const analysis = await apiClient.runAnalysis(projectId, {
        dataset_config_id: selectedConfigId ? Number(selectedConfigId) : null,
        target_column: target || null,
        problem_type: problemType,
        mode,
        column_type_overrides: normalizedTypeOverrides(),
        missing_value_tokens: normalizedMissingTokens(),
        ignored_columns: normalizedIgnoredColumns()
      });
      onAnalysisSelected(analysis.id);
      const [nextOverview, nextRecommendations, nextComparison, nextCharts] = await Promise.all([
        apiClient.getAnalysisOverview(analysis.id),
        apiClient.getAnalysisPreprocessingRecommendations(analysis.id),
        apiClient.getTrainTestComparison(analysis.id).catch(() => null),
        apiClient.getAnalysisCharts(analysis.id)
      ]);
      setOverview(nextOverview);
      setPreprocessingRecommendations(nextRecommendations);
      setComparison(nextComparison);
      setCharts(nextCharts);
      setAnalyses((current) => [analysis, ...current.filter((item) => item.id !== analysis.id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setRunning(false);
    }
  }

  async function handleCreateSuggestedPipeline() {
    if (!projectId || !overview) {
      return;
    }
    setRunning(true);
    setError(null);
    setNotice(null);
    try {
      const pipeline = await apiClient.createSuggestedPipeline(projectId, overview.analysis_run.id, {
        name: `Suggested preprocessing #${overview.analysis_run.id}`
      });
      setNotice(`Suggested pipeline created with ${pipeline.steps.length} steps.`);
      onPipelineCreated(pipeline.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create suggested pipeline");
    } finally {
      setRunning(false);
    }
  }

  if (!projectId) {
    return <EmptyState title="No project selected" message="Choose a project before running analysis." />;
  }

  if (loading) {
    return <LoadingState />;
  }

  return (
    <div className="page-stack">
      <section className="metric-grid">
        <ScoreCard label="Readiness" value={overview ? overview.analysis_run.readiness_score.toFixed(1) : "Pending"} />
        <ScoreCard label="Issues" value={overview ? Object.values(overview.issue_counts).reduce((sum, value) => sum + value, 0) : "Pending"} />
        <ScoreCard label="Columns" value={overview?.column_count ?? "Pending"} />
      </section>

      <Card title="Run Analysis">
        <form className="form" onSubmit={handleRun}>
          {error ? <ErrorState message={error} /> : null}
          {notice ? <div className="state state-success">{notice}</div> : null}
          <label>
            <span>Saved Setup</span>
            <select value={selectedConfigId} onChange={(event) => setSelectedConfigId(event.target.value)}>
              <option value="">Manual setup</option>
              {datasetConfigs.map((config) => (
                <option key={config.id} value={config.id}>
                  {config.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Setup Name</span>
            <input value={configName} onChange={(event) => setConfigName(event.target.value)} />
          </label>
          <label>
            <span>Mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value as Pipeline["mode"])}>
              <option value="single">Single dataset</option>
              <option value="train_test">Train/test pair</option>
            </select>
          </label>
          <label>
            <span>Target Column</span>
            <select value={target} onChange={(event) => setTarget(event.target.value)}>
              <option value="">No target</option>
              {availableColumns.map((column) => (
                <option key={column} value={column}>
                  {column}
                </option>
              ))}
            </select>
          </label>
          {setupSuggestion?.target_candidates.length ? (
            <div className="suggestion-box">
              <strong>Suggested setup</strong>
              <span>
                Target {setupSuggestion.recommended_target_column || "none"} / {setupSuggestion.recommended_problem_type}
              </span>
              <div className="target-candidates">
                {setupSuggestion.target_candidates.map((candidate) => (
                  <button type="button" key={candidate.column_name} onClick={() => setTarget(candidate.column_name)}>
                    {candidate.column_name}
                    <small>{Math.round(candidate.score * 100)}% / {candidate.inferred_type}</small>
                  </button>
                ))}
              </div>
              <Button type="button" variant="secondary" onClick={() => applySuggestion(setupSuggestion)}>
                Apply Suggestions
              </Button>
            </div>
          ) : null}
          <label>
            <span>Problem Type</span>
            <select value={problemType} onChange={(event) => setProblemType(event.target.value as AnalysisRun["problem_type"])}>
              <option value="classification">Classification</option>
              <option value="regression">Regression</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>
            <span>Missing Value Tokens</span>
            <input value={missingTokens} onChange={(event) => setMissingTokens(event.target.value)} placeholder="?,NA,N/A,unknown" />
            <small>Comma-separated strings to treat as missing during analysis only.</small>
          </label>
          <label>
            <span>Ignored Columns</span>
            <input value={ignoredColumns} onChange={(event) => setIgnoredColumns(event.target.value)} placeholder="id,raw_notes" />
            <small>Comma-separated columns to exclude from profiling and issue detection.</small>
          </label>
          <div className="toolbar no-margin">
            <Button type="button" variant="secondary" disabled={running || !datasets.length} onClick={handleSaveConfig}>
              {selectedConfigId ? "Update Setup" : "Save Setup"}
            </Button>
            <Button type="button" variant="ghost" disabled={running || !selectedConfigId} onClick={handleDeleteConfig}>
              Delete Setup
            </Button>
            <Button type="submit" disabled={running || !datasets.length}>
              {running ? "Running" : "Run Analysis"}
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Column Type Overrides">
        {availableColumns.length ? (
          <div className="override-grid">
            {availableColumns.map((column) => (
              <label key={column}>
                <span>{column}</span>
                <select
                  value={columnTypeOverrides[column] ?? ""}
                  onChange={(event) => {
                    setColumnTypeOverrides((current) => ({
                      ...current,
                      [column]: event.target.value as ColumnType | ""
                    }));
                  }}
                >
                  <option value="">Infer automatically</option>
                  <option value="numeric">numeric</option>
                  <option value="categorical">categorical</option>
                  <option value="boolean">boolean</option>
                  <option value="datetime">datetime</option>
                  <option value="text">text</option>
                  <option value="unknown">unknown</option>
                </select>
              </label>
            ))}
          </div>
        ) : (
          <EmptyState title="No columns available" message="Upload a dataset before configuring column type overrides." />
        )}
      </Card>

      <Card title="Analysis Results">
        {overview ? (
          <div className="page-stack">
            <div className="toolbar no-margin">
              <Button variant="secondary" onClick={onOpenIssues}>Issues</Button>
              <Button variant="secondary" onClick={onOpenColumns}>Columns</Button>
              <a className="button button-secondary" href={apiClient.analysisReportUrl(overview.analysis_run.id)}>Download Report</a>
              <Button variant="secondary" disabled={running} onClick={handleCreateSuggestedPipeline}>Create Suggested Pipeline</Button>
              <Button onClick={() => onBuildPipeline(overview.analysis_run.id)}>Build Pipeline</Button>
            </div>
            <div className="summary-grid">
              <pre>{JSON.stringify(overview.issue_counts, null, 2)}</pre>
              <pre>{JSON.stringify(overview.column_type_counts, null, 2)}</pre>
            </div>
            {comparison ? (
              <div className="summary-grid">
                <pre>{JSON.stringify({ drift_score: comparison.drift_score }, null, 2)}</pre>
                <pre>{JSON.stringify(comparison.summary, null, 2)}</pre>
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState title="No analysis yet" message="Upload a CSV and run analysis to see readiness details." />
        )}
      </Card>

      <Card title="Preprocessing Recommendations">
        {preprocessingRecommendations?.recommendations.length ? (
          <div className="list">
            {preprocessingRecommendations.recommendations.map((recommendation, index) => (
              <div className="issue-card" key={`${recommendation.category}-${index}`}>
                <div className="issue-content">
                  <strong>{recommendation.title}</strong>
                  <p>{recommendation.rationale}</p>
                  {recommendation.affected_columns.length ? (
                    <small>Columns: {recommendation.affected_columns.join(", ")}</small>
                  ) : null}
                  {recommendation.suggested_step ? (
                    <>
                      <small>
                        Suggested step: {recommendation.suggested_step.operation_type} / {recommendation.suggested_step.columns.length} columns
                      </small>
                      <div className="toolbar no-margin">
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => overview && recommendation.suggested_step && onUseRecommendation(overview.analysis_run.id, {
                            ...recommendation.suggested_step,
                            source_title: recommendation.title,
                            source_category: recommendation.category
                          })}
                        >
                          Add to Pipeline
                        </Button>
                      </div>
                    </>
                  ) : (
                    <small>Manual review recommended before preprocessing.</small>
                  )}
                </div>
                <span className={`issue-badge issue-${recommendation.priority === "critical" ? "critical" : recommendation.priority === "high" ? "warning" : "info"}`}>
                  {recommendation.priority}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No recommendations"
            message={preprocessingRecommendations?.notes[0] ?? "Run analysis to receive preprocessing recommendations."}
          />
        )}
      </Card>

      <AnalysisCharts charts={charts} />

      <Card title="Recent Analysis Runs">
        {analyses.length ? (
          <div className="list">
            {analyses.map((analysis) => (
              <button
                className="list-row list-button"
                key={analysis.id}
                onClick={() => {
                  onAnalysisSelected(analysis.id);
                  Promise.all([
                    apiClient.getAnalysisOverview(analysis.id),
                    apiClient.getAnalysisPreprocessingRecommendations(analysis.id),
                    apiClient.getTrainTestComparison(analysis.id).catch(() => null),
                    apiClient.getAnalysisCharts(analysis.id)
                  ])
                    .then(([nextOverview, nextRecommendations, nextComparison, nextCharts]) => {
                      setOverview(nextOverview);
                      setPreprocessingRecommendations(nextRecommendations);
                      setComparison(nextComparison);
                      setCharts(nextCharts);
                    })
                    .catch((err: Error) => setError(err.message));
                }}
              >
                <strong>Score {analysis.readiness_score.toFixed(1)}</strong>
                <span>{analysis.problem_type} / target {analysis.target_column || "none"}</span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="No runs" message="Run analysis to create profiles and issue reports." />
        )}
      </Card>
    </div>
  );
}
