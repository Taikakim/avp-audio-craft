// The two bits of MODEL STAGE / SEED logic that are not just "read a RANGES
// entry and call settings.patch" (spec 5.1, 5.3).

import { RANGES } from "../../lib/sampling/scheduleRules";

/**
 * A fresh integer within RANGES.seed (spec 5.1). `rand` defaults to
 * Math.random and exists as a parameter purely so the boundary behaviour --
 * and only the boundary behaviour -- can be pinned in a test without mocking
 * a global.
 */
export function randomSeed(rand: () => number = Math.random): number {
  const { min, max } = RANGES.seed;
  return Math.min(max, min + Math.floor(rand() * (max - min + 1)));
}

/**
 * Spec 5.3's inline confirm, verbatim, and the SAME wording for both
 * directions -- entering POST and returning to BASE both rebuild the
 * backbone. The switch, rather than a bare return, is so a future per-stage
 * caveat has somewhere to go without touching every call site.
 */
export function stageConfirmMessage(next: "POST" | "BASE"): string {
  switch (next) {
    case "POST":
    case "BASE":
      return "rebuilds the model — continue?";
  }
}
