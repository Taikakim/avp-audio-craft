// Lane header text and the FILES/preview/MIXDOWN drop payload (spec 4.3, M1
// T15's application/x-forge-ref convention).

import { isAudioRef } from "../forge/guards";
import type { AudioRef, ForgeClip } from "../forge/types";

function isLatentBacked(c: ForgeClip): boolean {
  return c.audio.kind === "crop" || c.latentState !== "none";
}

/** Spec 4.3: count label "N clips · latent/audio". */
export function laneCountLabel(clips: ForgeClip[]): string {
  if (clips.length === 0) return "empty lane";
  const latent = clips.filter(isLatentBacked).length;
  const audio = clips.length - latent;
  const parts: string[] = [];
  if (latent) parts.push(`${latent} latent`);
  if (audio) parts.push(`${audio} audio`);
  return `${clips.length} clip${clips.length === 1 ? "" : "s"} · ${parts.join(" ")}`;
}

/**
 * Which clip CLIP BPM / DETUNE act on: the selection, if it is in this lane
 * (v3 1660-1678), else the lane's first clip; null when the lane is empty.
 */
export function bpmTargetClip(
  clips: ForgeClip[],
  selected: ForgeClip | undefined,
  laneIndex: number,
): ForgeClip | null {
  if (selected && selected.lane === laneIndex) return selected;
  return clips.find((c) => c.lane === laneIndex) ?? null;
}

/**
 * The drop slot and the lane canvas both accept a ref dropped from FILES, the
 * preview container or the MIXDOWN slot, carried as JSON under the
 * "application/x-forge-ref" mime type. Returns null for anything malformed or
 * anything that is not a valid AudioRef (a LatentRef pointing at a raw .npy
 * path, for instance, needs an encode/decode step this milestone does not
 * have a route for — see the Open Questions note).
 */
export function parseForgeRefPayload(raw: string): AudioRef | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    return isAudioRef(parsed) ? parsed : null;
  } catch {
    return null;
  }
}
