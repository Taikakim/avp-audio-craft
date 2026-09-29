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

/**
 * What a RENDER actually runs. Each maps to one real endpoint on
 * explorer_render_server.py -- there is deliberately no option here that the
 * server cannot currently do (no n-way latent mixdown, no /encode, no
 * /inpaint; those are M7 work we'd author server-side first).
 */
export type RenderOp = "generate" | "decode" | "a2a_track" | "a2a_mix" | "longform" | "bend";

export const RENDER_OPS: { value: RenderOp; label: string; needs: string }[] = [
  { value: "generate", label: "generate — text → audio", needs: "prompt" },
  { value: "decode", label: "decode — latent → audio", needs: "a crop or latent path" },
  { value: "a2a_track", label: "a2a — audio → audio pass", needs: "a server-side audio path + prompt" },
  { value: "a2a_mix", label: "a2a mix — A→B transition", needs: "two server-side audio paths" },
  { value: "longform", label: "longform — prompt arc", needs: "a schedule string" },
  { value: "bend", label: "bend — latent data-bending", needs: "a latent + at least one op" },
];

/** One entry of /bend's `ops` list. Vocabulary read from eval/latent_bend.py. */
export interface BendOp {
  op: "channel_swap" | "channel_roll" | "noise" | "quantize" | "segment_shuffle" | "band_scale";
  amount?: number;
  k?: number;
  shift?: number;
  bits?: number;
  seg?: number;
  channels?: number[];
}

export const BEND_OP_NAMES: BendOp["op"][] = [
  "channel_swap",
  "channel_roll",
  "noise",
  "quantize",
  "segment_shuffle",
  "band_scale",
];

/** Per-clip render parameters -- deliberately NOT global. The design handoff's
 * prototype kept prompt/steps/cfg/seed in one global block; PLAN_CORRECTIONS.md
 * §5 flags that as a bug the real app must fix (each clip can be a different
 * generation). */
export interface RenderParams {
  op: RenderOp;
  prompt: string;
  negativePrompt?: string;
  steps: number;
  cfgScale: number;
  seed: number; // -1 = resolve server-side (resolve_seed)
  samplerType?: string;
  distShift?: number;
  /** a2a_track / a2a_mix / longform */
  noiseLevel: number;
  apgScale?: number;
  /** a2a_mix: the B side, and the region prompt the transition is rendered under */
  mixBPath?: string;
  promptRegion?: string;
  /** longform */
  schedule?: string;
  windowSec?: number;
  overlapSec?: number;
  xfadeSec?: number;
  /** bend */
  bendOps?: BendOp[];
}

export const DEFAULT_RENDER_PARAMS: RenderParams = {
  op: "generate",
  prompt: "",
  steps: 24,
  cfgScale: 6.0,
  seed: -1,
  noiseLevel: 0.4,
};

export type ClipSource =
  | { kind: "empty" } // a slot on the timeline with nothing in it yet -- a generate/longform will fill it
  | { kind: "audio-file"; name: string; url: string } // user-imported audio, decoded client-side
  | { kind: "crop"; cropId: string } // a pre-extracted latent crop known to the render server (GET /crops)
  | { kind: "render"; jobId: string; filename: string }; // output of a committed RENDER (GET /audio/{job}/{filename})

/** Label for a clip's source, for the timeline and the inspector. */
export function sourceLabel(source: ClipSource): string {
  switch (source.kind) {
    case "empty":
      return "empty";
    case "audio-file":
      return source.name;
    case "crop":
      return source.cropId;
    case "render":
      return source.filename;
  }
}

export interface Clip {
  id: string;
  laneId: string;
  /** Timeline position in seconds. Audio-domain, unconstrained by the latent frame. */
  startSec: number;
  durationSec: number;
  /** Trim into the source material, in seconds from its start. */
  offsetSec: number;
  source: ClipSource;
  /** Set once a clip is backed by a latent (crop or a render that returned latents). */
  latentState: LatentState;
  /** The offset this clip's latent was last encoded/valid at, if any. */
  encodedAt?: LatentOffset;
  /** URL the transport can decodeAudioData() from -- always audio, per "the timeline is audio". */
  previewUrl?: string;
  /**
   * Absolute path ON THE SERVER, when one is known. This is the hinge for
   * a2a: /a2a_track and /a2a_mix take `audio_path` and resolve it with
   * require_path() server-side -- they do NOT accept an upload, and the server
   * has no ingest route. So a clip is only a2a-able once the server can see
   * its audio: either it came back from a job (build_response's `files` are
   * absolute server paths), or the path was typed in by hand.
   */
  serverPath?: string;
  /** Server-side path to this clip's latent, when it has one (job `latents`). */
  latentPath?: string;
  /** Native tempo, for MATCH BPM. No /analyze endpoint exists -- user-entered. */
  bpm?: number;
  /** First downbeat, seconds into the clip's own material. User-entered. */
  downbeatSec?: number;
  render: RenderParams;
  /** Set while a RENDER is in flight for this clip. */
  pendingJobId?: string;
  /** Human-readable note from the last render (timings, warnings). */
  lastRenderNote?: string;
}

// Four lanes, matching the four-stem prior art (mir-feature-extraction's
// latent_crossfader.py: STEMS = [drums, bass, other, vocals]) -- see
// PLAN_CORRECTIONS.md §4b. Lane 0 doubles as the "master"/full-mix anchor.
export const LANE_IDS = ["drums", "bass", "other", "vocals"] as const;
export type LaneId = (typeof LANE_IDS)[number];

// Same four hues as LANE_META in the design handoff (docs/sa3-studio/design_handoff/
// SA3 Studio v3.dc.html) -- purple/green/turq/neutral, in that order -- so a clip's
// lane is visually identifiable the same way there and here.
export const LANE_COLORS = ["var(--purple)", "var(--green)", "var(--accent)", "var(--neutral-lane)"] as const;

export interface Lane {
  id: LaneId;
  label: string;
  color: string;
  muted: boolean;
  solo: boolean;
  gain: number; // 0..1, audio-domain preview gain only -- never sent to the server
}

export function defaultLanes(): Lane[] {
  return LANE_IDS.map((id, i) => ({
    id,
    label: id[0].toUpperCase() + id.slice(1),
    color: LANE_COLORS[i % LANE_COLORS.length],
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
