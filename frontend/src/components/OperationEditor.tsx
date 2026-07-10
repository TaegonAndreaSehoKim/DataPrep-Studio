import type { OperationMetadata, OperationParamMetadata } from "../api/types";

function parseJsonValue(raw: string, fallback: unknown): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) {
    return "none";
  }
  if (Array.isArray(value) || typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function guidanceText(param: OperationParamMetadata) {
  const items = [`Default: ${formatValue(param.default)}`];
  if (param.options?.length) {
    items.push(`Allowed: ${param.options.join(", ")}`);
  }
  return items.join(" / ");
}

function renderParamInput(
  param: OperationParamMetadata,
  value: unknown,
  onChange: (name: string, value: unknown) => void
) {
  if (param.type === "boolean") {
    return (
      <div className="checkbox-row">
        <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(param.name, event.target.checked)} />
        <span>{param.description}</span>
      </div>
    );
  }

  if (param.type === "select") {
    return (
      <select value={String(value ?? "")} onChange={(event) => onChange(param.name, event.target.value)}>
        {(param.options ?? []).map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  if (param.type === "number") {
    return (
      <input
        type="number"
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(event) => onChange(param.name, event.target.value === "" ? null : Number(event.target.value))}
      />
    );
  }

  if (param.type === "list" || param.type === "object") {
    return (
      <textarea
        value={JSON.stringify(value ?? param.default ?? (param.type === "list" ? [] : {}), null, 2)}
        onChange={(event) => onChange(param.name, parseJsonValue(event.target.value, value))}
      />
    );
  }

  return (
    <input
      value={value === null || value === undefined ? "" : String(value)}
      onChange={(event) => onChange(param.name, event.target.value)}
    />
  );
}

export function defaultParamsForOperation(operation: OperationMetadata | null): Record<string, unknown> {
  if (!operation) {
    return {};
  }
  return Object.fromEntries(operation.params.map((param) => [param.name, param.default ?? null]));
}

export function OperationEditor({
  operation,
  params,
  onParamsChange
}: {
  operation: OperationMetadata | null;
  params: Record<string, unknown>;
  onParamsChange: (params: Record<string, unknown>) => void;
}) {
  if (!operation) {
    return <div className="state">Select an operation to configure parameters.</div>;
  }

  function updateParam(name: string, nextValue: unknown) {
    onParamsChange({ ...params, [name]: nextValue });
  }

  return (
    <div className="operation-editor">
      <h3>{operation.label}</h3>
      <p>{operation.description}</p>
      <div className="operation-support">
        <span>Supported columns</span>
        <strong>{operation.supported_column_types.join(", ")}</strong>
      </div>
      {operation.params.length ? (
        operation.params.map((param) => (
          <label className="param-field" key={param.name}>
            <span className="param-heading">
              <span>{param.name}</span>
              <span className="param-badges">
                <span>{param.type}</span>
                {param.required ? <span>required</span> : <span>optional</span>}
              </span>
            </span>
            {renderParamInput(param, params[param.name] ?? param.default ?? null, updateParam)}
            {param.type !== "boolean" ? <small>{param.description}</small> : null}
            <small className="param-guidance">{guidanceText(param)}</small>
          </label>
        ))
      ) : (
        <div className="state">This operation has no parameters.</div>
      )}
    </div>
  );
}
