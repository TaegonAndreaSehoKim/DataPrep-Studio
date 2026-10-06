"""Start a loopback-only API with disposable database and storage for Playwright."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="dataprep-browser-") as directory:
        root = Path(directory)
        os.environ.update({
            "DATABASE_URL": f"sqlite:///{root / 'browser.db'}",
            "STORAGE_DIR": str(root / "storage"),
            "UPLOAD_DIR": str(root / "uploads"),
            "EXPORT_DIR": str(root / "exports"),
            "CORS_ORIGINS": json.dumps(["http://127.0.0.1:5174"]),
        })
        import uvicorn
        from app.database import reset_database_engine

        try:
            uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="warning")
        finally:
            reset_database_engine()


if __name__ == "__main__":
    main()
