from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _create_project(client) -> int:
    response = client.post("/projects", json={"name": "Dataset project"})
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_csv_and_preview(client):
    project_id = _create_project(client)
    csv_path = FIXTURE_DIR / "preprocessing_sample.csv"

    with csv_path.open("rb") as handle:
        response = client.post(
            f"/projects/{project_id}/datasets/upload",
            data={"role": "single"},
            files={"file": ("preprocessing_sample.csv", handle, "text/csv")},
        )

    assert response.status_code == 201
    dataset = response.json()["dataset"]
    assert dataset["role"] == "single"
    assert dataset["row_count"] == 4
    assert dataset["column_count"] == 4
    assert dataset["columns"] == ["age", "income", "city", "target"]

    listed = client.get(f"/projects/{project_id}/datasets")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    preview = client.get(f"/datasets/{dataset['id']}/preview?limit=2")
    assert preview.status_code == 200
    body = preview.json()
    assert body["columns"] == ["age", "income", "city", "target"]
    assert body["row_count"] == 4
    assert len(body["rows"]) == 2
    assert body["rows"][0]["city"] == "Seattle"

    suggestions = client.get(f"/datasets/{dataset['id']}/setup-suggestions")
    assert suggestions.status_code == 200
    suggestion_body = suggestions.json()
    assert suggestion_body["recommended_target_column"] == "target"
    assert suggestion_body["recommended_problem_type"] == "classification"
    assert suggestion_body["target_candidates"][0]["column_name"] == "target"


def test_upload_rejects_non_csv(client):
    project_id = _create_project(client)

    response = client.post(
        f"/projects/{project_id}/datasets/upload",
        data={"role": "single"},
        files={"file": ("notes.txt", b"not,a,csv", "text/plain")},
    )

    assert response.status_code == 400
    assert "Only .csv files" in response.json()["detail"]


def test_upload_rejects_invalid_project(client):
    csv_path = FIXTURE_DIR / "preprocessing_sample.csv"

    with csv_path.open("rb") as handle:
        response = client.post(
            "/projects/999/datasets/upload",
            data={"role": "single"},
            files={"file": ("preprocessing_sample.csv", handle, "text/csv")},
        )

    assert response.status_code == 404


def test_delete_dataset_removes_record(client):
    project_id = _create_project(client)
    csv_path = FIXTURE_DIR / "preprocessing_sample.csv"

    with csv_path.open("rb") as handle:
        uploaded = client.post(
            f"/projects/{project_id}/datasets/upload",
            data={"role": "single"},
            files={"file": ("preprocessing_sample.csv", handle, "text/csv")},
        )
    dataset_id = uploaded.json()["dataset"]["id"]

    deleted = client.delete(f"/datasets/{dataset_id}")
    assert deleted.status_code == 204

    missing = client.get(f"/datasets/{dataset_id}")
    assert missing.status_code == 404
