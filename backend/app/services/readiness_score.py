from app.services.issue_detector import IssueData


def calculate_readiness_score(issues: list[IssueData], default_score: float = 100.0) -> tuple[float, dict[str, float | int | str]]:
    penalties = {"critical": 12.0, "warning": 5.0, "info": 1.5}
    counts = {"critical": 0, "warning": 0, "info": 0}
    total_penalty = 0.0

    for issue in issues:
        if issue.severity in counts:
            counts[issue.severity] += 1
            total_penalty += penalties[issue.severity]

    score = max(0.0, float(default_score) - total_penalty)
    breakdown: dict[str, float | int | str] = {
        "critical_count": counts["critical"],
        "warning_count": counts["warning"],
        "info_count": counts["info"],
        "penalty": total_penalty,
        "method": "heuristic_issue_penalty",
    }
    return score, breakdown
