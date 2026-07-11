import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../api/client";
import type { Issue, SuggestedPipelineStep } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { IssueBadge } from "../components/IssueBadge";
import { LoadingState } from "../components/LoadingState";

const ISSUE_SEVERITY_RANK: Record<Issue["severity"], number> = {
  critical: 0,
  warning: 1,
  info: 2
};

function sortIssuesByImportance(items: Issue[]) {
  return [...items].sort((left, right) => {
    const severityDelta = ISSUE_SEVERITY_RANK[left.severity] - ISSUE_SEVERITY_RANK[right.severity];
    if (severityDelta !== 0) {
      return severityDelta;
    }
    const categoryDelta = left.category.localeCompare(right.category);
    if (categoryDelta !== 0) {
      return categoryDelta;
    }
    const titleDelta = left.title.localeCompare(right.title);
    if (titleDelta !== 0) {
      return titleDelta;
    }
    return left.id - right.id;
  });
}

export function IssuesPage({ analysisId, pipelineId }: { analysisId: number | null; pipelineId: number | null }) {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [suggestions, setSuggestions] = useState<Record<number, SuggestedPipelineStep>>({});
  const [issueErrors, setIssueErrors] = useState<Record<number, string>>({});
  const [addedIssues, setAddedIssues] = useState<Record<number, boolean>>({});
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(Boolean(analysisId));
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId) {
      return;
    }
    setLoading(true);
    apiClient
      .listIssues(analysisId)
      .then(setIssues)
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }, [analysisId]);

  const categories = Array.from(new Set(issues.map((issue) => issue.category))).sort();
  const filtered = useMemo(
    () => sortIssuesByImportance(
      issues.filter((issue) => (!severity || issue.severity === severity) && (!category || issue.category === category))
    ),
    [issues, severity, category]
  );

  async function loadSuggestion(issueId: number) {
    try {
      setIssueErrors((current) => {
        const next = { ...current };
        delete next[issueId];
        return next;
      });
      const suggestion = await apiClient.getIssueSuggestedStep(issueId);
      setSuggestions((current) => ({ ...current, [issueId]: suggestion }));
    } catch (err) {
      setIssueErrors((current) => ({ ...current, [issueId]: err instanceof Error ? err.message : "No suggestion available" }));
    }
  }

  async function addSuggestion(issueId: number) {
    if (!pipelineId) {
      setIssueErrors((current) => ({ ...current, [issueId]: "Select or create a pipeline before adding issue suggestions." }));
      return;
    }
    try {
      setIssueErrors((current) => {
        const next = { ...current };
        delete next[issueId];
        return next;
      });
      await apiClient.createPipelineStepFromIssue(pipelineId, issueId);
      await loadSuggestion(issueId);
      setAddedIssues((current) => ({ ...current, [issueId]: true }));
    } catch (err) {
      setIssueErrors((current) => ({ ...current, [issueId]: err instanceof Error ? err.message : "Failed to add suggested step" }));
    }
  }

  if (!analysisId) {
    return <EmptyState title="No analysis selected" message="Run or select an analysis before viewing issues." />;
  }

  if (loading) {
    return <LoadingState />;
  }

  if (loadError) {
    return <ErrorState message={loadError} />;
  }

  return (
    <Card title="Issues">
      <div className="toolbar">
        <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
          <option value="">All severities</option>
          <option value="critical">critical</option>
          <option value="warning">warning</option>
          <option value="info">info</option>
        </select>
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">All categories</option>
          {categories.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      {filtered.length ? (
        <div className="list">
          {filtered.map((issue) => (
            <div className="issue-card" key={issue.id}>
              <IssueBadge severity={issue.severity} />
              <div className="issue-content">
                <strong>{issue.title}</strong>
                <p>{issue.explanation}</p>
                <span>{issue.suggested_actions.join(" / ")}</span>
                {suggestions[issue.id] ? (
                  <div className="suggestion-box">
                    <strong>{suggestions[issue.id].operation_type}</strong>
                    <span>{suggestions[issue.id].reason}</span>
                    <code>{suggestions[issue.id].columns.join(", ") || "all rows"}</code>
                  </div>
                ) : null}
                {issueErrors[issue.id] ? <div className="state state-error compact-state">{issueErrors[issue.id]}</div> : null}
                {addedIssues[issue.id] ? <div className="state state-success compact-state">Suggested step added.</div> : null}
                <div className="toolbar no-margin">
                  <Button variant="secondary" onClick={() => loadSuggestion(issue.id)}>
                    Suggest Step
                  </Button>
                  <Button disabled={!pipelineId} onClick={() => addSuggestion(issue.id)}>
                    Add to Pipeline
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No matching issues" message="Adjust filters or run a different analysis." />
      )}
    </Card>
  );
}
