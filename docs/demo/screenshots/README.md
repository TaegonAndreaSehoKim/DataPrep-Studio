# Demo Screenshots

These screenshots were captured from a clean local demo run using the AirQuality UCI data under `datasets/AirQualityUCI/`.

The source CSV includes empty trailing columns, trailing blank rows, and `-200` sentinel values for missing sensor readings. The screenshot run used temporary CSV copies that:

- dropped empty trailing columns and blank rows
- renamed columns to snake_case
- converted `-200` sentinel values to missing values
- used `c6h6_gt` as the regression target
- ignored `date` and `time` during analysis
- used a chronological 70/30 train/test split for the train/test flow

## Single Dataset Flow

- `01-dashboard.png` - clean dashboard
- `02-project-overview.png` - newly created project
- `03-upload-preview.png` - CSV upload completion and preview
- `04-analysis-results.png` - readiness score, AirQuality recommendations, report, and charts
- `05-issues.png` - issue review for AirQuality missingness, outliers, and duplicates
- `06-columns.png` - AirQuality column profile view
- `07-pipeline-builder.png` - manual pipeline that drops sparse `nmhc_gt`, imputes sensor/weather features, and scales numeric features
- `08-pipeline-validation.png` - pipeline validation feedback
- `09-preview.png` - before/after pipeline preview
- `10-exports.png` - cleaned CSV, config, report, and code exports

## Train/Test Flow

- `11-train-test-analysis.png` - chronological train/test analysis with drift summary
- `12-train-test-exports.png` - split-safe clean train/test exports
