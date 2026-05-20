import json
from typing import Any


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _json_inline(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def generate_report(config: dict[str, object], before_summary: dict[str, object], after_summary: dict[str, object], step_effects: list[dict[str, object]], warnings: list[str]) -> str:
    lines = [
        "# DataPrep Studio Preprocessing Report",
        "",
        "## Project",
        f"- Project ID: {config.get('project_id')}",
        f"- Pipeline ID: {config.get('pipeline_id')}",
        f"- Pipeline name: {config.get('pipeline_name') or 'not specified'}",
        f"- Mode: {config.get('mode')}",
        f"- Config schema: {config.get('schema_version') or 'legacy'}",
        "",
        "## Dataset",
        f"- Input files: {', '.join(config.get('input_file_names', []))}",
        "",
        "## Target / Problem Type",
        f"- Target column: {config.get('target_column') or 'not specified'}",
        f"- Problem type: {config.get('problem_type')}",
        "",
        "## Pipeline Steps",
    ]
    for step in config.get("steps", []):
        if not isinstance(step, dict):
            continue
        columns = step.get("columns") or []
        params = step.get("params") or {}
        lines.append(f"- Step {step.get('step_id')}: `{step.get('operation_type')}`")
        lines.append(f"  - Columns: {', '.join(str(column) for column in columns) if columns else 'none'}")
        lines.append(f"  - Params: `{_json_inline(params)}`")
    if not config.get("steps"):
        lines.append("- No enabled steps were exported.")

    lines.extend(
        [
            "",
            "## Before Summary",
            f"```json\n{_json_block(before_summary)}\n```",
            "",
            "## After Summary",
            f"```json\n{_json_block(after_summary)}\n```",
            "",
            "## Step Effects",
        ]
    )
    for effect in step_effects:
        summary = effect.get("summary") if isinstance(effect, dict) else None
        lines.append(f"- {summary or _json_block(effect)}")
    if not step_effects:
        lines.append("- No step effects were recorded.")

    lines.extend(["", "## Warnings"])
    if warnings:
        lines.extend([f"- {warning}" for warning in warnings])
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Exported Files",
        ]
    )
    for name in config.get("output_file_names", []):
        lines.append(f"- {name}")

    lines.extend(
        [
            "",
            "## Notes on Leakage-Safe Train/Test Processing",
            "In train/test mode, preprocessing statistics are fit on train only and applied to test.",
        ]
    )
    return "\n".join(lines) + "\n"
