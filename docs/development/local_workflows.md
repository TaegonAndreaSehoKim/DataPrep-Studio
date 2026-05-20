# Local Workflows

This file collects local setup and development commands.

## Backend Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend exposes:

```text
GET /health
GET /dashboard
POST /projects
GET /projects
GET /projects/{project_id}
PATCH /projects/{project_id}
DELETE /projects/{project_id}
POST /projects/{project_id}/datasets/upload
GET /projects/{project_id}/datasets
GET /datasets/{dataset_file_id}/preview
POST /projects/{project_id}/analysis/run
GET /analysis/{analysis_id}/overview
GET /analysis/{analysis_id}/columns
GET /analysis/{analysis_id}/issues
POST /projects/{project_id}/pipelines
POST /pipelines/{pipeline_id}/steps
POST /pipelines/{pipeline_id}/preview
POST /pipelines/{pipeline_id}/apply
GET /pipeline-runs/{pipeline_run_id}/download/config
GET /pipeline-runs/{pipeline_run_id}/download/report
GET /pipeline-runs/{pipeline_run_id}/download/code
```

## Backend Tests

```powershell
cd backend
python -m pytest -q
```

## Backend Smoke Demo

```powershell
cd backend
python scripts\smoke_demo.py
```

The smoke script uses a temporary SQLite database and temporary storage directory, then runs project creation, CSV upload, analysis, pipeline preview, apply, and config download.

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

The frontend includes the main workflow pages and a centralized API client. Project, upload, analysis, issue, column, pipeline, preview, and export pages are wired to backend APIs.
Analysis charts are rendered with Recharts from backend chart API data.

## Frontend Build

```powershell
cd frontend
npm run build
```

## Frontend Browser Tests

```powershell
cd frontend
npm run test:e2e
```

The Playwright tests run against the Vite dev server with mocked backend responses for the core browser workflow: project navigation, CSV upload, analysis run, recommendation-to-pipeline, preview, apply, and export navigation.

## Local Storage

Uploaded files should live under:

```text
backend/app/storage/uploads
```

Generated exports should live under:

```text
backend/app/storage/exports
```

Only `.gitkeep` files should be committed from storage directories.
