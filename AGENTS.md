# AGENTS.md

## Purpose

This file gives future coding agents a practical operating guide for `DataPrep Studio`.
It reflects the project state after the local MVP became runnable end to end.

DataPrep Studio is a configurable data quality and preprocessing workbench for tabular machine learning workflows. It is not AutoML, not a black-box data repair tool, and not an AI/LLM application.

## Project Snapshot

The current MVP is a local full-stack app with:

- FastAPI backend under `backend/`
- React, Vite, and TypeScript frontend under `frontend/`
- SQLite-backed local persistence
- local CSV upload and export storage
- CSV dataset profiling
- ML-readiness issue detection
- train/test drift and split quality checks
- manual preprocessing pipeline construction
- leakage-safe train/test preprocessing
- before/after pipeline preview
- cleaned CSV export
- reproducible preprocessing config export
- markdown report export
- generated pandas-style preprocessing code export
- pytest coverage for backend data-quality and transformation behavior
- frontend build validation
- Playwright browser smoke coverage for the core workflow
- workflow progress, workspace context, printable analysis report, recommendation action cards, and pipeline recipe UX

This is local MVP software intended for demos, portfolio discussion, and future iteration. Do not optimize prematurely for production deployment, multi-user collaboration, or cloud storage.

## Current Development Stage

The project is in a working local MVP stage.

What exists now:

- Product requirements in `DataPrep Studio.txt`
- This operating guide
- backend and frontend implementations for the core workflow
- persisted projects, datasets, configs, analysis runs, profiles, issues, pipelines, steps, and pipeline runs
- analysis recommendations, charts, inline/downloadable analysis reports, pipeline preview/apply, and export artifacts
- backend pytest coverage and frontend Playwright smoke coverage

What should be improved next:

- additional browser coverage for less common failure states and recovery paths
- demo screenshots or portfolio walkthrough material
- continued operation-specific UX refinement as new transformations are added
- documentation updates whenever workflow, API, setup, or export behavior changes

What is explicitly out of scope for the MVP:

- AutoML
- model training platform
- hyperparameter tuning
- LLM-based data cleaning
- user authentication
- cloud object storage
- multi-user collaboration
- production deployment
- advanced resampling such as SMOTE
- SQL, warehouse, or Parquet connectors

## Source of Truth

Use these files first when reasoning about requirements and behavior:

- `DataPrep Studio.txt`
- `README.md`
- `backend/README.md`
- `frontend/README.md`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/services/profiler.py`
- `backend/app/services/issue_detector.py`
- `backend/app/services/readiness_score.py`
- `backend/app/services/drift_detector.py`
- `backend/app/services/pipeline_engine.py`
- `backend/app/services/transformations.py`
- `backend/app/services/pipeline_preview.py`
- `backend/app/services/export_service.py`
- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`

For current quality expectations, read backend tests under:

- `backend/tests/`

When implementation and this guide disagree, prefer the explicit product requirements in `DataPrep Studio.txt`, then update this guide if project policy has changed.

## Working Principles

1. Preserve user control.
   The product should diagnose issues and expose preprocessing choices. Do not turn it into a black-box "fix my dataset" flow.

2. Keep preprocessing reproducible.
   Every applied pipeline should be representable as config, report, and generated code.

3. Treat leakage safety as a core requirement.
   In train/test mode, all learned preprocessing statistics must be fit on train only and then applied to test.

4. Prefer small, test-backed changes.
   Backend behavior should usually be covered with pytest before the task is considered complete.

5. Keep the MVP local and deterministic.
   Avoid external services, network-dependent tests, cloud storage, or hidden background infrastructure.

6. Preserve API contract clarity.
   If an API response shape changes, update `backend/app/schemas.py`, backend tests, and `frontend/src/api/types.ts` together.

7. Avoid silent data mutation.
   Uploaded files are immutable inputs. Preview operations must use copies. Applied pipelines should write new exported files.

8. Make errors user-readable.
   Invalid CSVs, invalid pipeline parameters, unsupported columns, and missing project state should return clear messages.

## Leakage-Safe Rules

In train/test mode, never compute learned values from combined train and test data.

Fit on train only for:

- numeric imputation values
- categorical imputation values
- missingness indicator columns
- rare-category frequency thresholds
- one-hot category lists
- ordinal category maps
- frequency encoding maps
- scaling statistics
- clipping thresholds
- log transform validation thresholds where relevant
- datetime parsing assumptions where relevant

Transform test using the fitted train parameters.

Reports and generated code should explicitly state train-only fitting behavior.

## Data Handling Rules

- Accept CSV files only for the MVP.
- Enforce upload extension and size validation.
- Store uploads under `backend/app/storage/uploads`.
- Store exports under `backend/app/storage/exports`.
- Keep uploaded and exported files out of git.
- Keep `.gitkeep` files in empty storage directories.
- Do not overwrite uploaded source files.
- Do not rely on global process state for pipeline results.
- Use pandas copies for previews and transformations unless a function intentionally returns a new DataFrame.

## Backend Guidance

- Prefer service modules for data-processing behavior and keep routers thin.
- Use SQLAlchemy ORM models for persistence.
- Use Pydantic schemas for API boundaries.
- Keep JSON blobs explicit in schemas where flexibility is needed, but avoid `Any` when a stable type is practical.
- Validate operation parameters before applying transformations.
- Do not silently ignore missing columns or unsupported column types.
- Keep transformation logic deterministic.
- Keep tests isolated with temporary SQLite databases and temporary storage directories.
- Do not add external API calls.

## Frontend Guidance

- Build a practical developer tool UI, not a marketing landing page.
- Keep API calls centralized in `frontend/src/api/client.ts`.
- Keep shared API types in `frontend/src/api/types.ts`.
- Use React state and straightforward component composition; do not add Redux unless a real need appears.
- Render pipeline operation forms from backend operation metadata where practical.
- Keep empty, loading, and error states visible and useful.
- Prefer simple CSS or CSS modules over heavy UI frameworks.
- Ensure `npm run build` passes before closing frontend work.

## Current Priorities

When choosing what to improve next, bias toward these:

- keep CSV upload, preview, and analysis reliable
- protect leakage-safe pipeline behavior
- keep export artifacts honest and reproducible
- keep the workflow progress, context bar, recommendation cards, and pipeline recipe summary easy to understand
- keep README instructions current
- expand tests around train/test mode and failure states

Lower priority for now:

- auth
- cloud deployment
- model training
- complex data connectors

## Known Risks and Footguns

1. Train/test leakage is the highest-risk bug class.
   Any operation with learned parameters must fit on train only.

2. Readiness score is a heuristic.
   Do not present it as a guarantee of model performance.

3. Issue detection is advisory.
   Suggested actions should help users decide, not automatically rewrite data.

4. CSV parsing can be messy.
   Keep parser errors clear, and avoid assuming all CSVs are clean UTF-8 with perfect rows.

5. SQLite is local MVP persistence.
   Do not design around multi-user production assumptions before that milestone is explicit.

6. Local storage paths should be predictable.
   Running `cd backend && uvicorn app.main:app --reload` should store app data under `backend/app/storage`.

7. Tests must not depend on persistent local files.
   Use temporary DB and storage paths in test fixtures.

8. Generated code should be useful and honest.
   It does not need to cover every future advanced case, but it should not claim behavior it does not implement.

9. Frontend and backend types can drift.
   When changing schemas, update both sides in the same task.

10. Large dependency additions are rarely justified for the MVP.
    Prefer pandas, NumPy, scikit-learn, FastAPI, SQLAlchemy, and simple React patterns.

## Editing Guidance

- Prefer changing backend behavior in service modules before duplicating logic in routers.
- If adding a model field, update SQLAlchemy models, schemas, tests, and frontend types together.
- If changing upload handling, verify extension, size, invalid project, preview, and row/column count behavior.
- If changing analysis behavior, update profiler, issue detector, readiness score, and tests as needed.
- If changing pipeline operations, update operation metadata, transformation logic, preview/apply behavior, generated config, generated code, and tests.
- If changing export paths or filenames, update download endpoints, tests, and README instructions.
- Do not commit `.env`, local database files, uploaded CSVs, generated exports, `node_modules`, or frontend build output.
- Keep durable documentation in sync when behavior changes, especially `README.md`, `AGENTS.md`, and backend/frontend READMEs.

## Validation Checklist

Run backend tests before closing backend or full-stack changes:

```powershell
cd backend
python -m pytest -q
```

Run the backend locally for smoke checks:

```powershell
cd backend
uvicorn app.main:app --reload
```

Run frontend build before closing frontend or full-stack changes:

```powershell
cd frontend
npm run build
```

Run the frontend locally:

```powershell
cd frontend
npm run dev
```

Useful manual product smoke:

1. Start backend.
2. Start frontend.
3. Create a project.
4. Upload a CSV.
5. Select target column and run analysis.
6. Inspect readiness score, issues, and columns.
7. Create a pipeline.
8. Add preprocessing steps.
9. Preview before/after effects.
10. Apply the pipeline.
11. Download cleaned data, config, report, and generated code.

## Preferred Change Pattern

For most tasks:

1. Read the relevant router/service, schema, and tests.
2. Make the smallest coherent change.
3. Update or add backend tests when behavior changes.
4. Update frontend types/client when API shape changes.
5. Run targeted checks.
6. Update durable docs when setup, architecture, or operating expectations change.

## Commit Convention

- Prefer Conventional Commit style messages such as `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, or `chore: ...`.
- Keep the subject line concise and focused on the outcome.
- Group related code, test, and documentation changes when they serve the same milestone.

## Near-Term Roadmap

Reasonable next milestones:

- add browser smoke coverage for additional recovery paths after API failures
- broaden backend edge-case coverage as new operations and exports are added
- prepare demo screenshots or portfolio walkthrough material
- keep documentation current with implemented workflow and API behavior

## Default Mindset

This repository rewards practical iteration over architectural ambition.
Keep the local MVP working, keep preprocessing explicit and reproducible, protect train/test leakage boundaries, and make data quality issues easier for a user to inspect and act on.
