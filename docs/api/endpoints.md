# API Endpoints

This file tracks the planned API surface for the MVP.

## Health

- `GET /health`

## Dashboard

- `GET /dashboard`

## Projects

- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id}`
- `PATCH /projects/{project_id}`
- `DELETE /projects/{project_id}`

## Datasets

- `POST /projects/{project_id}/datasets/upload`
- `GET /projects/{project_id}/datasets`
- `GET /datasets/{dataset_file_id}`
- `GET /datasets/{dataset_file_id}/preview`
- `GET /datasets/{dataset_file_id}/setup-suggestions`
- `DELETE /datasets/{dataset_file_id}`

## Dataset Configs

- `POST /projects/{project_id}/dataset-configs`
- `GET /projects/{project_id}/dataset-configs`
- `GET /dataset-configs/{config_id}`
- `PATCH /dataset-configs/{config_id}`
- `DELETE /dataset-configs/{config_id}`

## Analysis

- `POST /projects/{project_id}/analysis/run`
- `GET /analysis/{analysis_id}`
- `GET /analysis/{analysis_id}/overview`
- `GET /analysis/{analysis_id}/columns`
- `GET /analysis/{analysis_id}/columns/{column_name}`
- `GET /analysis/{analysis_id}/columns/{column_name}/charts`
- `GET /analysis/{analysis_id}/issues`
- `GET /analysis/{analysis_id}/charts`
- `GET /analysis/{analysis_id}/score`
- `GET /analysis/{analysis_id}/train-test-comparison`

## Pipelines

- `POST /projects/{project_id}/pipelines`
- `POST /projects/{project_id}/pipelines/from-analysis/{analysis_id}`
- `POST /projects/{project_id}/pipelines/from-config`
  - Accepts exported DataPrep Studio preprocessing configs. If no name is provided, `metadata.pipeline_name` is used for the imported draft when available.
- `GET /projects/{project_id}/pipelines`
- `GET /pipelines/{pipeline_id}`
- `DELETE /pipelines/{pipeline_id}`
- `POST /pipelines/{pipeline_id}/steps`
- `PATCH /pipelines/{pipeline_id}/steps/{step_id}`
- `DELETE /pipelines/{pipeline_id}/steps/{step_id}`
- `POST /pipelines/{pipeline_id}/steps/reorder`
- `POST /pipelines/{pipeline_id}/steps/{step_id}/toggle`
- `POST /pipelines/{pipeline_id}/steps/from-issue/{issue_id}`
- `POST /pipelines/{pipeline_id}/validate`
- `GET /issues/{issue_id}/suggested-step`
- `GET /pipeline/operations`

## Preview and Apply

- `POST /pipelines/{pipeline_id}/preview`
  - Returns before/after summaries, affected columns, before/after sample rows, column-level diffs, step effects, warnings, and fitted parameter metadata.
- `POST /pipelines/{pipeline_id}/preview/charts`
- `POST /pipelines/{pipeline_id}/apply`

## Exports

- `GET /pipeline-runs/{pipeline_run_id}`
- `GET /pipeline-runs/{pipeline_run_id}/download/config`
  - Returns a versioned preprocessing config with fitted steps and metadata such as pipeline name, operation types, step count, input/output file counts, summaries, and train-only fit status.
- `GET /pipeline-runs/{pipeline_run_id}/download/report`
- `GET /pipeline-runs/{pipeline_run_id}/download/code`
- `GET /pipeline-runs/{pipeline_run_id}/download/cleaned-single`
- `GET /pipeline-runs/{pipeline_run_id}/download/cleaned-train`
- `GET /pipeline-runs/{pipeline_run_id}/download/cleaned-test`
