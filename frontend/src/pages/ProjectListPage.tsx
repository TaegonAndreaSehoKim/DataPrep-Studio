import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { Project } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

export function ProjectListPage({
  onCreateProject,
  onSelectProject,
  onProjectDeleted
}: {
  onCreateProject: () => void;
  onSelectProject: (projectId: number) => void;
  onProjectDeleted: (projectId: number) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .listProjects()
      .then(setProjects)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function deleteProject(project: Project) {
    setDeletingId(project.id);
    setError(null);
    try {
      await apiClient.deleteProject(project.id);
      setProjects((current) => current.filter((item) => item.id !== project.id));
      setConfirmingDeleteId(null);
      onProjectDeleted(project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project");
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  return (
    <Card title="Projects">
      <div className="card-actions">
        <Button onClick={onCreateProject}>Create Project</Button>
      </div>
      {projects.length ? (
        <div className="list">
          {projects.map((project) => (
            <div className="list-row project-row" key={project.id}>
              <button className="list-button row-main-button" onClick={() => onSelectProject(project.id)}>
                <strong>{project.name}</strong>
                <span>{project.description || "No description"}</span>
              </button>
              {confirmingDeleteId === project.id ? (
                <div className="row-actions danger-actions">
                  <span>Delete this project and its local records?</span>
                  <Button variant="secondary" disabled={deletingId === project.id} onClick={() => setConfirmingDeleteId(null)}>
                    Cancel
                  </Button>
                  <Button variant="ghost" disabled={deletingId === project.id} onClick={() => deleteProject(project)}>
                    {deletingId === project.id ? "Deleting" : "Confirm Delete"}
                  </Button>
                </div>
              ) : (
                <div className="row-actions">
                  <Button variant="ghost" disabled={deletingId === project.id} onClick={() => setConfirmingDeleteId(project.id)}>
                    Delete
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No projects" message="Create a project to upload and analyze datasets." />
      )}
    </Card>
  );
}
