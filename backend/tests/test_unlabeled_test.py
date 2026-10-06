from io import StringIO
from pathlib import Path

import pandas as pd
import pytest


def create_pair(client, train_csv=None, test_csv=None):
    project_id = client.post("/projects", json={"name": "Unlabeled test"}).json()["id"]
    inputs = {
        "train": train_csv or "age,city,target\n10,A,0\n,B,1\n30,A,0\n",
        "test": test_csv or "age,city\n,C\n1000,A\n",
    }
    sources = {}
    for role, csv in inputs.items():
        response = client.post(f"/projects/{project_id}/datasets/upload", data={"role": role}, files={"file": (f"{role}.csv", csv.encode(), "text/csv")})
        assert response.status_code == 201
        sources[role] = response.json()["dataset"]
    analysis = client.post(f"/projects/{project_id}/analysis/run", json={"mode": "train_test", "target_column": "target", "problem_type": "classification", "column_type_overrides": {"age": "numeric"}})
    return project_id, inputs, sources, analysis


def create_pipeline(client, project_id, analysis_id):
    return client.post(f"/projects/{project_id}/pipelines", json={"name": "Feature preprocessing", "mode": "train_test", "analysis_run_id": analysis_id}).json()["id"]


def test_unlabeled_test_analysis_checks_features_and_skips_target_comparison(client):
    _, _, _, response = create_pair(client)
    assert response.status_code == 201
    analysis_id = response.json()["id"]
    summary = client.get(f"/analysis/{analysis_id}/train-test-comparison").json()["summary"]
    assert summary["test_target_present"] is False
    assert summary["missing_columns_in_test"] == []
    assert summary["target_distribution_status"] == "not_available"
    assert "target_distribution" not in summary
    assert summary["columns"]["city"]["unseen_categories"] == ["C"]
    profiles = client.get(f"/analysis/{analysis_id}/columns").json()
    assert any(profile["column_name"] == "target" and profile["dataset_role"] == "train" for profile in profiles)
    assert not any(profile["column_name"] == "target" and profile["dataset_role"] == "test" for profile in profiles)
    issues = client.get(f"/analysis/{analysis_id}/issues").json()
    assert not any(issue["title"] == "Train/test column mismatch" for issue in issues)
    assert "target distribution comparison is unavailable" in client.get(f"/analysis/{analysis_id}/download/report").text


def test_unlabeled_test_pipeline_preserves_labels_and_replays_exports(client):
    project_id, inputs, sources, analysis = create_pair(client)
    assert analysis.status_code == 201
    source_bytes = {role: Path(dataset["storage_path"]).read_bytes() for role, dataset in sources.items()}
    pipeline_id = create_pipeline(client, project_id, analysis.json()["id"])
    for operation, columns, params in [
        ("remove_duplicate_rows", [], {}), ("add_missing_indicator", ["age"], {}),
        ("numeric_imputation", ["age"], {"strategy": "mean"}), ("one_hot_encoding", ["city"], {}),
    ]:
        assert client.post(f"/pipelines/{pipeline_id}/steps", json={"operation_type": operation, "columns": columns, "params": params}).status_code == 201
    validation = client.post(f"/pipelines/{pipeline_id}/validate").json()
    assert validation["valid"], validation
    preview = client.post(f"/pipelines/{pipeline_id}/preview")
    assert preview.status_code == 200
    assert any("train target unchanged" in warning for warning in preview.json()["warnings"])
    assert any("excludes the train target" in warning for warning in preview.json()["warnings"])
    response = client.post(f"/pipelines/{pipeline_id}/apply")
    assert response.status_code == 201
    run_id = response.json()["id"]
    config = client.get(f"/pipeline-runs/{run_id}/download/config").json()
    assert config["steps"][0]["params"]["subset"] == ["age", "city"]
    assert config["steps"][2]["fitted"]["fill_values"]["age"] == 20
    cleaned = {role: pd.read_csv(StringIO(client.get(f"/pipeline-runs/{run_id}/download/cleaned-{role}").text)) for role in inputs}
    assert cleaned["train"]["target"].tolist() == [0, 1, 0]
    assert "target" not in cleaned["test"].columns
    assert [column for column in cleaned["train"].columns if column != "target"] == cleaned["test"].columns.tolist()
    assert cleaned["test"].loc[0, "age"] == 20
    assert cleaned["test"].loc[0, "city_A"] == 0 and cleaned["test"].loc[0, "city_B"] == 0
    namespace = {}
    exec(client.get(f"/pipeline-runs/{run_id}/download/code").text, namespace)
    replay_train, replay_test = namespace["preprocess_train_test"](*(pd.read_csv(StringIO(inputs[role])) for role in ["train", "test"]))
    pd.testing.assert_frame_equal(replay_train, cleaned["train"], check_dtype=False)
    pd.testing.assert_frame_equal(replay_test, cleaned["test"], check_dtype=False)
    for role, dataset in sources.items():
        assert Path(dataset["storage_path"]).read_bytes() == source_bytes[role]


@pytest.mark.parametrize("operation,columns,params", [
    ("numeric_imputation", ["target"], {}), ("drop_columns", ["target"], {}),
    ("rename_columns", [], {"rename_map": {"target": "label"}}),
    ("reorder_columns", [], {"column_order": ["target", "age", "city"]}),
    ("remove_duplicate_rows", [], {"subset": ["target"]}),
])
def test_unlabeled_test_rejects_label_changes_consistently(client, operation, columns, params):
    project_id, _, _, analysis = create_pair(client)
    pipeline_id = create_pipeline(client, project_id, analysis.json()["id"])
    assert client.post(f"/pipelines/{pipeline_id}/steps", json={"operation_type": operation, "columns": columns, "params": params}).status_code == 201
    validation = client.post(f"/pipelines/{pipeline_id}/validate").json()
    assert not validation["valid"]
    assert any("select feature columns only" in issue["message"] for issue in validation["issues"])
    for action in ["preview", "apply"]:
        response = client.post(f"/pipelines/{pipeline_id}/{action}")
        assert response.status_code == 400
        assert "select feature columns only" in response.json()["detail"]
    assert client.get(f"/projects/{project_id}/pipeline-runs").json() == []


def test_unlabeled_test_still_rejects_missing_required_feature_at_execution(client):
    project_id, _, _, analysis = create_pair(client, test_csv="age\n20\n40\n")
    assert analysis.status_code == 201
    summary = client.get(f"/analysis/{analysis.json()['id']}/train-test-comparison").json()["summary"]
    assert summary["missing_columns_in_test"] == ["city"]
    pipeline_id = create_pipeline(client, project_id, analysis.json()["id"])
    client.post(f"/pipelines/{pipeline_id}/steps", json={"operation_type": "one_hot_encoding", "columns": ["city"]})
    for action in ["preview", "apply"]:
        response = client.post(f"/pipelines/{pipeline_id}/{action}")
        assert response.status_code == 400
        assert "Columns do not exist: city" in response.json()["detail"]


def test_selected_target_is_still_required_in_train(client):
    _, _, _, response = create_pair(client, train_csv="age,city\n10,A\n20,B\n")
    assert response.status_code == 400
    assert response.json()["detail"] == "Target column does not exist in the train dataset"


@pytest.mark.parametrize("subset", [None, False, ""])
def test_unlabeled_test_dedup_default_does_not_hide_invalid_parameters(client, subset):
    project_id, _, _, analysis = create_pair(client)
    pipeline_id = create_pipeline(client, project_id, analysis.json()["id"])
    client.post(f"/pipelines/{pipeline_id}/steps", json={"operation_type": "remove_duplicate_rows", "params": {"subset": subset}})
    assert not client.post(f"/pipelines/{pipeline_id}/validate").json()["valid"]
    for action in ["preview", "apply"]:
        response = client.post(f"/pipelines/{pipeline_id}/{action}")
        assert response.status_code == 400 and "Param subset" in response.json()["detail"]
