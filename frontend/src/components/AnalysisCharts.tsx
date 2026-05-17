import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { AnalysisCharts as AnalysisChartsData, ChartData } from "../api/types";
import { Card } from "./Card";
import { EmptyState } from "./EmptyState";

function valueFormatter(value: unknown): string | number {
  return typeof value === "number" ? Number(value.toFixed(4)) : String(value ?? "");
}

function ChartPanel({ chart }: { chart: ChartData }) {
  if (!chart.data.length) {
    return <EmptyState title={chart.title} message="No chart data available." />;
  }

  const height = chart.chart_type === "horizontal_bar" ? Math.max(220, chart.data.length * 32) : 260;
  const layout = chart.chart_type === "horizontal_bar" ? "vertical" : "horizontal";

  return (
    <div className="chart-panel">
      <div className="chart-heading">
        <h3>{chart.title}</h3>
        {chart.description ? <p>{chart.description}</p> : null}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chart.data} layout={layout} margin={{ top: 8, right: 20, bottom: 8, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          {chart.chart_type === "horizontal_bar" ? (
            <>
              <XAxis type="number" tickFormatter={(value) => String(valueFormatter(value))} />
              <YAxis dataKey="label" type="category" width={120} />
            </>
          ) : (
            <>
              <XAxis dataKey="label" />
              <YAxis tickFormatter={(value) => String(valueFormatter(value))} />
            </>
          )}
          <Tooltip formatter={(value) => valueFormatter(value)} />
          <Bar dataKey="value" fill="#1f7a55" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AnalysisCharts({ charts }: { charts: AnalysisChartsData | null }) {
  if (!charts) {
    return null;
  }

  const orderedKeys = [
    "issue_severity",
    "issue_category",
    "missingness",
    "cardinality",
    "inferred_types",
    "train_test_drift",
    "numeric_summary",
    "top_values",
    "class_balance",
    "shape_change",
    "missing_rate_change"
  ].filter((key) => charts.charts[key]);
  const remainingKeys = Object.keys(charts.charts).filter((key) => !orderedKeys.includes(key));

  return (
    <Card title="Charts">
      <div className="chart-grid">
        {[...orderedKeys, ...remainingKeys].map((key) => (
          <ChartPanel chart={charts.charts[key]} key={key} />
        ))}
      </div>
    </Card>
  );
}
