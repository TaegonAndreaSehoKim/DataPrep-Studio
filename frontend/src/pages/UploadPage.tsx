import { FormEvent, useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { DatasetFile, DatasetPreview, Project } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

export function UploadPage({
  selectedProjectId,
  onUploaded,
  onAnalyzeReady
}: {
  selectedProjectId: number | null;
  onUploaded: (projectId: number, dataset: DatasetFile) => void;
  onAnalyzeReady: (projectId: number) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [role, setRole] = useState<DatasetFile["role"]>("single");
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState<DatasetFile | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .listProjects()
      .then((items) => {
        setProjects(items);
        if (items.length) {
          const selected = selectedProjectId && items.some((item) => item.id === selectedProjectId) ? selectedProjectId : items[0].id;
          setProjectId(String(selected));
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedProjectId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !projectId) {
      setError("Choose a project and CSV file before uploading.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const response = await apiClient.uploadDataset({ projectId: Number(projectId), role, file });
      setUploaded(response.dataset);
      const nextPreview = await apiClient.previewDataset(response.dataset.id, 5);
      setPreview(nextPreview);
      onUploaded(Number(projectId), response.dataset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <LoadingState />;
  }

  if (!projects.length) {
    return <EmptyState title="No projects" message="Create a project before uploading datasets." />;
  }

  return (
    <Card title="Upload Dataset">
      <form className="form" onSubmit={handleSubmit}>
        {error ? <ErrorState message={error} /> : null}
        <label>
          <span>Project</span>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Dataset Role</span>
          <select value={role} onChange={(event) => setRole(event.target.value as DatasetFile["role"])}>
            <option value="single">Single dataset</option>
            <option value="train">Train dataset</option>
            <option value="test">Test dataset</option>
          </select>
        </label>
        <label>
          <span>CSV File</span>
          <input type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        <Button type="submit" disabled={saving}>
          {saving ? "Uploading" : "Upload CSV"}
        </Button>
      </form>
      {uploaded ? (
        <div className="upload-result upload-complete">
          <div>
            <strong>Upload complete: {uploaded.filename}</strong>
            <span>
              {uploaded.role} / {uploaded.row_count} rows / {uploaded.column_count} columns
            </span>
          </div>
          <div className="toolbar no-margin">
            <Button variant="secondary" onClick={() => onAnalyzeReady(uploaded.project_id)}>
              Run Analysis
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setUploaded(null);
                setPreview(null);
                setFile(null);
              }}
            >
              Upload Another
            </Button>
          </div>
        </div>
      ) : null}
      {preview ? (
        <div className="preview-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {preview.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row, index) => (
                <tr key={index}>
                  {preview.columns.map((column) => (
                    <td key={column}>{String(row[column] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Card>
  );
}
