import type { OperationMetadata, PipelineStep, PipelineValidationIssue } from "../api/types";

export type PipelineStepSource = {
  type?: string;
  title?: string;
  category?: string;
  reason?: string;
  issue_id?: number;
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "not set";
  }
  if (Array.isArray(value)) {
    return value.length ? value.map(String).join(", ") : "empty";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function sourceLabel(source: PipelineStepSource | null) {
  if (!source) {
    return "Manual";
  }
  return source.type === "issue" ? "From Issue" : "Recommended";
}

export function validationFix(issue: PipelineValidationIssue) {
  if (issue.message.includes("requires at least one selected column")) {
    return "Select at least one compatible column, or use an operation that can run without columns.";
  }
  if (issue.message.includes("not available at this step")) {
    return "Check whether an earlier step dropped or renamed this column, then move this step earlier or select the new column name.";
  }
  if (issue.message.includes("supports")) {
    return "Choose columns with a supported inferred type, or change the operation.";
  }
  if (issue.message.includes("Missing required param")) {
    return "Open the parameters section and fill the required value.";
  }
  if (issue.message.includes("must be one of")) {
    return "Choose one of the allowed parameter values.";
  }
  return "Review this step's columns and parameters before previewing or applying.";
}

export function PipelineStepCard({
  step,
  stepNumber,
  operation,
  source = null,
  validationIssues = [],
  onToggle,
  onDelete,
  onMoveUp,
  onMoveDown
}: {
  step: PipelineStep;
  stepNumber?: number;
  operation?: OperationMetadata | null;
  source?: PipelineStepSource | null;
  validationIssues?: PipelineValidationIssue[];
  onToggle?: () => void;
  onDelete?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}) {
  const displayParams = Object.entries(step.params).filter(([key]) => key !== "__dataprep_source");
  const title = operation?.label ?? step.operation_type;

  return (
    <article className="pipeline-step">
      <div className="step-number">{stepNumber ?? step.order_index + 1}</div>
      <div className="step-main">
        <div className="step-heading">
          <span className={`source-badge ${source ? "source-recommended" : "source-manual"}`}>{sourceLabel(source)}</span>
          <span className={`source-badge ${step.enabled ? "source-enabled" : "source-disabled"}`}>{step.enabled ? "Enabled" : "Disabled"}</span>
          <strong>{title}</strong>
          <small>{step.operation_type}</small>
        </div>
        <p>{operation?.description ?? "Custom preprocessing operation."}</p>
        <dl className="step-summary">
          <div>
            <dt>Columns</dt>
            <dd>{step.columns.length ? step.columns.join(", ") : "All rows / no column selection"}</dd>
          </div>
          <div>
            <dt>Parameters</dt>
            <dd>
              {displayParams.length
                ? displayParams.map(([key, value]) => `${key}: ${formatValue(value)}`).join(" / ")
                : "Default settings"}
            </dd>
          </div>
          {source ? (
            <div>
              <dt>Why added</dt>
              <dd>{source.reason || source.title || "Added from analysis context."}</dd>
            </div>
          ) : null}
        </dl>
        <div className="step-impact">Preview impact: use Preview to inspect before/after row samples, column changes, and step effects.</div>
        {validationIssues.length ? (
          <div className="step-validation">
            <span className={`issue-badge ${validationIssues.some((issue) => issue.severity === "error") ? "issue-critical" : "issue-warning"}`}>
              {validationIssues.length} validation {validationIssues.length === 1 ? "issue" : "issues"}
            </span>
            <ul>
              {validationIssues.map((issue, index) => (
                <li key={index}>
                  <strong>{issue.message}</strong>
                  <span>Fix: {validationFix(issue)}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <div className="step-actions">
        <button type="button" onClick={onMoveUp}>Up</button>
        <button type="button" onClick={onMoveDown}>Down</button>
        <button type="button" onClick={onToggle}>{step.enabled ? "Disable" : "Enable"}</button>
        <button type="button" onClick={onDelete}>Delete</button>
      </div>
    </article>
  );
}
