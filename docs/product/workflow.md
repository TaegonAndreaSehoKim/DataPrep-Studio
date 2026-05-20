# Product Workflow

DataPrep Studio is a manual preprocessing workbench for tabular machine learning workflows.

It is designed for users who want to inspect data quality, choose transformations, tune parameters, and export reproducible preprocessing artifacts before model training.

## Core Flow

1. Create a project.
2. Upload one CSV dataset or a train/test CSV pair.
3. Confirm the upload completion state and current loaded dataset in the workspace header.
4. Open analysis directly from the upload success state when the dataset is ready.
5. Review suggested analysis setup for target column, problem type, missing value tokens, ignored columns, and column type overrides.
6. Save reusable analysis setup when the same dataset rules should be rerun, and update or delete saved setup as it changes.
7. Run dataset analysis.
8. Inspect readiness score, notable preprocessing recommendations, issues, charts, and column profiles.
9. Send an accepted preprocessing recommendation into an editable pipeline draft, or build a pipeline manually.
10. Generate a suggested pipeline draft, import an exported preprocessing config, or configure operation parameters manually.
11. Validate the pipeline against selected columns, profile types, and step-to-step column availability, then preview before/after summaries, column-level diffs, and sample rows.
12. Apply the pipeline.
13. Export cleaned data, config, report, and code.

## MVP Feature Areas

- Project management
- CSV upload and preview
- Dataset profiling
- Issue detection
- Analysis-level preprocessing recommendations
- Readiness scoring
- Analysis setup persistence
- Chart visualizations
- Train/test comparison
- Pipeline builder
- Issue-to-step suggestions
- Preprocessing config import and export metadata
- Pipeline validation
- Transformation preview with before/after samples and column diffs
- Pipeline apply
- Export artifacts

## Non-Goals

- AutoML
- automatic model selection
- hyperparameter tuning
- LLM-based data cleaning
- user authentication
- cloud object storage
- multi-user collaboration
- production deployment
- SQL, warehouse, or Parquet connectors

## User Control

The app should surface issues and suggested actions, but the user chooses which transformations to apply.

The readiness score is a prioritization heuristic, not a promise that model performance will improve.
