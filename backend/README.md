# DataPrep Studio Backend

FastAPI backend for the DataPrep Studio MVP.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```powershell
uvicorn app.main:app --reload
```

## Test

```powershell
python -m pytest -q
```

## Current Scaffold

- FastAPI app setup
- pydantic-settings config
- SQLAlchemy SQLite session setup
- ORM model definitions
- Pydantic API schemas
- health, dashboard, and project CRUD routers
- placeholder router modules for the remaining MVP API areas
- local storage directories for uploads and exports
