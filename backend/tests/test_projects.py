from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_project_crud(client):
    created = client.post("/projects", json={"name": "Demo", "description": "Initial project"})
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Demo"

    listed = client.get("/projects")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/projects/{project['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Initial project"

    updated = client.patch(f"/projects/{project['id']}", json={"name": "Updated"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated"

    deleted = client.delete(f"/projects/{project['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/projects/{project['id']}")
    assert missing.status_code == 404


def test_delete_project_removes_related_records_and_storage(client):
    project = client.post("/projects", json={"name": "Delete with data"}).json()
    with (FIXTURE_DIR / "preprocessing_sample.csv").open("rb") as handle:
        upload = client.post(
            f"/projects/{project['id']}/datasets/upload",
            data={"role": "single"},
            files={"file": ("preprocessing_sample.csv", handle, "text/csv")},
        )
    assert upload.status_code == 201
    upload_path = Path(upload.json()["dataset"]["storage_path"])
    assert upload_path.exists()

    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()
    pipeline = client.post(
        f"/projects/{project['id']}/pipelines",
        json={"name": "delete pipeline", "analysis_run_id": analysis["id"], "mode": "single"},
    ).json()
    client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "numeric_imputation", "columns": ["income"], "params": {"strategy": "median"}},
    )
    run = client.post(f"/pipelines/{pipeline['id']}/apply", json={"limit": 20}).json()
    export_paths = [Path(path) for path in run["output_paths"].values()]
    assert all(path.exists() for path in export_paths)

    deleted = client.delete(f"/projects/{project['id']}")

    assert deleted.status_code == 204
    assert client.get(f"/projects/{project['id']}").status_code == 404
    assert client.get(f"/projects/{project['id']}/datasets").status_code == 404
    assert client.get(f"/pipeline-runs/{run['id']}").status_code == 404
    assert not upload_path.exists()
    assert all(not path.exists() for path in export_paths)
