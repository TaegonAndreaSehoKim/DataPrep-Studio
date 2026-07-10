# Product Workflow

DataPrep Studio is a manual preprocessing workbench for tabular machine learning workflows.

It is designed for users who want to inspect data quality, choose transformations, tune parameters, and export reproducible preprocessing artifacts before model training.

## Core Flow

1. Create a project.
2. Upload one CSV dataset or a train/test CSV pair.
3. Use the workflow progress bar to confirm the current stage and next recommended action.
4. Confirm the upload completion state and current workspace context, including project, loaded data, selected analysis, and selected pipeline.
5. Open analysis directly from the upload success state when the dataset is ready.
6. Review suggested analysis setup for target column, problem type, missing value tokens, ignored columns, and column type overrides.
7. Save reusable analysis setup when the same dataset rules should be rerun, and update or delete saved setup as it changes.
8. Run dataset analysis.
9. Inspect the analysis summary first: readiness band, issue counts, column profile counts, recommended fixes, and next action cards.
10. Review notable preprocessing recommendations, issues, charts, and column profiles, or read and print the inline analysis report.
11. Add an accepted preprocessing recommendation directly into the pipeline with a clear action label, or build a pipeline manually.
12. Review the pipeline recipe summary to understand what the enabled steps will do before preview or apply.
13. Generate a suggested pipeline draft, import an exported preprocessing config, or configure operation parameters manually with visible defaults, allowed values, and supported column types.
14. Validate the pipeline against selected columns, profile types, and step-to-step column availability, with affected-step feedback, then preview before/after summaries, column-level diffs, and sample rows.
15. Apply the pipeline.
16. Export cleaned data, config, report, and code.

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
- Workflow progress and current workspace context
- Issue-to-step suggestions
- Inline printable analysis report
- Recommendation action cards
- Pipeline recipe summary
- Operation parameter help
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
