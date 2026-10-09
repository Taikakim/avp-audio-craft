import { fetchLatchHeads, type LatchHeadInfo } from "../chains/latch";
import type { Target } from "../forge/types";
import { arrangement } from "../stores/arrangement.svelte";
import { settings } from "../stores/settings.svelte";
import { view } from "../stores/view.svelte";
import { PAD_SEC, type DispatchWorld } from "./dispatch";

/** Task 6 built this inline in PreviewContainer; Task 9 needs the identical world for
 *  `▸ INPAINT OVERLAP`, and two copies of §7.1's inputs would drift on the first spec change.
 *  Called from inside a $derived.by, every store read below is still tracked -- the reads happen
 *  during derivation, and moving them behind a plain function call does not change that. */
export function dispatchWorld(
  target: Target,
  heads: Record<string, LatchHeadInfo>,
): DispatchWorld {
  const clip = target.kind === "clip" ? arrangement.clips.find((c) => c.id === target.id) ?? null : null;
  const overlap = target.kind === "overlap"
    ? arrangement.overlaps.find((o) => o.key === target.key) ?? null
    : null;
  return {
    settings: settings.current(target),
    cfgScale: settings.effectiveCfg(target),
    clip,
    // A clip renders through ITS lane's chain; a plain prompt render (no target) through the
    // active lane's, so a LatCH render needs no clip and no A2A.
    lane: clip ? arrangement.lanes[clip.lane] : target.kind === "none" ? arrangement.lanes[view.activeLane] ?? null : null,
    heads,
    ckptPath: settings.ckptPath,
    overlap,
    // Non-seeding read -- this function runs inside a $derived.by (Global constraint 4).
    overlapParams: overlap ? arrangement.peekOverlapParams(overlap.key) : null,
    clipById: (id: string) => arrangement.clips.find((c) => c.id === id) ?? null,
    arcPrompt: settings.current(target).prompt,
    bendOps: [] as unknown[],
    padSec: PAD_SEC,
  };
}

export { fetchLatchHeads };
