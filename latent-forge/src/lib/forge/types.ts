// TS mirror of the frozen HTTP contract, spec §6.1, field for field.
// eval/forge/contract.py is the Python side of the same shapes; if one changes,
// both change in the same commit.

export type AudioRef =
  | { kind: "upload"; sha256: string }
  | { kind: "render"; job_id: string; file: string }
  | { kind: "crop"; crop_id: string }
  | { kind: "file"; root: string; rel: string }
  | { kind: "path"; path: string };

export type LatentRef =
  | { kind: "crop"; crop_id: string }
  | { kind: "path"; path: string }
  | { kind: "audio"; audio: AudioRef };

export interface Envelope {
  points: [number, number, number, number];
  curves: [number, number, number];
}

export type ScheduleShape =
  | "model" | "logsnr" | "geometric" | "linear" | "log" | "exponential" | "cosine";

export interface ScheduleSpec {
  shape: ScheduleShape;
  rho: number;        // 0.1..15
  sigma_min: number;  // 0.001..0.5, < sigma_max
  lam_min: number;    // -12..0
  lam_max: number;    // 0..6, > lam_min
  stepped: boolean;
  plateaus: number;   // 2..24, integer
  tilt: number;       // 0..1
}

export interface RenderSettings {
  prompt: string;
  negative_prompt: string;
  steps: number;
  cfg_scale: number;
  seed: number;                              // -1 = resolve server-side
  apg_scale: number;
  cfg_interval_progress: [number, number];   // progress = 1 - sigma/sigma_0
  schedule: ScheduleSpec;
  scale_phi: number;
  sampler_type: string | null;               // null = objective default
  /**
   * §4.5 LENGTH, in seconds, <= 184. It belongs here and not in the tab's own
   * state because §9.3 says a `render` preset recalls every txt2audio parameter,
   * and the length a render was made at is one of them. On an A2A target the
   * clip supplies the length and this field is ignored.
   *
   * WIRE NAME: the existing server reads `duration` on /generate and /schedule,
   * so whoever builds a job payload sends `duration: settings.duration_sec`.
   */
  duration_sec: number;
}

export interface LatchSlot {
  head: string; kind: string; value: number;
  weight: number; start_pct: number; end_pct: number;
}

export interface LaneChain {
  latch_on: boolean;
  slots: [LatchSlot, LatchSlot];
  hparams: { rho: number; mu: number; gamma: number; n_iter: number; log_norms: boolean };
  film_on: boolean;
  film: { ckpt: string | null; gain: number; value: number };
  lora_on: boolean;
  lora: { ckpt_path: string | null; slot: number | null; strength: number };
  bungee_on: boolean;
  semitones: number;
}

export type JobOp =
  | "generate" | "a2a_track" | "a2a_mix" | "longform" | "decode" | "bend"
  | "a2a_clip" | "inpaint" | "commit";

export type JobState = "queued" | "running" | "done" | "error" | "cancelled";

/** = build_response() of the existing server. */
export interface JobResponse {
  status: string;
  job_id: string;
  files: string[];
  latents: string[];
  urls: string[];
  seed: number | null;
  timings: { total_sec: number; per_stage: Record<string, number> };
  warnings: string[];
  meta: Record<string, unknown>;
}

export interface Progress {
  job_id: string;
  op: string;
  stage: string;
  stage_index: number;
  stage_count: number;
  step: number;
  steps: number;
  steps_left_total: number;
  steps_total: number;
}

export interface JobRecord {
  ok: true;
  job_id: string;
  op: JobOp;
  payload: unknown;
  state: JobState;
  position: number | null;
  progress: Progress | null;
  result: JobResponse | null;
  error: string | null;
  created: number;
  started: number | null;
  finished: number | null;
}

// ---------------------------------------------------------------- project v2

export interface ForgeLane {
  index: 0 | 1 | 2 | 3;
  name: string;
  muted: boolean;
  solo: boolean;
  gain: number;
  chain: LaneChain;
}

export interface ForgeClip {
  id: string;
  lane: 0 | 1 | 2 | 3;
  start_sec: number;
  offset_sec: number;
  dur_sec: number;
  loop: boolean;
  audio: AudioRef;
  native_bpm: number | null;
  detune_cents: number;
  /**
   * SOURCE seconds, i.e. the UNSTRETCHED audio at `native_bpm`, exactly as
   * /forge/analyze returns them -- unlike `offset_sec`/`dur_sec`/`start_sec`,
   * which are timeline seconds in the STRETCHED domain (spec §7.3). A consumer
   * drawing or snapping to a downbeat must scale by the clip's own stretch
   * factor first; they are stored unstretched so that changing the project BPM
   * does not require re-analysing every clip.
   */
  downbeats_sec: number[];
  render: RenderSettings;
  a2a: null | { on: boolean; noise: number; envelope: Envelope };
  latentState: "none" | "valid" | "stale";
  history: AudioRef[];
}

export interface OverlapParams {
  curve: Envelope;
  chroma_xfade: boolean;
  override: boolean;
  steps: number;
  cfg: number;
  render: RenderSettings;
}

export interface MixSpec {
  order: "tree" | "cascade" | "quad";
  nodes: {
    M1: { interp: "lerp" | "slerp"; t: number };
    M2: { interp: "lerp" | "slerp"; t: number };
    MX: { interp: "lerp" | "slerp"; t: number };
  };
  quad_weights: [number, number, number, number];
}

export interface MasterChain {
  latch_on: boolean;
  head: string;
  gain: number;
  norm_on: boolean;
}

export interface RenderHistoryEntry {
  job_id: string;
  forge_job_id: string;
  file: string;
  label: string;
  kind: "gen" | "a2a" | "inpaint" | "mix";
  dur_sec: number;
  source_clip_id: string | null;
  created: number;
}

export interface ProjectV2 {
  version: 2;
  name: string;
  meter: { bpm: number; beatsPerBar: number };
  snap: string;
  view: { pxPerSec: number; scrollSec: number };
  lanes: ForgeLane[];
  clips: ForgeClip[];
  overlaps: Record<string, OverlapParams>;
  mix: MixSpec;
  master: MasterChain;
  defaults: RenderSettings;
  backbone: string;
  ckpt_path: string | null;
  renders: RenderHistoryEntry[];
  mixdown: number | null;
  preview: number | null;
  ui: { bottomTab: string; modules: string[]; sideOpen: boolean; terminal: string };
}

// ---------------------------------------------------------------- target seam

/**
 * What the PROMPT + SIGMA pane and ADVANCED SAMPLING are editing.
 *
 * Declared in M1 because M4 owns the settings store and M5 owns clips and
 * overlaps, and the two milestones are planned in parallel (spec §12). Without
 * this type they would each invent one and the panes would not compose.
 * `none` means the session defaults are being edited (spec §7.2).
 */
export type Target =
  | { kind: "none" }
  | { kind: "clip"; id: string }
  | { kind: "overlap"; key: string };
