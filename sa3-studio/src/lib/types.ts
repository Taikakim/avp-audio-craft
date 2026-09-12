// Core data model for SA3 Studio.
//
// Authoritative workflow (Kim, 2026-09-10 -- see docs/sa3-studio/ORIENTATION.md §3):
// clips live on a timeline; THE TIMELINE IS AUDIO. Every clip has an audio
// representation for scrub/preview (imported directly, or decoded once from a
// latent). Preview is explicitly NOT the eventual output -- it only proves
// onset/downbeat alignment before a RENDER commits the real op server-side.
//
// SAME latents are NOT translation-invariant (sub-frame roll moves 212/256
// dims; phase is only ~2-plane SO(2)-accurate below ~7kHz). A latent is valid
// ONLY at the offset it was encoded at. So a latent-backed clip tracks whether
// its current timeline position still matches the position it was encoded at
// -- move it, and it goes `stale` until re-encoded by the next RENDER.

export const SAMPLE_RATE = 44100;
// Latent frame rate (44100 / 4096 = 10.7666 Hz, i.e. 92.9ms/frame). This does
// NOT quantise audio-domain placement -- Kim corrected an earlier draft on
// exactly this point. It only matters when *encoding*: store the frame index
// plus the leftover sample residual so a commit-time encode is exact.
export const LATENT_HOP = 4096;

export type LatentState = "none" | "valid" | "stale";

export interface LatentOffset {
  /** floor(offsetSec * SAMPLE_RATE / LATENT_HOP) */
  frame: number;
  /** offsetSec*SAMPLE_RATE - frame*LATENT_HOP, i.e. the sub-frame remainder in samples */
  residualSamples: number;
}

export function toLatentOffset(offsetSec: number): LatentOffset {
  const totalSamples = Math.round(offsetSec * SAMPLE_RATE);
  const frame = Math.floor(totalSamples / LATENT_HOP);
  return { frame, residualSamples: totalSamples - frame * LATENT_HOP };
}

export function fromLatentOffset(o: LatentOffset): number {
  return (o.frame * LATENT_HOP + o.residualSamples) / SAMPLE_RATE;
}

/** Per-clip render parameters -- deliberately NOT global. The design handoff's
 * prototype kept prompt/steps/cfg/seed in one global block; PLAN_CORRECTIONS.md
 * §5 flags that as a bug the real app must fix (each clip can be a different
 * generation). */
export interface RenderParams {
  prompt: string;
  negativePrompt?: string;
  steps: number;
  cfgScale: number;
  seed: number; // -1 = resolve server-side (resolve_seed)
  samplerType?: string;
  distShift?: number;
}

export const DEFAULT_RENDER_PARAMS: RenderParams = {
  prompt: "",
  steps: 24,
  cfgScale: 6.0,
  seed: -1,
};

export type ClipSource =
  | { kind: "audio-file"; name: string; url: string } // user-imported audio, decoded client-side
  | { kind: "crop"; cropId: string } // a pre-extracted latent crop known to the render server (GET /crops)
  | { kind: "render"; jobId: string; filename: string }; // output of a committed RENDER (GET /audio/{job}/{filename})

export interface Clip {
  id: string;
  laneId: string;
  /** Timeline position in seconds. Audio-domain, unconstrained by the latent frame. */
  startSec: number;
  durationSec: number;
  source: ClipSource;
  /** Set once a clip is backed by a latent (crop or a render that returned latents). */
  latentState: LatentState;
  /** The offset this clip's latent was last encoded/valid at, if any. */
  encodedAt?: LatentOffset;
  /** URL the transport can decodeAudioData() from -- always audio, per "the timeline is audio". */
  previewUrl?: string;
  render: RenderParams;
  /** Set while a RENDER is in flight for this clip. */
  pendingJobId?: string;
}

// Four lanes, matching the four-stem prior art (mir-feature-extraction's
// latent_crossfader.py: STEMS = [drums, bass, other, vocals]) -- see
// PLAN_CORRECTIONS.md §4b. Lane 0 doubles as the "master"/full-mix anchor.
export const LANE_IDS = ["drums", "bass", "other", "vocals"] as const;
export type LaneId = (typeof LANE_IDS)[number];

export interface Lane {
  id: LaneId;
  label: string;
  muted: boolean;
  solo: boolean;
  gain: number; // 0..1, audio-domain preview gain only -- never sent to the server
}

export function defaultLanes(): Lane[] {
  return LANE_IDS.map((id) => ({
    id,
    label: id[0].toUpperCase() + id.slice(1),
    muted: false,
    solo: false,
    gain: 1.0,
  }));
}

let _idCounter = 0;
/** Monotonic id generator -- Date.now()/crypto.randomUUID() are fine at
 * runtime, but this stays trivially testable and avoids a dependency. */
export function nextId(prefix: string): string {
  _idCounter += 1;
  return `${prefix}_${Date.now().toString(36)}_${_idCounter}`;
}
