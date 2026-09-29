// Every value here is quoted from the spec. Keep the section reference on the
// line so a reviewer can check it without opening another file.

import type {
  Envelope, LaneChain, MasterChain, MixSpec, OverlapParams, RenderSettings, ScheduleSpec,
} from "./types";

/** spec §2.2 / X12 — 16 GB display card, T < 2048. */
export const LENGTH_CAP_SEC = 184;

/** spec §5.3 — the ScheduleSpec block's stated defaults. */
export const SCHEDULE_DEFAULT: ScheduleSpec = {
  shape: "model",
  rho: 1.0,
  sigma_min: 0.01,
  lam_min: -6.2,
  lam_max: 2.0,
  stepped: false,
  plateaus: 6,
  tilt: 0.15,
};

/** spec §5.3 — BASE = medium-base, the lab's validated defaults (X7). */
export const BASE_DEFAULTS: RenderSettings = {
  prompt: "",
  negative_prompt: "",
  steps: 24,
  cfg_scale: 6.0,
  seed: -1,
  apg_scale: 1.0,
  cfg_interval_progress: [0, 1],
  schedule: { ...SCHEDULE_DEFAULT },
  scale_phi: 0,
  sampler_type: "euler",
  duration_sec: 47.556,   // T=512 exactly (MASTER: crop lengths are frame multiples)
};

/** spec §5.3 — POST = medium (rf_denoiser); guidance is distilled in, so CFG is sent as 1.0. */
export const POST_DEFAULTS: RenderSettings = {
  prompt: "",
  negative_prompt: "",
  steps: 8,
  cfg_scale: 1.0,
  seed: -1,
  apg_scale: 1.0,
  cfg_interval_progress: [0, 1],
  schedule: { ...SCHEDULE_DEFAULT, shape: "logsnr", rho: 1, lam_min: -6.2, lam_max: 2.0 },
  scale_phi: 0,
  sampler_type: "pingpong",
  duration_sec: 47.556,
};

/** The session default before a backbone is known. BASE is the resident model (spec §2.2). */
export const RENDER_DEFAULTS: RenderSettings = BASE_DEFAULTS;

/** spec §5.2 — crossfade curve default (also §7.2's overlap default). */
export const ENVELOPE_DEFAULT: Envelope = { points: [0, 0.35, 0.7, 1], curves: [0, 0, 0] };

/** spec §5.2 — a2a noise envelope default: flat at 0.4. */
export const A2A_ENVELOPE_DEFAULT: Envelope = { points: [0.4, 0.4, 0.4, 0.4], curves: [0, 0, 0] };

/** spec §7.2 — per-overlap defaults. */
export const OVERLAP_DEFAULT: OverlapParams = {
  curve: { ...ENVELOPE_DEFAULT, points: [...ENVELOPE_DEFAULT.points], curves: [...ENVELOPE_DEFAULT.curves] },
  chroma_xfade: true,
  override: false,
  steps: 28,
  cfg: 3.0,
  render: BASE_DEFAULTS,
};

/** spec §5.5 — LANE CHAIN. Slider defaults: weight 1, start 0 %, end 60 %. */
export const CHAIN_DEFAULTS: LaneChain = {
  latch_on: false,
  slots: [
    { head: "none", kind: "constant", value: 1.0, weight: 1, start_pct: 0, end_pct: 0.6 },
    { head: "none", kind: "constant", value: 1.0, weight: 1, start_pct: 0, end_pct: 0.6 },
  ],
  hparams: { rho: 1, mu: 1, gamma: 0.3, n_iter: 4, log_norms: false },
  film_on: false,
  // gain 1.75 = the server's FILM_DEFAULT_GAIN (eval/explorer_render_server.py:150), which
  // /info.film_default reports and M8's own CHAIN_DEFAULTS already uses (WINTERMUTE
  // 2026-09-25). 1.0 made every untouched lane disagree with the server. TARGET = onsets/s (X9).
  film: { ckpt: null, gain: 1.75, value: 4.0 },
  lora_on: false,
  lora: { ckpt_path: null, slot: null, strength: 1.0 },
  bungee_on: false,
  semitones: 0,
};

/** spec §4.6 — MASTER CHAIN: GAIN 0–120 default 64, LATENT NORMALISE on. */
export const MASTER_DEFAULT: MasterChain = {
  latch_on: false,
  head: "none",
  gain: 64,
  norm_on: true,
};

/** spec §4.5 — MIX ORDER default with every node at slerp t = 0.5. */
export const MIX_DEFAULT: MixSpec = {
  order: "tree",
  nodes: {
    M1: { interp: "slerp", t: 0.5 },
    M2: { interp: "slerp", t: 0.5 },
    MX: { interp: "slerp", t: 0.5 },
  },
  quad_weights: [1, 1, 1, 1],
};

/** spec §5.3 / X5 — SA3 is rectified-flow only; the k-diffusion list is dropped. */
export const SAMPLERS_BY_OBJECTIVE: Record<string, string[]> = {
  rectified_flow: ["euler", "rk4", "dpmpp", "pingpong"],
  rf_denoiser: ["pingpong", "euler"],
};

/** Deep copy — settings are per target, so nothing may share a schedule object. */
export function cloneRenderSettings(s: RenderSettings): RenderSettings {
  return {
    ...s,
    cfg_interval_progress: [s.cfg_interval_progress[0], s.cfg_interval_progress[1]],
    schedule: { ...s.schedule },
  };
}
