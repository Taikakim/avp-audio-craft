// Pure parts of the sigma column (spec 4.5 item 3, 5.3) and the tab's own defaults, kept
// out of the components so the request-building and note-priority rules are covered
// without mounting anything or faking a debounce timer.

import type { LatchSlot, ScheduleSpec } from "../../lib/forge/types";
import type { ScheduleRequest } from "../../lib/sampling/scheduleClient.svelte";
import { flatPlateauNote } from "../../lib/sampling/scheduleRules";

/** The drawing's own canvas attributes (v3:404, width="320" height="180"). SigmaGraph.svelte
 * (Task 7) only measures its own DOM box when `input` is null; once this column has a
 * schedule to draw, it must supply a width/height itself, and it has no ref to a canvas it
 * does not own -- so it supplies the drawing's own nominal geometry rather than guessing at
 * a live pixel size. See this task's Open Questions entry. */
export const SIGMA_GRAPH_WIDTH = 320;
export const SIGMA_GRAPH_HEIGHT = 180;

export const STALE_SHAPE_NOTE = "schedule shape is charted from M3 onward";

/** Every argument lands in its own request field. `duration` is never defaulted or
 * omitted -- the Global Constraints say omitting it silently charts the server's 47s
 * default, and this is the one function in the milestone that assembles the request body. */
export function buildScheduleRequest(
  steps: number,
  duration: number,
  sigmaMax: number,
  samplerType: string | null,
  schedule: ScheduleSpec,
): ScheduleRequest {
  return { steps, duration, sigma_max: sigmaMax, sampler_type: samplerType, schedule };
}

/**
 * Spec 4.5's SIGMA column note is the first of three things that could be wrong, in this
 * order: the client actually failed; the server may not be honouring the requested shape
 * yet (Global Constraints -- until M3, only "model" is true); or the schedule itself is
 * flagged by Task 3's flat-plateau rule. Only one shows at a time -- showing all three would
 * bury the one that matters.
 */
export function sigmaNote(
  error: string | null,
  staleShape: boolean,
  spec: ScheduleSpec,
  samplerType: string | null,
): string | null {
  if (error !== null) return error;
  if (staleShape) return STALE_SHAPE_NOTE;
  return flatPlateauNote(spec, samplerType);
}

/** Spec 4.5's LatCH slot legend: the slot's own head name, or an em dash for a slot that
 * is absent, unset, or explicitly "none". Active-ness (Task 2's isLatchActive) is not the
 * test here -- the drawing's legend names whatever is IN the slot, active or not. */
export function slotLegendLabel(slot: LatchSlot | undefined): string {
  if (!slot) return "—";
  if (slot.head === "" || slot.head === "none") return "—";
  return slot.head;
}
