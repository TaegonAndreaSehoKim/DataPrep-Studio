import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { AnalysisCharts as AnalysisChartsData, ColumnProfile } from "../api/types";
import { AnalysisCharts } from "../components/AnalysisCharts";
import { Card } from "../components/Card";
import { ColumnProfileTable } from "../components/ColumnProfileTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

export function ColumnsPage({ analysisId }: { analysisId: number | null }) {
  const [columns, setColumns] = useState<ColumnProfile[]>([]);
  const [selected, setSelected] = useState<ColumnProfile | null>(null);
  const [charts, setCharts] = useState<AnalysisChartsData | null>(null);
  const [loading, setLoading] = useState(Boolean(analysisId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId) {
      return;
    }
    setLoading(true);
    apiClient
      .listColumns(analysisId)
      .then((items) => {
        setColumns(items);
        setSelected(items[0] ?? null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [analysisId]);

  useEffect(() => {
    if (!analysisId || !selected) {
      setCharts(null);
      return;
    }
    apiClient
      .getColumnCharts(analysisId, selected.column_name)
      .then(setCharts)
      .catch((err: Error) => setError(err.message));
  }, [analysisId, selected]);

  if (!analysisId) {
    return <EmptyState title="No analysis selected" message="Run or select an analysis before viewing columns." />;
  }

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  return (
    <div className="page-stack">
      <Card title="Columns">
        <ColumnProfileTable columns={columns} onSelect={setSelected} />
      </Card>
      {selected ? (
        <Card title={selected.column_name}>
          <pre>{JSON.stringify(selected.summary, null, 2)}</pre>
        </Card>
      ) : (
        <EmptyState title="No columns" message="This analysis did not produce column profiles." />
      )}
      <AnalysisCharts charts={charts} />
    </div>
  );
}
