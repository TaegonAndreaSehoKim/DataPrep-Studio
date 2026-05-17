from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _upload(client, project_id: int, filename: str = "preprocessing_sample.csv") -> None:
    with (FIXTURE_DIR / filename).open("rb") as handle:
        response = client.post(
            f"/projects/{project_id}/datasets/upload",
            data={"role": "single"},
            files={"file": (filename, handle, "text/csv")},
        )
    assert response.status_code == 201


def test_pipeline_preview_returns_before_after_and_step_effects(client):
    project = client.post("/projects", json={"name": "Preview project"}).json()
    _upload(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()
    pipeline = client.post(
        f"/projects/{project['id']}/pipelines",
        json={"name": "preview pipeline", "analysis_run_id": analysis["id"], "mode": "single"},
    ).json()
    client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "numeric_imputation", "columns": ["income"], "params": {"strategy": "median"}},
    )
    client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "drop_columns", "columns": ["city"], "params": {}},
    )

    response = client.post(f"/pipelines/{pipeline['id']}/preview", json={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["before_summary"]["column_count"] == 4
    assert body["after_summary"]["column_count"] == 3
    assert len(body["before_sample_rows"]) == 2
    assert len(body["sample_rows"]) == 2
    assert body["before_sample_rows"][1]["income"] is None
    assert body["sample_rows"][1]["income"] is not None
    assert "city" in body["before_sample_rows"][0]
    assert "city" not in body["sample_rows"][0]
    assert len(body["step_effects"]) == 2
    assert body["affected_columns"] == ["city", "income"]
    diffs = {diff["column_name"]: diff for diff in body["column_diffs"]}
    assert diffs["income"]["status"] == "changed"
    assert diffs["income"]["before_missing_count"] == 1
    assert diffs["income"]["after_missing_count"] == 0
    assert diffs["income"]["changed_sample_count"] == 1
    assert diffs["city"]["status"] == "removed"

    charts = client.post(f"/pipelines/{pipeline['id']}/preview/charts", json={"limit": 2})
    assert charts.status_code == 200
    assert set(charts.json()["charts"]) >= {"shape_change", "missing_rate_change"}


def test_pipeline_preview_returns_validation_error(client):
    project = client.post("/projects", json={"name": "Bad preview project"}).json()
    _upload(client, project["id"])
    pipeline = client.post(f"/projects/{project['id']}/pipelines", json={"name": "bad", "mode": "single"}).json()
    client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "numeric_imputation", "columns": ["missing_column"], "params": {"strategy": "median"}},
    )

    response = client.post(f"/pipelines/{pipeline['id']}/preview", json={"limit": 2})

    assert response.status_code == 400
    assert "missing_column" in response.json()["detail"]
