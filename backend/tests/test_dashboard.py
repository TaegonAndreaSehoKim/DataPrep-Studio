from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_dashboard_counts_and_recent_runs(client):
    project = client.post("/projects", json={"name": "Dashboard project"}).json()
    with (FIXTURE_DIR / "preprocessing_sample.csv").open("rb") as handle:
        client.post(
            f"/projects/{project['id']}/datasets/upload",
            data={"role": "single"},
            files={"file": ("preprocessing_sample.csv", handle, "text/csv")},
        )
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()
    pipeline = client.post(
        f"/projects/{project['id']}/pipelines",
        json={"name": "dashboard pipeline", "analysis_run_id": analysis["id"], "mode": "single"},
    ).json()
    run = client.post(f"/pipelines/{pipeline['id']}/apply", json={}).json()

    response = client.get("/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["project_count"] == 1
    assert body["dataset_count"] == 1
    assert body["analysis_count"] == 1
    assert body["pipeline_count"] == 1
    assert body["recent_projects"][0]["id"] == project["id"]
    assert body["recent_analysis_runs"][0]["id"] == analysis["id"]
    assert body["recent_pipeline_runs"][0]["id"] == run["id"]
