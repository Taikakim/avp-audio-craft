// Typed client for avp-audio-craft/eval/explorer_render_server.py.
//
// Every shape here was read from the server source on 2026-09-12, not
// inferred from a docstring or the design handoff (that was last session's
// load-bearing mistake -- see docs/sa3-studio/PLAN_CORRECTIONS.md §1). If the
// server changes, update this file and the line number below.
//
// Source: avp-audio-craft/eval/explorer_render_server.py (2292 lines, 27 routes).

export interface InfoResponse {
  ok: true;
  model: string;
  sample_rate: number;
  fps: number;
  max_duration_sec: number;
  out_dir: string;
  latch_heads: unknown[];
  dora: Record<string, unknown>;
  film_default: { ckpt: string | null; gain: number };
}

export interface StatusResponse {
  ok: true;
  busy: boolean;
  job_id: string | null;
  log_tail: string[];
}

export interface CkptEntry {
  path: string;
  name: string;
  mtime: number;
  size: number;
  kind: "ckpt" | "safetensors";
  root_id?: string;
  family?: string;
  label?: string;
  epoch?: number;
  step?: number;
  rank?: number;
  corpus?: string;
  verdict?: string;
}

export interface CkptsResponse {
  ok: boolean;
  root?: string;
  roots?: unknown;
  cached: boolean;
  scanned_at: number;
  count: number;
  ckpts: CkptEntry[];
  error?: string;
}

export interface PresetsResponse {
  ok: true;
  presets: string[];
}

// build_response() (explorer_render_server.py:682) -- the shape shared by
// EVERY job-based op (/generate, /a2a_track, /a2a_mix, /longform, /decode,
// /bend).
export interface JobResponse {
  status: "ok";
  job_id: string;
  files: string[];
  /** Non-empty when the op captured z0 (currently /generate) -- paths on the server, not URLs. */
  latents: string[];
  /** Ready-to-fetch playback URLs, one per output file, in the same order as `files`. */
  urls: string[];
  seed: number | null;
  timings: { total_sec: number; per_stage: Record<string, number> };
  warnings: string[];
  meta: Record<string, unknown>;
}

export interface ErrorResponse {
  error: string;
  traceback?: string;
}

export interface GenerateRequest {
  prompt: string;
  duration?: number; // 1..max_duration_sec, server default 47.0
  steps?: number; // default 24
  cfg_scale?: number; // default 6.0
  batch_size?: number; // default 1
  seed?: number; // -1 -> resolve_seed() picks one server-side
  negative_prompt?: string;
  sampler_type?: string;
  // dist_shift / cfg_interval / latch / film / dora / mutate all accepted but
  // left untyped here -- add fields as the studio grows features that need them.
  [extra: string]: unknown;
}

export interface DecodeRequest {
  /** Absolute path on the server, OR crop_id + latent_dir (defaults to the player's configured dir). */
  latent_path?: string;
  crop_id?: string;
  latent_dir?: string;
}

/**
 * POST /a2a_track. `audio_path` is resolved by require_path() ON THE SERVER --
 * there is no upload route, so the file must already exist on the server's
 * filesystem. `noise_levels` renders one output per level (a sweep); omit it
 * and `noise_level` is used for a single pass.
 */
export interface A2ATrackRequest {
  audio_path: string;
  prompt: string;
  noise_level?: number; // default 0.4
  noise_levels?: number[];
  steps?: number; // default 24
  cfg_scale?: number; // default 6.0
  apg_scale?: number; // default 1.0
  seed?: number;
  [extra: string]: unknown;
}

/** POST /a2a_mix -- the A→B transition, not an n-way mixdown (no such op exists). */
export interface A2AMixRequest {
  a_path: string;
  b_path: string;
  prompt_region: string;
  mode?: string; // default "sinesweep"
  seg_sec?: number; // default 75.0
  snap_to_downbeat?: boolean; // default true
  tempo_match?: boolean; // default true
  tempo_mode?: string; // default "ramp"
  fine_align?: boolean; // default true
  trans_start_sec?: number; // default 26.0
  trans_end_sec?: number; // default 49.0
  noise_level?: number; // default 0.42
  chroma_morph?: boolean; // default true
  interp?: "slerp" | "lerp";
  steps?: number;
  cfg_scale?: number;
  seed?: number;
  [extra: string]: unknown;
}

/** POST /longform -- `schedule` uses the arc grammar "0:promptA|45:promptB|...". */
export interface LongformRequest {
  schedule: string;
  duration?: number; // default 120.0
  steps?: number;
  cfg_scale?: number;
  seed?: number;
  audio_path?: string;
  init_latent_path?: string;
  window_sec?: number; // default 30.0
  overlap_sec?: number; // default 5.0  (must satisfy 0 < overlap < window)
  xfade_sec?: number; // default 4.0
  noise_level?: number; // default 0.4
  [extra: string]: unknown;
}

/** POST /bend -- op vocabulary from eval/latent_bend.py's apply_bends(). */
export interface BendRequest {
  ops: { op: string; amount?: number; [k: string]: unknown }[];
  latent_path?: string;
  crop_id?: string;
  latent_dir?: string;
  seed?: number;
}

const RENDER_BASE = ""; // vite dev proxy forwards these paths to the render server (see vite.config.ts)

/** Parse a response body as JSON, tolerating the non-JSON bodies a dead proxy
 * or a crashed dev server tends to produce (empty body, an HTML error page)
 * so callers see "render server unreachable" instead of a raw JSON parse error. */
async function parseBody(res: Response, path: string): Promise<unknown> {
  const text = await res.text();
  if (!text) throw new ApiError(res.status, { error: `render server unreachable (empty response from ${path})` });
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError(res.status, { error: `render server unreachable (non-JSON response from ${path})` });
  }
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(RENDER_BASE + path);
  const body = await parseBody(res, path);
  if (!res.ok) throw new ApiError(res.status, body as ErrorResponse);
  return body as T;
}

async function postJSON<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(RENDER_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const body = await parseBody(res, path);
  if (!res.ok) throw new ApiError(res.status, body as ErrorResponse);
  return body as T;
}

export class ApiError extends Error {
  status: number;
  body: ErrorResponse;
  constructor(status: number, body: ErrorResponse) {
    super(body?.error || `request failed (${status})`);
    this.status = status;
    this.body = body;
  }
}

export const api = {
  info: () => getJSON<InfoResponse>("/info"),
  status: () => getJSON<StatusResponse>("/status"),
  ckpts: (opts?: { rescan?: boolean; root?: string; rootIds?: string[] }) => {
    const p = new URLSearchParams();
    if (opts?.rescan) p.set("rescan", "1");
    if (opts?.root) p.set("root", opts.root);
    if (opts?.rootIds?.length) p.set("root_ids", opts.rootIds.join(","));
    const qs = p.toString();
    return getJSON<CkptsResponse>(`/ckpts${qs ? `?${qs}` : ""}`);
  },
  presets: () => getJSON<PresetsResponse>("/presets"),
  presetGet: (name: string) => getJSON<Record<string, unknown>>(`/presets/${encodeURIComponent(name)}`),

  /** RENDER: commit a text-to-audio generation. Real latent op, runs server-side. */
  generate: (req: GenerateRequest) => postJSON<JobResponse>("/generate", req),
  /** RENDER: decode an existing latent (crop_id or latent_path) to audio. */
  decodeJob: (req: DecodeRequest) => postJSON<JobResponse>("/decode", req),
  /** RENDER: audio-to-audio pass over a file the SERVER can see. */
  a2aTrack: (req: A2ATrackRequest) => postJSON<JobResponse>("/a2a_track", req),
  /** RENDER: the A→B transition between two server-side files. */
  a2aMix: (req: A2AMixRequest) => postJSON<JobResponse>("/a2a_mix", req),
  /** RENDER: longform generation over a prompt arc. */
  longform: (req: LongformRequest) => postJSON<JobResponse>("/longform", req),
  /** RENDER: latent data-bending, then decode. */
  bend: (req: BendRequest) => postJSON<JobResponse>("/bend", req),

  /** The sigma schedule the real run would use -- same build_schedule() the sampler calls. */
  schedule: (params: Record<string, string | number>) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) p.set(k, String(v));
    return getJSON<Record<string, unknown>>(`/schedule?${p.toString()}`);
  },
  roots: () => getJSON<Record<string, unknown>>("/roots"),

  /** Ready-to-play URL for a job's output file (GET /audio/{job_id}/{filename}). */
  audioUrl: (jobId: string, filename: string) => `${RENDER_BASE}/audio/${jobId}/${filename}`,

  // --- "player" surface: fast GET-based previews over pre-extracted crops.
  // Distinct from the job-based ops above -- these return raw WAV bytes
  // directly (see explorer_render_server.py:2143 _player_run), no job_id, no
  // polling. This is the natural source for cheap audio-domain preview of a
  // latent-backed clip before a RENDER commits it.
  crops: () => getJSON<string[]>("/crops"),
  cropMeta: (cropId: string) =>
    getJSON<{ source_path: string; start_sample: number; end_sample: number; padding_mask?: number[] }>(
      `/meta?crop_id=${encodeURIComponent(cropId)}`,
    ),
  playerStatus: () => getJSON<{ ok: true; model: string | null; sample_rate: number; latent_dir: string; heads: string[] }>(
    "/player_status",
  ),
  /** WAV bytes decoded fresh from the crop's latent -- NOT cached, hits the GPU_LOCK. */
  decodePreviewUrl: (cropId: string) => `${RENDER_BASE}/decode?crop_id=${encodeURIComponent(cropId)}`,
  /** WAV bytes of the original source audio window the crop was encoded from. */
  sourcePreviewUrl: (cropId: string) => `${RENDER_BASE}/source?crop_id=${encodeURIComponent(cropId)}`,
  /** Latent-space crossfade preview between two crops (per-frame slerp or lerp). */
  mixPreviewUrl: (cropAId: string, cropBId: string, t: number, interp: "slerp" | "lerp" = "slerp") =>
    `${RENDER_BASE}/mix?crop_a=${encodeURIComponent(cropAId)}&crop_b=${encodeURIComponent(cropBId)}&t=${t}&interp=${interp}`,
  /** LatCH-steered preview: gradient-ascend a control head's mean activation, decode. */
  steerPreviewUrl: (cropId: string, head: string, gain = 48.0) =>
    `${RENDER_BASE}/steer?crop_id=${encodeURIComponent(cropId)}&head=${encodeURIComponent(head)}&gain=${gain}`,
};
