// Pure vocabulary for the statistics ANALYSE header (spec §4.4): which lanes
// can be analysed, their button labels, and the exact strings that feed the
// DOM contract M1 T13 already fixed -- [data-stats-lane="1"|"2"|"3"|"4"|"all"].

export type LaneSel = 1 | 2 | 3 | 4 | "all";

export const LANE_SELECTIONS: readonly LaneSel[] = [1, 2, 3, 4, "all"];

/** Button copy: "LANE 1".."LANE 4", "ALL". */
export function laneSelLabel(s: LaneSel): string {
  return s === "all" ? "ALL" : `LANE ${s}`;
}

/** Feeds `[data-stats-lane]`, which M1 T13 already fixed as "1"|"2"|"3"|"4"|"all". */
export function laneSelAttr(s: LaneSel): string {
  return String(s);
}
