# DataPrep Studio Frontend

React/Vite/TypeScript frontend for DataPrep Studio.

The frontend implements the local MVP workflow across project creation, CSV upload, analysis, issue review, column profiles, pipeline building, preview, and exports.

## Setup

```powershell
npm install
```

## Run

```powershell
npm run dev
```

## Build

```powershell
npm run build
```

## Browser Tests

```powershell
npm run test:e2e
```

The Playwright suite covers dashboard/project navigation, workflow progress guidance, workspace context, upload-to-analysis flow, upload error display, inline analysis report display, recommendation action cards, issue suggestions, column charts, recommendation-to-pipeline step creation, pipeline recipe summary, preview, apply, and export navigation with mocked backend responses.

## UX Surfaces

- Workflow progress bar for project, upload, analysis, review, pipeline, preview, and export stages.
- Current workspace context bar for project, loaded data, selected analysis, and selected pipeline.
- Analysis summary cards for readiness, issues, column profile counts, and recommended fixes.
- Inline printable analysis report viewer with markdown download.
- Recommendation cards with explicit pipeline action labels.
- Pipeline recipe summary showing what enabled steps will do before preview or apply.

## API Base URL

The default API base URL is:

```text
http://127.0.0.1:8000
```

Override it with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```
