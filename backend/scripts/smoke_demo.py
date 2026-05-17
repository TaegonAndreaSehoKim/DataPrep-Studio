from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "preprocessing_sample.csv"


def assert_ok(response, label: str) -> dict:
    if response.status_code >= 400:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    if response.status_code == 204:
        return {}
    return response.json()


def main() -> None:
    tempdir = tempfile.TemporaryDirectory()
    root = Path(tempdir.name)
    os.environ["DATABASE_URL"] = f"sqlite:///{root / 'smoke.db'}"
    os.environ["STORAGE_DIR"] = str(root / "storage")
    os.environ["UPLOAD_DIR"] = str(root / "storage" / "uploads")
    os.environ["EXPORT_DIR"] = str(root / "storage" / "exports")

    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.database import reset_database_engine
    from app.main import app

    get_settings.cache_clear()
    reset_database_engine()

    try:
        with TestClient(app) as client:
            health = assert_ok(client.get("/health"), "health")
            print(f"health: {health['status']}")

            project = assert_ok(client.post("/projects", json={"name": "Smoke Demo", "description": "End-to-end local smoke"}), "create project")
            print(f"project: {project['id']}")

            with FIXTURE.open("rb") as handle:
                upload = assert_ok(
                    client.post(
                        f"/projects/{project['id']}/datasets/upload",
                        data={"role": "single"},
                        files={"file": (FIXTURE.name, handle, "text/csv")},
                    ),
                    "upload dataset",
                )
            dataset = upload["dataset"]
            print(f"dataset: {dataset['row_count']} rows, {dataset['column_count']} columns")

            analysis = assert_ok(
                client.post(
                    f"/projects/{project['id']}/analysis/run",
                    json={"target_column": "target", "problem_type": "classification", "mode": "single"},
                ),
                "run analysis",
            )
            print(f"analysis: score={analysis['readiness_score']}")

            pipeline = assert_ok(
                client.post(
                    f"/projects/{project['id']}/pipelines",
                    json={"name": "Smoke Pipeline", "analysis_run_id": analysis["id"], "mode": "single"},
                ),
                "create pipeline",
            )
            assert_ok(
                client.post(
                    f"/pipelines/{pipeline['id']}/steps",
                    json={"operation_type": "numeric_imputation", "columns": ["income"], "params": {"strategy": "median"}},
                ),
                "add imputation step",
            )
            assert_ok(
                client.post(
                    f"/pipelines/{pipeline['id']}/steps",
                    json={"operation_type": "drop_columns", "columns": ["city"], "params": {}},
                ),
                "add drop step",
            )
            preview = assert_ok(client.post(f"/pipelines/{pipeline['id']}/preview", json={"limit": 2}), "preview")
            print(f"preview: {len(preview['step_effects'])} effects")

            run = assert_ok(client.post(f"/pipelines/{pipeline['id']}/apply", json={}), "apply")
            print(f"pipeline_run: {run['id']}")

            config = assert_ok(client.get(f"/pipeline-runs/{run['id']}/download/config"), "download config")
            print(f"config: {len(config['steps'])} steps")

            print("smoke: ok")
    finally:
        reset_database_engine()
        get_settings.cache_clear()
    tempdir.cleanup()


if __name__ == "__main__":
    main()
