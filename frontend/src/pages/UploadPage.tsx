import { FormEvent, useEffect, useRef, useState } from "react";

import { apiClient } from "../api/client";
import type { DatasetFile, DatasetPreview, Project } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

export function UploadPage({
  selectedProjectId,
  onProjectSelected,
  onUploaded,
  onAnalyzeReady
}: {
  selectedProjectId: number | null;
  onProjectSelected: (projectId: number) => void;
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
  const mountedRef = useRef(true);
  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, []);

  useEffect(() => {
    let active = true;
    apiClient
      .listProjects()
      .then((items) => {
        if (!active) return;
        setProjects(items);
        if (items.length) {
          const selected = selectedProjectId && items.some((item) => item.id === selectedProjectId) ? selectedProjectId : items[0].id;
          setProjectId(String(selected));
          if (selected !== selectedProjectId) onProjectSelected(selected);
        }
      })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedProjectId, onProjectSelected]);

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
      if (!mountedRef.current) return;
      setUploaded(response.dataset);
      const nextPreview = await apiClient.previewDataset(response.dataset.id, 5);
      if (!mountedRef.current) return;
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
          <select value={projectId} disabled={saving} onChange={(event) => onProjectSelected(Number(event.target.value))}>
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
