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

export const FORGE_REF_MIME = "application/x-forge-ref";

/** The length rides BESIDE the ref, never inside it: an AudioRef is an identity that gets serialised
 *  into ProjectV2, and a measurement has no business in it. A drop with no length is still a valid
 *  drop (a FILES row does not know one) -- lifecycle.addClip resolves it. (M9 T10) */
export const FORGE_DUR_MIME = "application/x-forge-dur";

export function writeForgeDrag(dt: DataTransfer, ref: AudioRef, durSec: number | null): void {
  dt.setData(FORGE_REF_MIME, JSON.stringify(ref));
  if (durSec !== null && Number.isFinite(durSec) && durSec > 0) {
    dt.setData(FORGE_DUR_MIME, String(durSec));
  }
}

/** `Number("")` is 0, not NaN, so the `raw > 0` half of the guard is what makes an absent length
 *  read as null rather than as zero. Both halves are load-bearing. */
export function readForgeDrag(
  dt: DataTransfer | null,
): { ref: AudioRef; durationSec: number | null } | null {
  if (!dt) return null;
  const ref = parseForgeRefPayload(dt.getData(FORGE_REF_MIME));
  if (!ref) return null;
  const raw = Number(dt.getData(FORGE_DUR_MIME));
  const durationSec = Number.isFinite(raw) && raw > 0 ? raw : null;
  return { ref, durationSec };
}
