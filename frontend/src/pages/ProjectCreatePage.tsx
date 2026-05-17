import { FormEvent, useState } from "react";

import { apiClient } from "../api/client";
import type { Project } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { ErrorState } from "../components/ErrorState";

export function ProjectCreatePage({ onCreated }: { onCreated: (project: Project) => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const project = await apiClient.createProject({ name, description });
      onCreated(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Create Project">
      <form className="form" onSubmit={handleSubmit}>
        {error ? <ErrorState message={error} /> : null}
        <label>
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          <span>Description</span>
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <Button type="submit" disabled={saving}>
          {saving ? "Creating" : "Create Project"}
        </Button>
      </form>
    </Card>
  );
}
