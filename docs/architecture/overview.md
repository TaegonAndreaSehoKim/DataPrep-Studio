# Architecture Overview

DataPrep Studio is a local full-stack MVP.

```text
React/Vite frontend
  -> FastAPI backend
       -> SQLite database
       -> local upload storage
       -> pandas/NumPy/scikit-learn services
       -> local export storage
```

## Backend

The backend owns persistence, CSV parsing, profiling, issue detection, preprocessing recommendations, preprocessing, preview, export generation, and download endpoints.

Important backend modules:

- `app/main.py` for FastAPI app setup
- `app/config.py` for pydantic-settings configuration
- `app/database.py` for SQLAlchemy session setup
- `app/models.py` for ORM models
- `app/schemas.py` for request and response schemas
- `app/routers/` for API routes
- `app/services/` for profiling, issue detection, readiness scoring, drift detection, recommendations, chart payloads, pipeline execution, preview, reports, and exports

## Frontend

The frontend is a practical developer-tool interface for the core workflow.

Important frontend modules:

- `src/api/client.ts` for API calls
- `src/api/types.ts` for shared response types
- `src/pages/` for workflow pages
- `src/components/` for reusable UI pieces
- `src/styles/global.css` for app styling

Current frontend UX surfaces include workflow progress guidance, current workspace context, analysis summary cards, recommendation action cards, inline printable analysis report viewing, and a pipeline recipe summary.

## Persistence

SQLite stores metadata for projects, dataset files, saved dataset configs, analysis runs, profiles, issues, pipelines, pipeline steps, and pipeline runs.

Uploaded CSVs and generated exports are stored on the local filesystem under `backend/app/storage`.

## Leakage-Safe Train/Test Processing

In train/test mode, all learned preprocessing parameters must be fit from train data only.

Examples:

- imputation values
- category vocabularies
- rare-category thresholds
- one-hot encoded columns
- frequency maps
- scaler statistics
- clipping thresholds

The test dataset is transformed using train-fitted parameters.
