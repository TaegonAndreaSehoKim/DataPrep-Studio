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
- Analysis runs keep an immutable `options` snapshot even after saved setups are edited or deleted. Startup adds the snapshot column to existing SQLite databases; legacy runs return `options: null` rather than inventing historical settings.
- `POST /pipelines/{id}/analysis-setup` explicitly prepends editable ignored-column and trimmed placeholder steps from the linked snapshot. Repeated requests do not duplicate them. Type overrides remain profiling hints. Config/report/code record analysis context, while only enabled steps mutate exported data.
- Editable pipeline drafts may contain invalid parameters. Validate, preview, and apply share operation parameter checks for types, finite numbers, range lengths/order, and supported values; execution rejects invalid parameters with readable 400 errors.
- CSV files are the only supported input format for the MVP.
- Preprocessing previews operate on copies and do not mutate uploaded source files.
- In train/test mode, learned preprocessing parameters are fit on train only and applied to test.
- Missing required test features are rejected. Numeric imputation coerces both splits consistently, rare grouping honors the same missing-value option in both splits, and inferred per-column date formats are learned on train and embedded in config/code. Ambiguous dates default to the format inferred from train; provide an explicit format when needed. Missing/invalid dates retain missing derived values.
- All-missing train numeric columns need a constant imputation strategy before scaling/clipping. Robust scaling centers on the train median and uses the configured train quantile span.
- One-hot encoding allocates deterministic unique output names, preserving existing input features and embedding the category-to-output map in exports. Other derived features and rename operations reject collisions instead of overwriting columns; test uses the names allocated on train.
- Generated Python code loads embedded JSON safely, including nulls, booleans, and escaped strings. Export tests execute downloaded code and compare its outputs with cleaned CSVs in single and train/test modes.
- Recommendations and readiness scores are advisory heuristics, not model performance guarantees.
