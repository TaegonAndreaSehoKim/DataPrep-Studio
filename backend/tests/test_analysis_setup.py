import json
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine

from app.database import migrate_database


def upload(client, project_id, role, csv):
    response = client.post(f"/projects/{project_id}/datasets/upload", data={"role": role},
                           files={"file": (f"{role}.csv", csv.encode(), "text/csv")})
    assert response.status_code == 201
    return response.json()["dataset"]


def test_analysis_snapshot_survives_config_edits_and_deletion(client):
    project_id = client.post("/projects", json={"name": "Snapshot"}).json()["id"]
    dataset = upload(client, project_id, "single", "age,notes,target\n10,a,0\n ?,b,1\n30,c,0\n")
    config = client.post(f"/projects/{project_id}/dataset-configs", json={
        "name": "Original", "dataset_file_id": dataset["id"], "target_column": "target",
        "problem_type": "classification", "missing_value_tokens": [" ? ", "?"],
        "ignored_columns": ["notes"], "column_type_overrides": {"age": "numeric"},
    }).json()
    response = client.post(f"/projects/{project_id}/analysis/run", json={"dataset_config_id": config["id"]})
    assert response.status_code == 201
    analysis = response.json()
    expected = {"dataset_config_id": config["id"], "mode": "single", "missing_value_tokens": ["?"],
                "ignored_columns": ["notes"], "column_type_overrides": {"age": "numeric"}}
    assert analysis["options"] == expected
    assert client.patch(f"/dataset-configs/{config['id']}", json={"missing_value_tokens": [], "ignored_columns": [], "column_type_overrides": {}}).status_code == 200
    assert client.delete(f"/dataset-configs/{config['id']}").status_code == 204
    assert client.get(f"/analysis/{analysis['id']}").json()["options"] == expected
    assert client.get(f"/projects/{project_id}/analysis").json()[0]["options"] == expected
    assert client.get(f"/analysis/{analysis['id']}/overview").json()["analysis_run"]["options"] == expected
    assert client.get("/dashboard").json()["recent_analysis_runs"][0]["options"] == expected
    report = client.get(f"/analysis/{analysis['id']}/download/report").text
    assert "Analysis Setup Snapshot" in report and '"notes"' in report


@pytest.mark.parametrize("mode", ["single", "train_test"])
def test_explicit_setup_steps_align_analysis_pipeline_and_code(client, mode):
    project_id = client.post("/projects", json={"name": "Explicit setup"}).json()["id"]
    inputs = {"single" if mode == "single" else "train": "age,notes,target\n10,a,0\n ?,b,1\n30,c,0\n"}
    if mode == "train_test":
        inputs["test"] = "age,notes,target\n ?,d,0\n9000,e,1\n"
    sources = {role: upload(client, project_id, role, csv) for role, csv in inputs.items()}
    source_bytes = {role: Path(dataset["storage_path"]).read_bytes() for role, dataset in sources.items()}
    analysis = client.post(f"/projects/{project_id}/analysis/run", json={
        "target_column": "target", "problem_type": "classification", "mode": mode,
        "missing_value_tokens": ["?"], "ignored_columns": ["notes"], "column_type_overrides": {"age": "numeric"},
    }).json()
    profiles = client.get(f"/analysis/{analysis['id']}/columns").json()
    assert all(profile["column_name"] != "notes" for profile in profiles)
    assert profiles[0]["missing_count"] == 1
    pipeline_id = client.post(f"/projects/{project_id}/pipelines", json={
        "name": "Explicit setup", "analysis_run_id": analysis["id"], "mode": mode,
    }).json()["id"]
    for operation, params in [("add_missing_indicator", {}), ("numeric_imputation", {"strategy": "mean"})]:
        assert client.post(f"/pipelines/{pipeline_id}/steps", json={"operation_type": operation, "columns": ["age"], "params": params}).status_code == 201
    # Raw pipelines keep raw-input semantics until the user explicitly adds setup steps.
    raw_run = client.post(f"/pipelines/{pipeline_id}/apply").json()
    raw_key = "cleaned-single" if mode == "single" else "cleaned-train"
    raw = pd.read_csv(StringIO(client.get(f"/pipeline-runs/{raw_run['id']}/download/{raw_key}").text))
    assert "notes" in raw.columns and raw["age_was_missing"].tolist() == [0, 0, 0]
    response = client.post(f"/pipelines/{pipeline_id}/analysis-setup")
    assert response.status_code == 200
    steps = response.json()["steps"]
    assert [step["operation_type"] for step in steps] == ["drop_columns", "replace_placeholder_values", "add_missing_indicator", "numeric_imputation"]
    assert [step["order_index"] for step in steps] == list(range(4))
    assert client.post(f"/pipelines/{pipeline_id}/analysis-setup").json()["steps"] == steps
    validation = client.post(f"/pipelines/{pipeline_id}/validate").json()
    assert validation["valid"], validation
    run_response = client.post(f"/pipelines/{pipeline_id}/apply")
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]
    config = client.get(f"/pipeline-runs/{run_id}/download/config").json()
    assert config["analysis_options"] == analysis["options"]
    namespace = {}
    exec(client.get(f"/pipeline-runs/{run_id}/download/code").text, namespace)
    for role, csv in inputs.items():
        replay = namespace["apply_pipeline"](pd.read_csv(StringIO(csv)))
        key = "cleaned-single" if role == "single" else f"cleaned-{role}"
        cleaned = pd.read_csv(StringIO(client.get(f"/pipeline-runs/{run_id}/download/{key}").text))
        pd.testing.assert_frame_equal(replay, cleaned, check_dtype=False)
        assert "notes" not in cleaned.columns
        missing_row = 1 if role != "test" else 0
        assert cleaned.loc[missing_row, "age_was_missing"] == 1
        assert cleaned.loc[missing_row, "age"] == 20
        assert Path(sources[role]["storage_path"]).read_bytes() == source_bytes[role]
    assert "Only the enabled pipeline steps" in client.get(f"/pipeline-runs/{run_id}/download/report").text


def test_setup_requires_linked_snapshot_and_matching_mode(client):
    project_id = client.post("/projects", json={"name": "Setup guards"}).json()["id"]
    pipeline_id = client.post(f"/projects/{project_id}/pipelines", json={"name": "No analysis"}).json()["id"]
    assert client.post(f"/pipelines/{pipeline_id}/analysis-setup").status_code == 400
    upload(client, project_id, "single", "value\n1\n2\n")
    analysis_id = client.post(f"/projects/{project_id}/analysis/run", json={}).json()["id"]
    mismatched = client.post(f"/projects/{project_id}/pipelines", json={"name": "Wrong mode", "analysis_run_id": analysis_id, "mode": "train_test"}).json()["id"]
    response = client.post(f"/pipelines/{mismatched}/analysis-setup")
    assert response.status_code == 400 and "mode must match" in response.json()["detail"]


def test_sqlite_snapshot_migration_preserves_legacy_rows_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE analysis_runs (id INTEGER PRIMARY KEY, status TEXT)")
            connection.exec_driver_sql("INSERT INTO analysis_runs VALUES (1, 'completed')")
        migrate_database(engine)
        migrate_database(engine)
        with engine.connect() as connection:
            row = connection.exec_driver_sql("SELECT id, status, options_json FROM analysis_runs").one()
            assert row[:2] == (1, "completed") and json.loads(row[2]) is None
    finally:
        engine.dispose()
