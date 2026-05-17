def generate_report(config: dict[str, object], before_summary: dict[str, object], after_summary: dict[str, object], step_effects: list[dict[str, object]], warnings: list[str]) -> str:
    lines = [
        "# DataPrep Studio Preprocessing Report",
        "",
        "## Project",
        f"- Project ID: {config.get('project_id')}",
        f"- Pipeline ID: {config.get('pipeline_id')}",
        f"- Mode: {config.get('mode')}",
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
        lines.append(f"- Step {step.get('step_id')}: `{step.get('operation_type')}` on {step.get('columns')}")

    lines.extend(
        [
            "",
            "## Before Summary",
            f"```json\n{before_summary}\n```",
            "",
            "## After Summary",
            f"```json\n{after_summary}\n```",
            "",
            "## Step Effects",
        ]
    )
    for effect in step_effects:
        lines.append(f"- {effect.get('summary')}")

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
