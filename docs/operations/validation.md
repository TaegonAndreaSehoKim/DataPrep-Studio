# Validation and Smoke Checks

Validation should stay fast, local, and deterministic.

## Backend

Run the backend test suite:

```powershell
cd backend
python -m pytest -q
```

Run the backend server:

```powershell
cd backend
uvicorn app.main:app --reload
```

Expected health check:

```text
GET http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "app": "DataPrep Studio"
}
```

Run the end-to-end backend smoke flow with temporary database and storage:

```powershell
cd backend
python scripts\smoke_demo.py
```

## Frontend

Run the production build:

```powershell
cd frontend
npm run build
```

Run browser-level smoke tests:

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

Run the dev server:

```powershell
cd frontend
npm run dev
```

## Manual Product Smoke

1. Start the backend.
2. Start the frontend.
3. Create a project.
4. Upload a single CSV, or upload train/test CSVs.
5. Configure target, missing tokens, ignored columns, and optional type overrides.
6. Save, update, or delete setup when it should be reused or retired.
7. Run analysis with a target column.
8. Inspect the workflow progress bar and current workspace context.
9. Inspect readiness score, analysis summary, recommendations, issues, charts, columns, and the inline printable analysis report.
10. Add a recommended preprocessing action to a pipeline, generate a suggested pipeline, import a config, or create manual steps.
11. Review the pipeline recipe summary and recommendation-origin steps.
12. Validate the pipeline and review unsupported type, missing-column, or step dependency warnings.
13. Preview the pipeline.
14. Apply the pipeline.
15. Download export artifacts.

Current validation checkpoint:

```text
Backend pytest: 40 passed
Frontend build: passing
Frontend Playwright smoke: 8 passed
Backend smoke demo: passing
```

## Test Isolation

Backend tests should use:

- temporary SQLite databases
- temporary upload directories
- temporary export directories
- fixture CSVs
- no external services
