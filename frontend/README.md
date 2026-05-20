# DataPrep Studio Frontend

React/Vite/TypeScript frontend for DataPrep Studio.

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

The Playwright suite covers dashboard/project navigation, upload-to-analysis flow, upload error display, issue suggestions, column charts, recommendation-to-pipeline step creation, preview, apply, and export navigation with mocked backend responses.

## API Base URL

The default API base URL is:

```text
http://127.0.0.1:8000
```

Override it with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```
