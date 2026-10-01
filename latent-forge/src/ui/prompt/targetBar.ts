// Pure parts of the target bar (spec 4.5 item 1, 10 X11). Kept out of the
// component so the tag/colour/op rules are covered without mounting anything.

import type { Target } from "../../lib/forge/types";

export type TargetTag = "GENERATE" | "CLIP" | "A2A" | "INPAINT";

/** Spec 4.5: GENERATE turq, CLIP lane colour, A2A purple, INPAINT purple. */
export function targetTag(t: Target, a2aOn: boolean): TargetTag {
  if (t.kind === "none") return "GENERATE";
  if (t.kind === "overlap") return "INPAINT";
  return a2aOn ? "A2A" : "CLIP";
}

/**
 * Which CSS custom property colours the tag. CLIP uses the target's OWN lane,
 * never lane 1 by default -- a clip on lane 3 must not borrow lane 1's colour
 * just because this component does not know the arrangement.
 */
export function targetTagColorVar(tag: TargetTag, lane: 0 | 1 | 2 | 3): string {
  if (tag === "GENERATE") return "--turq-strong";
  if (tag === "CLIP") return `--lane${lane + 1}`;
  return "--purple-strong"; // A2A and INPAINT
}

/**
 * Spec 10 X11 -- the ops the existing app already had, kept reachable here. All four are
 * always selectable: the only op-related disabling the spec defines belongs to the RENDER
 * control (7.1, `turn A2A on or choose an op`), which is M9's, and 7.3 says staleness "is
 * informational (badge) and no longer blocks anything". A per-option latent gate here would
 * be a rule this app has invented for itself.
 */
export const CLIP_OPS = ["generate", "decode", "longform", "bend"] as const;
