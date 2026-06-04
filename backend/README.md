# DataPrep Studio Backend

FastAPI backend for the DataPrep Studio local MVP.

The backend owns persistence, CSV parsing, profiling, issue detection, preprocessing pipeline execution, preview, export generation, and download endpoints.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```powershell
uvicorn app.main:app --reload
```

The default local API is:

```text
http://127.0.0.1:8000
```

Health check:

```text
GET /health
```

## Test

```powershell
python -m pytest -q
```

Run the local backend smoke flow:

```powershell
python scripts\smoke_demo.py
```

## Implemented Areas

- FastAPI app setup and router registration
- pydantic-settings configuration
- SQLAlchemy SQLite session setup
- ORM models and Pydantic schemas
- health, dashboard, and project CRUD
- CSV upload, preview, listing, setup suggestions, and deletion
- reusable dataset analysis configs
- single dataset and train/test analysis
- column profiling, issue detection, readiness scoring, and drift comparison
- analysis charts, column charts, and rich markdown analysis report download
- preprocessing recommendations from notable analysis findings
- pipeline CRUD, step CRUD, reorder, toggle, validation, issue-to-step suggestions, and suggested pipeline generation
- preprocessing config import
- pipeline preview, preview charts, apply, and export downloads
- cleaned CSV, config JSON, markdown report, and generated Python code artifacts

## Local Storage

Uploaded CSVs are stored under:

```text
backend/app/storage/uploads
```

Generated exports are stored under:

```text
backend/app/storage/exports
```

Storage contents and local SQLite database files should stay out of git.

## Design Notes

- The backend is local-first and deterministic.
- CSV files are the only supported input format for the MVP.
- Preprocessing previews operate on copies and do not mutate uploaded source files.
- In train/test mode, learned preprocessing parameters are fit on train only and applied to test.
- Recommendations and readiness scores are advisory heuristics, not model performance guarantees.
