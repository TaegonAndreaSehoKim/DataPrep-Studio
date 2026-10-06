from pathlib import Path

import pytest


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
    assert body["charts"]["analysis_id"] == analysis["id"]
    assert set(body["charts"]["charts"]) >= {"shape_change", "missing_rate_change"}

    charts = client.post(f"/pipelines/{pipeline['id']}/preview/charts", json={"limit": 2})
    assert charts.status_code == 200
    assert set(charts.json()["charts"]) >= {"shape_change", "missing_rate_change"}
    assert charts.json() == body["charts"]


@pytest.mark.parametrize("mode", ["single", "train_test"])
def test_preview_returns_charts_without_reexecuting_transformations(client, monkeypatch, mode):
    from app.services import pipeline_engine

    project_id = client.post("/projects", json={"name": "Preview computation"}).json()["id"]
    for role in (["single"] if mode == "single" else ["train", "test"]):
        assert client.post(f"/projects/{project_id}/datasets/upload", data={"role": role}, files={"file": (f"{role}.csv", b"value\n1\n2\n3\n", "text/csv")}).status_code == 201
    pipeline_id = client.post(f"/projects/{project_id}/pipelines", json={"name": "One pass", "mode": mode}).json()["id"]
    assert client.post(f"/pipelines/{pipeline_id}/steps", json={"operation_type": "numeric_scaling", "columns": ["value"]}).status_code == 201
    calls = []
    original = pipeline_engine.fit_transform_step

    def tracked(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline_engine, "fit_transform_step", tracked)
    response = client.post(f"/pipelines/{pipeline_id}/preview")
    assert response.status_code == 200
    assert calls == ["numeric_scaling"]
    assert response.json()["charts"]["charts"]["shape_change"]["data"]


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


def test_pipeline_preview_rejects_invalid_operation_params(client):
    project = client.post("/projects", json={"name": "Invalid params preview"}).json()
    _upload(client, project["id"])
    analysis = client.post(
        f"/projects/{project['id']}/analysis/run",
        json={"target_column": "target", "problem_type": "classification", "mode": "single"},
    ).json()
    pipeline = client.post(
        f"/projects/{project['id']}/pipelines",
        json={"name": "bad params", "analysis_run_id": analysis["id"], "mode": "single"},
    ).json()
    client.post(
        f"/pipelines/{pipeline['id']}/steps",
        json={"operation_type": "numeric_imputation", "columns": ["income"], "params": {"strategy": "mode"}},
    )

    validation = client.post(f"/pipelines/{pipeline['id']}/validate")
    response = client.post(f"/pipelines/{pipeline['id']}/preview", json={"limit": 2})

    assert validation.status_code == 200
    assert validation.json()["valid"] is False
    assert any("Param strategy must be one of" in issue["message"] for issue in validation.json()["issues"])
    assert response.status_code == 400
    assert "Param strategy must be one of" in response.json()["detail"]


@pytest.mark.parametrize("operation,params,message", [
    ("numeric_scaling", {"method": "minmax", "feature_range": [1]}, "two finite numbers"),
    ("numeric_scaling", {"feature_range": [2, 1]}, "less than upper"),
    ("numeric_scaling", {"quantile_range": [-1, 75]}, "within 0 and 100"),
    ("numeric_scaling", {"method": None}, "cannot be null"),
    ("numeric_imputation", {"strategy": "constant", "fill_value": None}, "finite fill_value"),
    ("outlier_clipping", {"lower_percentile": 99, "upper_percentile": 1}, "Clipping percentiles"),
    ("outlier_clipping", {"iqr_multiplier": "oops"}, "must be number"),
    ("one_hot_encoding", {"max_categories": -1}, "positive integer"),
    ("one_hot_encoding", {"drop_first": "false"}, "must be boolean"),
    ("rare_category_grouping", {"min_frequency": 2}, "within 0 and 1"),
    ("rare_category_grouping", {"min_count": 1.5}, "positive integer"),
    ("datetime_extract", {"features": ["unknown"]}, "supports only"),
    ("ordinal_encoding", {"categories_order": {"income": "A"}}, "lists of strings"),
])
def test_validation_preview_apply_share_parameter_errors(client, operation, params, message):
    project_id = client.post("/projects", json={"name": "Parameter validation"}).json()["id"]
    _upload(client, project_id)
    pipeline_id = client.post(f"/projects/{project_id}/pipelines", json={"name": "Editable draft"}).json()["id"]
    response = client.post(f"/pipelines/{pipeline_id}/steps", json={
        "operation_type": operation, "columns": ["income"], "params": params,
    })
    assert response.status_code == 201
    validation = client.post(f"/pipelines/{pipeline_id}/validate").json()
    assert validation["valid"] is False
    assert any(message in issue["message"] for issue in validation["issues"])
    for action in ["preview", "apply"]:
        response = client.post(f"/pipelines/{pipeline_id}/{action}")
        assert response.status_code == 400
        assert message in response.json()["detail"]
    assert client.get(f"/projects/{project_id}/pipeline-runs").json() == []
