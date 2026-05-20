import type { PipelineStep, PipelineValidationIssue } from "../api/types";

export function PipelineStepCard({
  step,
  validationIssues = [],
  onToggle,
  onDelete,
  onMoveUp,
  onMoveDown
}: {
  step: PipelineStep;
  validationIssues?: PipelineValidationIssue[];
  onToggle?: () => void;
  onDelete?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}) {
  return (
    <article className="pipeline-step">
      <div>
        <strong>{step.operation_type}</strong>
        <p>{step.columns.length ? step.columns.join(", ") : "No columns selected"}</p>
        {validationIssues.length ? (
          <div className="step-validation">
            <span className={`issue-badge ${validationIssues.some((issue) => issue.severity === "error") ? "issue-critical" : "issue-warning"}`}>
              {validationIssues.length} validation {validationIssues.length === 1 ? "issue" : "issues"}
            </span>
            <ul>
              {validationIssues.map((issue, index) => (
                <li key={index}>{issue.message}</li>
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
