# Demo Walkthrough

This walkthrough is for a short local demo of the current MVP.

## Setup

Start the backend:

```powershell
cd backend
uvicorn app.main:app --reload
```

Start the frontend:

```powershell
cd frontend
npm run dev
```

Use a CSV with a mix of numeric and categorical columns, a target column, and at least one visible data-quality issue such as missing values, duplicate rows, high-cardinality categorical values, outliers, or train/test drift.

## Five-Minute Flow

1. Create a project.
2. Upload a single CSV or upload a train/test CSV pair.
3. Open analysis from the upload completion state.
4. Review the suggested setup for target column, problem type, missing tokens, ignored columns, and type overrides.
5. Run analysis.
6. Show the readiness score, issue counts, recommendation cards, charts, column profiles, and printable analysis report.
7. Add one recommendation to the pipeline, or create a suggested pipeline draft.
8. Review the pipeline recipe summary and operation parameter help.
9. Validate the pipeline.
10. Preview before/after summaries, column diffs, and sample rows.
11. Apply the pipeline.
12. Open exports and show cleaned CSV, config, report, and generated code downloads.

## Talking Points

- DataPrep Studio is a manual preprocessing workbench, not AutoML.
- Recommendations are advisory; users choose and tune transformations.
- Train/test preprocessing fits learned values on train only, then applies them to test.
- Uploaded source files are immutable; previews use copies and applied pipelines create new export artifacts.
- Exported config, report, and generated code make preprocessing decisions reproducible.

## Train/Test Variant

Use this when showing leakage safety:

1. Upload one CSV as `Train dataset`.
2. Upload one CSV as `Test dataset`.
3. Run analysis in `Train/test pair` mode.
4. Show `Train/Test Drift` in the analysis results.
5. Build a `Train/test` pipeline.
6. Add an operation with learned parameters, such as numeric imputation or scaling.
7. Preview and apply the pipeline.
8. Confirm exports include `Clean Train` and `Clean Test` rather than one combined cleaned CSV.

## Validation Before Demo

Run:

```powershell
cd backend
python -m pytest -q
```

```powershell
cd frontend
npm run build
npm run test:e2e
```
