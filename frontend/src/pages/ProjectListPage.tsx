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
  onSelectProject
}: {
  onCreateProject: () => void;
  onSelectProject: (projectId: number) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .listProjects()
      .then(setProjects)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

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
            <button className="list-row list-button" key={project.id} onClick={() => onSelectProject(project.id)}>
              <strong>{project.name}</strong>
              <span>{project.description || "No description"}</span>
            </button>
          ))}
        </div>
      ) : (
        <EmptyState title="No projects" message="Create a project to upload and analyze datasets." />
      )}
    </Card>
  );
}
