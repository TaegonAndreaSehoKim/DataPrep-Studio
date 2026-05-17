def _project_id(client) -> int:
    response = client.post("/projects", json={"name": "Pipeline project"})
    assert response.status_code == 201
    return response.json()["id"]


def test_operation_metadata_contains_core_operations(client):
    response = client.get("/pipeline/operations")

    assert response.status_code == 200
    operations = {operation["operation_type"] for operation in response.json()}
    assert "numeric_imputation" in operations
    assert "one_hot_encoding" in operations
    assert "numeric_scaling" in operations
    assert "outlier_clipping" in operations
    assert len(operations) >= 17


def test_pipeline_and_step_crud(client):
    project_id = _project_id(client)

    created = client.post(
        f"/projects/{project_id}/pipelines",
        json={"name": "baseline preprocessing", "description": "demo", "mode": "single"},
    )
    assert created.status_code == 201
    pipeline = created.json()
    assert pipeline["name"] == "baseline preprocessing"
    assert pipeline["steps"] == []

    first = client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "numeric_imputation", "columns": ["age"], "params": {"strategy": "median"}},
    )
    assert first.status_code == 201
    first_step = first.json()
    assert first_step["order_index"] == 0

    second = client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "drop_columns", "columns": ["id"], "params": {}},
    )
    second_step = second.json()
    assert second_step["order_index"] == 1

    fetched = client.get(f"/pipelines/{pipeline['id']}")
    assert fetched.status_code == 200
    assert [step["operation_type"] for step in fetched.json()["steps"]] == ["numeric_imputation", "drop_columns"]

    updated = client.patch(
        f"/pipelines/{pipeline['id']}/steps/{first_step['id']}",
        json={"params": {"strategy": "mean"}, "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["params"] == {"strategy": "mean"}
    assert updated.json()["enabled"] is False

    toggled = client.post(f"/pipelines/{pipeline['id']}/steps/{first_step['id']}/toggle")
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is True

    reordered = client.post(
        f"/pipelines/{pipeline['id']}/steps/reorder",
        json={"step_ids": [second_step["id"], first_step["id"]]},
    )
    assert reordered.status_code == 200
    assert [step["id"] for step in reordered.json()["steps"]] == [second_step["id"], first_step["id"]]
    assert [step["order_index"] for step in reordered.json()["steps"]] == [0, 1]

    deleted_step = client.delete(f"/pipelines/{pipeline['id']}/steps/{second_step['id']}")
    assert deleted_step.status_code == 204
    remaining = client.get(f"/pipelines/{pipeline['id']}").json()["steps"]
    assert len(remaining) == 1
    assert remaining[0]["order_index"] == 0

    deleted_pipeline = client.delete(f"/pipelines/{pipeline['id']}")
    assert deleted_pipeline.status_code == 204
    assert client.get(f"/pipelines/{pipeline['id']}").status_code == 404


def test_create_pipeline_rejects_invalid_project(client):
    response = client.post("/projects/999/pipelines", json={"name": "bad", "mode": "single"})

    assert response.status_code == 404


def test_issue_suggestion_and_pipeline_validation(client):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "dirty_missing_values.csv"
    project = client.post("/projects", json={"name": "Issue suggestions"}).json()
    with fixture.open("rb") as handle:
        upload = client.post(
            f"/projects/{project['id']}/datasets/upload",
            data={"role": "single"},
            files={"file": ("dirty_missing_values.csv", handle, "text/csv")},
        )
    assert upload.status_code == 201
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()
    pipeline = client.post(
        f"/projects/{project['id']}/pipelines",
        json={"name": "suggested", "analysis_run_id": analysis["id"], "mode": "single"},
    ).json()
    issues = client.get(f"/analysis/{analysis['id']}/issues").json()
    missing_issue = next(issue for issue in issues if issue["category"] == "missingness" and issue["affected_columns"])

    suggestion = client.get(f"/issues/{missing_issue['id']}/suggested-step")
    assert suggestion.status_code == 200
    assert suggestion.json()["operation_type"] in {"numeric_imputation", "categorical_imputation", "replace_placeholder_values"}

    step = client.post(f"/pipelines/{pipeline['id']}/steps/from-issue/{missing_issue['id']}")
    assert step.status_code == 201

    validation = client.post(f"/pipelines/{pipeline['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "numeric_imputation", "columns": ["city"], "params": {"strategy": "median"}},
    )
    invalid = client.post(f"/pipelines/{pipeline['id']}/validate")
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert any("city" in issue["message"] for issue in invalid.json()["issues"])

    empty_step_project = client.post("/projects", json={"name": "Empty step validation"}).json()
    empty_pipeline = client.post(
        f"/projects/{empty_step_project['id']}/pipelines",
        json={"name": "empty", "mode": "single"},
    ).json()
    client.post(
        f"/pipelines/{empty_pipeline['id']}/steps",
        json={"operation_type": "numeric_imputation", "columns": [], "params": {"strategy": "median"}},
    )
    empty_validation = client.post(f"/pipelines/{empty_pipeline['id']}/validate")
    assert empty_validation.status_code == 200
    assert empty_validation.json()["valid"] is False
    assert any("requires at least one selected column" in issue["message"] for issue in empty_validation.json()["issues"])


def test_create_suggested_pipeline_from_analysis(client):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "dirty_missing_values.csv"
    project = client.post("/projects", json={"name": "Suggested pipeline"}).json()
    with fixture.open("rb") as handle:
        upload = client.post(
            f"/projects/{project['id']}/datasets/upload",
            data={"role": "single"},
            files={"file": ("dirty_missing_values.csv", handle, "text/csv")},
        )
    assert upload.status_code == 201
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={
            "target_column": "target",
            "problem_type": "classification",
            "mode": "single",
            "missing_value_tokens": ["N/A", "unknown", "?"],
        },
    ).json()

    response = client.post(
        f"/projects/{project['id']}/pipelines/from-analysis/{analysis['id']}",
        json={"name": "auto draft"},
    )

    assert response.status_code == 201
    pipeline = response.json()
    assert pipeline["name"] == "auto draft"
    operation_types = [step["operation_type"] for step in pipeline["steps"]]
    assert "remove_duplicate_rows" in operation_types
    assert "numeric_imputation" in operation_types
    assert len(operation_types) == len(set((step["operation_type"], str(step["params"])) for step in pipeline["steps"]))

    validation = client.post(f"/pipelines/{pipeline['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
