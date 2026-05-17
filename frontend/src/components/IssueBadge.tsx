import type { Issue } from "../api/types";

export function IssueBadge({ severity }: { severity: Issue["severity"] }) {
  return <span className={`issue-badge issue-${severity}`}>{severity}</span>;
}
