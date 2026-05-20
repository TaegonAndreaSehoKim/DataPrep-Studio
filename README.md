# DataPrep Studio - Configurable ML Preprocessing Workbench

DataPrep Studio is a full-stack data preparation workbench for tabular machine learning projects.

It helps users upload CSV datasets, inspect data quality and ML-readiness issues, build preprocessing pipelines step by step, preview before/after effects, and export reproducible cleaned datasets, configs, reports, and pandas-style preprocessing code.

This is not AutoML. It is not a black-box "fix my data" app. DataPrep Studio is designed for users who understand data science and want control over preprocessing choices.

## What It Does

```text
CSV dataset -> profile -> diagnose issues -> configure pipeline -> preview -> apply -> export
```

Core capabilities implemented in the MVP:

- Create local data preparation projects.
- Upload either one CSV dataset or a train/test CSV pair.
- See the currently loaded dataset in the workspace header and move from upload completion directly into analysis.
- Get suggested analysis setup for target column, problem type, missing tokens, type overrides, and ignored ID-like columns.
- Select a target column and problem type.
- Save, update, and delete reusable analysis setup with missing tokens, ignored columns, and column type overrides.
- Profile columns for type, missingness, cardinality, distributions, and warnings.
- Detect ML-readiness issues such as missing values, duplicates, outliers, leakage candidates, high-cardinality features, target imbalance, and train/test drift.
- Highlight analysis-specific preprocessing recommendations from notable findings.
- Send a recommended preprocessing step into the pipeline builder with an editable draft pipeline, operation, columns, and parameters prefilled for review.
- Visualize analysis, column-level summaries, and pipeline preview changes with charts.
- Convert detected issues into type-aware suggested preprocessing steps.
- Generate a suggested preprocessing pipeline draft from an analysis run.
- Build explicit preprocessing pipelines with user-selected operations and parameters.
- Import an exported `preprocessing_config.json` back into an editable pipeline draft.
- Validate pipeline steps against analysis column profiles before applying, with issue feedback surfaced on affected steps.
- Preview before/after summaries, column-level diffs, and sample rows before writing cleaned data.
- Apply pipelines in a reproducible way.
- Export cleaned CSVs, `preprocessing_config.json`, `preprocessing_report.md`, and generated Python preprocessing code.

## Product Philosophy

DataPrep Studio favors transparent control over automation:

- Diagnose issues clearly.
- Offer transformation options.
- Let the user choose operations and parameters.
- Preview effects before applying.
- Preserve leakage-safe train/test behavior.
- Export artifacts that make the work reproducible.

Recommendations and readiness scores are heuristics. They help users prioritize data preparation work, but they are not guarantees of model performance.

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite, pandas, NumPy, scikit-learn
- Frontend: React, Vite, TypeScript, plain CSS
- Testing: pytest for backend, frontend production build checks, Playwright browser smoke tests
- Storage: local filesystem under `backend/app/storage`
- Exports: CSV, JSON, Markdown, generated Python code

## Architecture

```text
React/Vite frontend
  -> FastAPI backend
       -> SQLite metadata store
       -> local upload storage
       -> pandas profiling and preprocessing services
       -> local export artifacts
```

In train/test mode, preprocessing statistics are fit on train only and applied to test. This rule applies to imputation values, category maps, scaling statistics, clipping thresholds, and other learned transformation parameters.

More detail:

- [Product workflow](docs/product/workflow.md)
- [Architecture overview](docs/architecture/overview.md)
- [API endpoints](docs/api/endpoints.md)
- [Local workflows](docs/development/local_workflows.md)
- [Validation and smoke checks](docs/operations/validation.md)

## Quick Start

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

The frontend defaults to:

```text
http://127.0.0.1:8000
```

The current MVP includes a runnable FastAPI backend and Vite frontend workflow shell.

## Demo Flow

1. Create a project.
2. Upload a CSV dataset or train/test CSV pair.
3. Confirm the loaded data status in the workspace header.
4. Select the target column and problem type.
5. Optionally save the setup for reuse.
6. Run analysis.
7. Review readiness score, issues, charts, and column profiles.
8. Create a preprocessing pipeline.
9. Add and configure transformation steps, or add suggested steps from issues.
10. Validate and preview before/after effects.
11. Apply the pipeline.
12. Download cleaned data, config, report, and generated code.

## Validation

Backend:

```powershell
cd backend
python -m pytest -q
```

Backend smoke:

```powershell
cd backend
python scripts\smoke_demo.py
```

Frontend:

```powershell
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

More checks: [Validation and smoke checks](docs/operations/validation.md).

## Current Status

DataPrep Studio is at the working local MVP stage.

Built so far:

- product requirements
- development policy for future coding agents
- README and documentation structure
- FastAPI backend with config, database setup, ORM models, schemas, health, dashboard, and project CRUD
- CSV upload, preview, listing, and deletion
- single dataset and train/test analysis flows
- profiling, issue detection, readiness scoring, and train/test comparison
- analysis-level preprocessing recommendations for notable data quality findings
- user-controlled analysis setup for saved configs, update/delete, missing value tokens, ignored columns, and column type overrides
- dataset setup suggestion API and frontend application flow
- analysis, column, and preview chart APIs with Recharts-based frontend visualizations
- type-aware issue-to-pipeline-step suggestions
- suggested pipeline draft generation from analysis issues
- pipeline CRUD, step CRUD, reorder, toggle, operation metadata, column-aware validation, preview, apply, and exports
- exported preprocessing config import back into editable pipeline drafts
- versioned preprocessing config metadata for exported pipeline names, operation lists, summaries, and train-only fit notes
- generated cleaned CSV, config JSON, markdown report, and Python code artifacts
- React/Vite frontend workflow for projects, upload, analysis, issues, columns, pipelines, preview, and exports
- backend pytest coverage, frontend build validation, and Playwright browser workflow tests for upload, analysis, recommendation-to-pipeline, preview, apply, and export navigation

Next implementation milestones:

- UI polish after manual workflow screenshots
- broader browser coverage for train/test mode, issue pages, column charts, and failure states

## Development Workflow

DataPrep Studio is being developed with AI-assisted coding support using Codex. Codex is used as a pair-programming assistant for implementation planning, scaffolding, refactoring, documentation, and test generation.

I own the product direction, architecture decisions, requirements, code review, debugging, and final validation. Generated code is reviewed, modified, and tested before being kept in the project.

## Project Map

```text
backend/                  FastAPI app, SQLite models, routers, services, tests
frontend/                 React/Vite app, API client, pages, components
docs/product/             product workflow and feature notes
docs/architecture/        architecture and data model notes
docs/api/                 API reference
docs/development/         local development workflows
docs/operations/          validation and smoke checks
AGENTS.md                 guidance for future coding agents
DataPrep Studio.txt       original product requirements
```

## Known Limitations

- CSV-only local MVP.
- SQLite and local filesystem storage are not production persistence.
- Readiness scores and issue recommendations are heuristic.
- Generated Python code replays fitted preprocessing steps for the implemented MVP operations, but should still be reviewed before production use.
- Frontend browser coverage exercises the core upload, analysis, recommendation-to-pipeline, preview, apply, and export navigation workflow, but does not yet cover train/test mode or failure states.
- No authentication, collaboration, cloud storage, or deployment path yet.
- No model training, AutoML, or hyperparameter tuning.

## Resume Bullet Draft

DataPrep Studio - Configurable ML Preprocessing Workbench | Python, FastAPI, React, pandas, scikit-learn

- Built a configurable preprocessing dashboard that lets users diagnose tabular datasets, select transformation strategies, tune parameters, and preview before/after effects before modeling.
- Implemented leakage-safe train/test preprocessing for imputation, encoding, scaling, rare-category grouping, duplicate handling, outlier clipping, and feature cleanup.
- Exported cleaned datasets, preprocessing configs, markdown reports, and reproducible pandas-style pipeline code, with pytest coverage for data-quality checks and transformation rules.
