from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class LoadedCsv:
    dataframe: pd.DataFrame
    raw_bytes: bytes
    file_size_bytes: int


class CsvValidationError(ValueError):
    pass


def validate_csv_filename(filename: str, allowed_extension: str = ".csv") -> None:
    if not filename:
        raise CsvValidationError("Uploaded file must have a filename")
    if Path(filename).suffix.lower() != allowed_extension:
        raise CsvValidationError(f"Only {allowed_extension} files are supported")


def load_csv_upload(raw_bytes: bytes, max_upload_mb: int) -> LoadedCsv:
    max_bytes = max_upload_mb * 1024 * 1024
    file_size_bytes = len(raw_bytes)
    if file_size_bytes == 0:
        raise CsvValidationError("Uploaded CSV is empty")
    if file_size_bytes > max_bytes:
        raise CsvValidationError(f"Uploaded CSV exceeds the {max_upload_mb} MB limit")

    try:
        dataframe = pd.read_csv(BytesIO(raw_bytes))
    except Exception as exc:
        raise CsvValidationError(f"Could not parse CSV: {exc}") from exc

    if dataframe.empty and len(dataframe.columns) == 0:
        raise CsvValidationError("Uploaded CSV has no columns")

    return LoadedCsv(dataframe=dataframe, raw_bytes=raw_bytes, file_size_bytes=file_size_bytes)


def read_csv_file(path: str | Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except FileNotFoundError as exc:
        raise CsvValidationError("Stored CSV file was not found") from exc
    except Exception as exc:
        raise CsvValidationError(f"Could not read stored CSV: {exc}") from exc
