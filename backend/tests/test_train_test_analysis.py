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
