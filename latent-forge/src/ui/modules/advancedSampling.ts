// Pure parts of ADVANCED SAMPLING (spec 4.6 item 4, 5.3): which fields the current shape
// makes meaningful, and picking one issue out of Task 3's validateSchedule list for a
// specific field, so the component only ever renders "the" issue for a field, not the list.

import type { ScheduleIssue } from "../../lib/sampling/scheduleRules";

/** Lambda min/max describe a logSNR interval; every other shape ignores them (spec 5.3's
 * schedule table only reads lam_min/lam_max under "logsnr"). */
export function shapeUsesLambda(shape: string): boolean {
  return shape === "logsnr";
}

export function fieldIssue(
  issues: readonly ScheduleIssue[],
  field: string,
): { severity: "error" | "warning"; message: string } | null {
  const found = issues.find((i) => i.field === field);
  return found ? { severity: found.severity, message: found.message } : null;
}
