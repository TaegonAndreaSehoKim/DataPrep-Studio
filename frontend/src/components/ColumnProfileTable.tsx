import type { ColumnProfile } from "../api/types";
import { formatPercent } from "../utils/format";

export function ColumnProfileTable({
  columns,
  onSelect
}: {
  columns: ColumnProfile[];
  onSelect?: (column: ColumnProfile) => void;
}) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Missing</th>
          <th>Unique</th>
          <th>Cardinality</th>
        </tr>
      </thead>
      <tbody>
        {columns.map((column) => (
          <tr key={column.id} onClick={() => onSelect?.(column)}>
            <td>{column.column_name}</td>
            <td>{column.inferred_type}</td>
            <td>{formatPercent(column.missing_rate)}</td>
            <td>{column.unique_count}</td>
            <td>{formatPercent(column.cardinality_ratio)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
