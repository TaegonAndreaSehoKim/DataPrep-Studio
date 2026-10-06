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

The Playwright suite covers dashboard/project navigation, workflow progress guidance, workspace context, upload-to-analysis flow, upload error and blocked-state display, inline analysis report display, recommendation action cards, issue suggestions, column charts, recommendation-to-pipeline step creation, train/test analysis and export flow, pipeline recipe summary, operation parameter help, preview, apply, and export navigation with mocked backend responses.

## UX Surfaces

- Workflow progress bar for project, upload, analysis, review, pipeline, preview, and export stages.
- Current workspace context bar for project, loaded data, selected analysis, and selected pipeline.
- Project changes reset dependent selections and forms. Responses from obsolete workspace/pipeline requests are ignored, and switching pipelines clears the selected export run.
- Within one project, late validation, edits, and Apply responses remain associated with their original pipeline. A completed older Apply does not switch the current selection or open its exports, and older list responses cannot overwrite freshly edited steps.
- API errors show the backend detail message. Project loading, pipeline loading, preview, and exports support retry; Apply buttons remain disabled while a request is in progress.
- The preview page uses charts embedded in the preview response, avoiding a second transformation request for charts.
- Train/test workflows accept unlabeled test CSVs. Analysis explains unavailable target comparisons; the builder protects the train label from feature steps, and preview displays processing notes.
- Analysis summary cards for readiness, issues, column profile counts, and recommended fixes.
- Inline printable analysis report viewer with markdown download.
- Recommendation cards with explicit pipeline action labels.
- Pipeline recipe summary showing what enabled steps will do before preview or apply.
- Analysis results expose the saved run settings. The pipeline's **Add Analysis Setup Steps** button adds visible, editable missing-token and ignored-column steps before the existing recipe; setup hints do not silently alter exports.

## Browser Tests

`npm run test:e2e` runs isolated UI tests with mocked API responses, including failure recovery and workspace races. `npm run test:integration` launches a real API on port 8001 and frontend on port 5174, using temporary SQLite/upload/export storage. It covers single, labeled train/test, and unlabeled test workflows: upload, invalid CSV recovery, explicit setup steps, validation, preview, apply, downloads, and execution of downloaded Python code against the cleaned CSVs.

Install backend requirements and Playwright Chromium first. The integration runner selects `backend/.venv`, then the repository `.venv`, then `python`; set `DATAPREP_TEST_PYTHON` to a Python executable path to override this. Ports 8001 and 5174 must be free; existing servers are never reused. Test projects are deleted after each case, and temporary storage is removed on normal server shutdown. A force-killed process may leave only OS temporary files.

## API Base URL

The default API base URL is:

```text
http://127.0.0.1:8000
```

Override it with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```
