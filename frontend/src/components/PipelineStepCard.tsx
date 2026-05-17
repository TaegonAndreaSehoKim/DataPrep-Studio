import type { PipelineStep } from "../api/types";

export function PipelineStepCard({
  step,
  onToggle,
  onDelete,
  onMoveUp,
  onMoveDown
}: {
  step: PipelineStep;
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
