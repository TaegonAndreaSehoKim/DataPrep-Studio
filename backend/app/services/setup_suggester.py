from dataclasses import dataclass

import pandas as pd

from app.schemas import DatasetSetupSuggestionOut, TargetCandidateOut
from app.services.profiler import infer_column_type


MISSING_TOKEN_CANDIDATES = ["?", "NA", "N/A", "unknown", "Unknown", "UNK", "-", "--", "null", "None", "missing"]
TARGET_NAME_HINTS = ["target", "label", "class", "outcome", "response", "result", "y", "quality"]
ID_NAME_HINTS = ["id", "uuid", "guid", "key", "identifier"]
CATEGORICAL_CODE_HINTS = ["zip", "zipcode", "postal", "postcode", "code", "fips"]


@dataclass(frozen=True)
class _Candidate:
    column_name: str
    score: float
    inferred_type: str
    unique_count: int
    reason: str


def _normalized_name(column: object) -> str:
    return str(column).strip().lower().replace(" ", "_")


def _suggest_missing_tokens(df: pd.DataFrame) -> list[str]:
    found: list[str] = []
    object_columns = df.select_dtypes(include=["object", "string"]).columns
    for token in MISSING_TOKEN_CANDIDATES:
        count = 0
        for column in object_columns:
            count += int((df[column].dropna().astype(str).str.strip() == token).sum())
        if count:
            found.append(token)
    return found


def _suggest_type_overrides(df: pd.DataFrame) -> dict[str, str]:
    overrides: dict[str, str] = {}
    row_count = max(len(df), 1)
    for column in df.columns:
        name = _normalized_name(column)
        series = df[column]
        unique_count = int(series.nunique(dropna=True))
        inferred_type = infer_column_type(series)
        if any(hint in name for hint in CATEGORICAL_CODE_HINTS) and inferred_type == "numeric":
            overrides[str(column)] = "categorical"
        elif series.dtype == object and series.dropna().astype(str).str.match(r"^0\d+").any():
            overrides[str(column)] = "categorical"
        elif any(hint == name or name.endswith(f"_{hint}") for hint in ID_NAME_HINTS) and unique_count / row_count > 0.75:
            overrides[str(column)] = "categorical"
    return overrides


def _suggest_ignored_columns(df: pd.DataFrame) -> list[str]:
    ignored: list[str] = []
    row_count = max(len(df), 1)
    for column in df.columns:
        name = _normalized_name(column)
        unique_count = int(df[column].nunique(dropna=True))
        if any(hint == name or name.endswith(f"_{hint}") for hint in ID_NAME_HINTS) and unique_count / row_count > 0.90:
            ignored.append(str(column))
    return ignored


def _target_candidates(df: pd.DataFrame) -> list[_Candidate]:
    row_count = max(len(df), 1)
    candidates: list[_Candidate] = []
    for index, column in enumerate(df.columns):
        series = df[column]
        name = _normalized_name(column)
        unique_count = int(series.nunique(dropna=True))
        unique_ratio = unique_count / row_count
        inferred_type = infer_column_type(series, str(column))
        if unique_count <= 1 or unique_ratio > 0.95:
            continue

        score = 0.0
        reasons: list[str] = []
        if any(hint == name or name.endswith(f"_{hint}") or hint in name for hint in TARGET_NAME_HINTS):
            score += 0.55
            reasons.append("name looks target-like")
        if index == len(df.columns) - 1:
            score += 0.25
            reasons.append("last column")
        if inferred_type in {"categorical", "boolean"}:
            score += 0.20
            reasons.append("discrete values")
        elif inferred_type == "numeric" and unique_count <= max(20, int(row_count * 0.10)):
            score += 0.12
            reasons.append("low-cardinality numeric values")
        if any(hint in name for hint in ID_NAME_HINTS):
            score -= 0.40
            reasons.append("identifier-like name")
        if inferred_type == "text":
            score -= 0.25
            reasons.append("free-text column")

        if score > 0:
            candidates.append(
                _Candidate(
                    column_name=str(column),
                    score=round(min(score, 1.0), 4),
                    inferred_type=inferred_type,
                    unique_count=unique_count,
                    reason=", ".join(reasons),
                )
            )

    return sorted(candidates, key=lambda item: item.score, reverse=True)


def _problem_type_for_target(df: pd.DataFrame, target_column: str | None) -> str:
    if not target_column or target_column not in df.columns:
        return "unknown"
    series = df[target_column]
    inferred_type = infer_column_type(series, target_column)
    unique_count = int(series.nunique(dropna=True))
    row_count = max(len(series), 1)
    if inferred_type in {"categorical", "boolean"}:
        return "classification"
    if inferred_type == "numeric" and unique_count <= max(20, int(row_count * 0.10)):
        return "classification"
    if inferred_type == "numeric":
        return "regression"
    return "unknown"


def suggest_dataset_setup(dataset_file_id: int, df: pd.DataFrame) -> DatasetSetupSuggestionOut:
    candidates = _target_candidates(df)
    recommended_target = candidates[0].column_name if candidates else (str(df.columns[-1]) if len(df.columns) else None)
    problem_type = _problem_type_for_target(df, recommended_target)
    missing_tokens = _suggest_missing_tokens(df)
    overrides = _suggest_type_overrides(df)
    ignored = _suggest_ignored_columns(df)

    notes: list[str] = []
    if recommended_target:
        notes.append(f"Recommended target: {recommended_target}.")
    if missing_tokens:
        notes.append("Detected placeholder strings that commonly represent missing values.")
    if overrides:
        notes.append("Detected code-like columns that are safer as categorical values.")
    if ignored:
        notes.append("Detected ID-like columns that are usually excluded from modeling.")

    return DatasetSetupSuggestionOut(
        dataset_file_id=dataset_file_id,
        recommended_target_column=recommended_target,
        recommended_problem_type=problem_type,  # type: ignore[arg-type]
        target_candidates=[
            TargetCandidateOut(
                column_name=item.column_name,
                score=item.score,
                inferred_type=item.inferred_type,  # type: ignore[arg-type]
                unique_count=item.unique_count,
                reason=item.reason,
            )
            for item in candidates[:5]
        ],
        missing_value_tokens=missing_tokens,
        column_type_overrides=overrides,  # type: ignore[arg-type]
        ignored_columns=ignored,
        notes=notes,
    )
