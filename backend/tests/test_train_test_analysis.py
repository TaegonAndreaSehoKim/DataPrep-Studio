from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _upload(client, project_id: int, role: str, filename: str) -> None:
    with (FIXTURE_DIR / filename).open("rb") as handle:
        response = client.post(
            f"/projects/{project_id}/datasets/upload",
            data={"role": role},
            files={"file": (filename, handle, "text/csv")},
        )
    assert response.status_code == 201


def test_train_test_analysis_persists_comparison(client):
    project = client.post("/projects", json={"name": "Train test project"}).json()
    _upload(client, project["id"], "train", "train_drift.csv")
    _upload(client, project["id"], "test", "test_drift.csv")

    response = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "train_test"},
    )

    assert response.status_code == 201
    analysis = response.json()
    assert analysis["readiness_score"] < 100

    columns = client.get(f"/analysis/{analysis['id']}/columns").json()
    roles = {column["dataset_role"] for column in columns}
    assert roles == {"train", "test"}

    comparison = client.get(f"/analysis/{analysis['id']}/train-test-comparison")
    assert comparison.status_code == 200
    body = comparison.json()
    assert body["drift_score"] > 0
    assert body["summary"]["columns"]["city"]["unseen_category_count"] == 2

    charts = client.get(f"/analysis/{analysis['id']}/charts")
    assert charts.status_code == 200
    assert "train_test_drift" in charts.json()["charts"]


def test_train_test_analysis_requires_pair(client):
    project = client.post("/projects", json={"name": "Missing pair"}).json()
    _upload(client, project["id"], "train", "train_drift.csv")

    response = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "train_test"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Project must have train and test dataset uploads"


def test_distribution_drift_metrics_persist_and_appear_in_charts(client):
    project_id = client.post("/projects", json={"name": "Distribution drift"}).json()["id"]
    for role, scale in [("train", 1), ("test", 10)]:
        csv = "value,target\n" + "".join(f"{value * scale},{index % 2}\n" for index, value in enumerate([-1, 1] * 20))
        assert client.post(f"/projects/{project_id}/datasets/upload", data={"role": role}, files={"file": (f"{role}.csv", csv.encode(), "text/csv")}).status_code == 201
    response = client.post(f"/projects/{project_id}/analysis/run", json={"mode": "train_test", "target_column": "target", "problem_type": "classification", "column_type_overrides": {"value": "numeric"}})
    assert response.status_code == 201
    analysis_id = response.json()["id"]
    comparison = client.get(f"/analysis/{analysis_id}/train-test-comparison").json()
    assert comparison["summary"]["columns"]["value"]["variance_shift_flag"]
    chart = client.get(f"/analysis/{analysis_id}/charts").json()["charts"]["train_test_drift"]
    assert next(row["value"] for row in chart["data"] if row["label"] == "value") == 50
