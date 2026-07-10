from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _upload_fixture(client, project_id: int, filename: str = "dirty_missing_values.csv") -> int:
    csv_path = FIXTURE_DIR / filename
    with csv_path.open("rb") as handle:
        response = client.post(
            f"/projects/{project_id}/datasets/upload",
            data={"role": "single"},
            files={"file": (filename, handle, "text/csv")},
        )
    assert response.status_code == 201
    return response.json()["dataset"]["id"]


def test_run_analysis_creates_profiles_issues_and_score(client):
    project = client.post("/projects", json={"name": "Analysis project"}).json()
    _upload_fixture(client, project["id"])

    response = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    )

    assert response.status_code == 201
    analysis = response.json()
    assert analysis["project_id"] == project["id"]
    assert analysis["readiness_score"] < 100
    assert analysis["score_breakdown"]["warning_count"] >= 1

    columns = client.get(f"/analysis/{analysis['id']}/columns")
    assert columns.status_code == 200
    assert {column["column_name"] for column in columns.json()} >= {"age", "income", "city", "target"}

    issues = client.get(f"/analysis/{analysis['id']}/issues")
    assert issues.status_code == 200
    categories = {issue["category"] for issue in issues.json()}
    assert "missingness" in categories
    assert "duplicate" in categories

    score = client.get(f"/analysis/{analysis['id']}/score")
    assert score.status_code == 200
    assert score.json()["score"] == analysis["readiness_score"]


def test_analysis_rejects_missing_target_column(client):
    project = client.post("/projects", json={"name": "Invalid target"}).json()
    _upload_fixture(client, project["id"])

    response = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "does_not_exist", "problem_type": "classification", "mode": "single"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Target column does not exist in the dataset"


def test_analysis_rejects_missing_dataset_state(client):
    project = client.post("/projects", json={"name": "No dataset"}).json()

    single_response = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    )
    train_test_response = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "train_test"},
    )

    assert single_response.status_code == 400
    assert single_response.json()["detail"] == "Project does not have a single dataset upload"
    assert train_test_response.status_code == 400
    assert train_test_response.json()["detail"] == "Project must have train and test dataset uploads"


def test_analysis_overview(client):
    project = client.post("/projects", json={"name": "Overview project"}).json()
    _upload_fixture(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()

    response = client.get(f"/analysis/{analysis['id']}/overview")

    assert response.status_code == 200
    overview = response.json()
    assert overview["row_count"] == 5
    assert overview["column_count"] == 5
    assert overview["column_type_counts"]
    assert overview["target_summary"]["is_target"] is True


def test_list_project_analysis(client):
    project = client.post("/projects", json={"name": "List analysis project"}).json()
    _upload_fixture(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()

    response = client.get(f"/projects/{project['id']}/analysis")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [analysis["id"]]


def test_analysis_charts(client):
    project = client.post("/projects", json={"name": "Chart project"}).json()
    _upload_fixture(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()

    response = client.get(f"/analysis/{analysis['id']}/charts")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"] == analysis["id"]
    assert set(body["charts"]) >= {"issue_severity", "issue_category", "missingness", "cardinality", "inferred_types"}
    assert body["charts"]["missingness"]["chart_type"] == "horizontal_bar"
    assert any(row["label"] == "age" for row in body["charts"]["missingness"]["data"])


def test_preprocessing_recommendations_highlight_actionable_findings(client):
    project = client.post("/projects", json={"name": "Recommendation project"}).json()
    _upload_fixture(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()

    response = client.get(f"/analysis/{analysis['id']}/preprocessing-recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"] == analysis["id"]
    assert body["recommendations"]
    operation_types = {
        item["suggested_step"]["operation_type"]
        for item in body["recommendations"]
        if item["suggested_step"] is not None
    }
    assert "remove_duplicate_rows" in operation_types
    assert "numeric_imputation" in operation_types
    assert any("advisory" in note for note in body["notes"])


def test_analysis_report_download_contains_rich_findings(client):
    project = client.post("/projects", json={"name": "Report project"}).json()
    _upload_fixture(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()

    response = client.get(f"/analysis/{analysis['id']}/download/report")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "analysis_" in response.headers["content-disposition"]
    text = response.text
    assert "# DataPrep Studio Analysis Report" in text
    assert "## Executive Summary" in text
    assert "## Issue Summary" in text
    assert "## Preprocessing Recommendations" in text
    assert "## Column Profile Details" in text
    assert "## Chart Data Summary" in text
    assert "Readiness score" in text
    assert "numeric_imputation" in text
    assert "dirty_missing_values.csv" in text


def test_analysis_applies_missing_tokens_and_type_overrides(client):
    project = client.post("/projects", json={"name": "Setup overrides"}).json()
    csv_path = FIXTURE_DIR / "user_setup_overrides.csv"
    with csv_path.open("rb") as handle:
        upload = client.post(
            f"/projects/{project['id']}/datasets/upload",
            data={"role": "single"},
            files={"file": ("user_setup_overrides.csv", handle, "text/csv")},
        )
    assert upload.status_code == 201

    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={
            "target_column": "score",
            "problem_type": "classification",
            "mode": "single",
            "column_type_overrides": {"zip_code": "categorical", "notes": "text"},
            "missing_value_tokens": ["?", "unknown"],
        },
    ).json()

    columns = client.get(f"/analysis/{analysis['id']}/columns").json()
    by_name = {column["column_name"]: column for column in columns}
    assert by_name["zip_code"]["inferred_type"] == "categorical"
    assert "user_type_override" in by_name["zip_code"]["warnings"]
    assert by_name["notes"]["missing_count"] == 2
    assert by_name["score"]["summary"]["class_counts"] == {"1": 2, "2": 1, "3": 1}


def test_dataset_config_can_drive_analysis(client):
    project = client.post("/projects", json={"name": "Saved setup"}).json()
    dataset_id = _upload_fixture(client, project["id"], "user_setup_overrides.csv")
    config = client.post(
        f"/projects/{project['id']}/dataset-configs",
        json={
            "name": "classification setup",
            "dataset_file_id": dataset_id,
            "target_column": "score",
            "problem_type": "classification",
            "mode": "single",
            "column_type_overrides": {"zip_code": "categorical"},
            "missing_value_tokens": ["?", "unknown"],
            "ignored_columns": ["notes"],
        },
    )
    assert config.status_code == 201

    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"dataset_config_id": config.json()["id"]},
    )

    assert analysis.status_code == 201
    columns = client.get(f"/analysis/{analysis.json()['id']}/columns").json()
    by_name = {column["column_name"]: column for column in columns}
    assert "notes" not in by_name
    assert by_name["zip_code"]["inferred_type"] == "categorical"
    assert by_name["score"]["summary"]["class_counts"] == {"1": 2, "2": 1, "3": 1}

    updated = client.patch(
        f"/dataset-configs/{config.json()['id']}",
        json={"name": "updated setup", "ignored_columns": []},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "updated setup"

    listed = client.get(f"/projects/{project['id']}/dataset-configs")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "updated setup"

    suggestions = client.get(f"/datasets/{dataset_id}/setup-suggestions")
    assert suggestions.status_code == 200
    assert suggestions.json()["column_type_overrides"]["zip_code"] == "categorical"
    assert set(suggestions.json()["missing_value_tokens"]) >= {"?", "unknown"}


def test_column_charts(client):
    project = client.post("/projects", json={"name": "Column chart project"}).json()
    _upload_fixture(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()

    response = client.get(f"/analysis/{analysis['id']}/columns/city/charts")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"] == analysis["id"]
    assert "missingness" in body["charts"]
    assert "top_values" in body["charts"]
    assert body["charts"]["missingness"]["data"] == [
        {"label": "missing", "value": 0},
        {"label": "present", "value": 5},
    ]
