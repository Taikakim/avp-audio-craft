// Client for the frozen contract, spec §6. Route paths and field names are the
// spec's; nothing here invents a shape. The dev proxy (vite.config.ts) and the
// production serve module (M11) both forward these prefixes to the render
// server, so every path is site-relative.

import type {
  AudioRef, JobOp, JobRecord, LatentRef, Progress, ProjectV2, ScheduleSpec,
} from "./types";

export class ForgeApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ForgeApiError";
    this.status = status;
  }
}

/** Parse tolerantly: a dead proxy answers with HTML or nothing, and a raw JSON
 *  parse error is useless to the operator. */
async function parseBody(res: Response, path: string): Promise<unknown> {
  const text = await res.text();
  if (!text) throw new ForgeApiError(res.status, `render server unreachable (empty response from ${path})`);
  try {
    return JSON.parse(text);
  } catch {
    throw new ForgeApiError(res.status, `render server unreachable (non-JSON response from ${path})`);
  }
}

/** Returns the body as the server sent it. It never unwraps an envelope and never REQUIRES `ok`:
 *  GET /forge/sessions/{name} and GET /forge/presets/{level}/{name} return the stored object raw,
 *  with no {ok, ...} wrapper, while the list routes and PUT/DELETE do wrap (WINTERMUTE 2026-09-25).
 *  Only an explicit `ok: false` or a non-2xx status is an error. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const body = (await parseBody(res, path)) as { ok?: boolean; error?: string };
  if (!res.ok || body?.ok === false) {
    throw new ForgeApiError(res.status, body?.error ?? `request failed (${res.status})`);
  }
  return body as T;
}

function getJSON<T>(path: string): Promise<T> {
  return request<T>(path);
}

function sendJSON<T>(path: string, method: "POST" | "PUT" | "DELETE", payload?: unknown,
                     signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
    signal,
  });
}

function qs(params: Record<string, string | number | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

const POLL_MS = 500;   // spec §9.5

export const forgeApi = {
  // ------------------------------------------------------------ status, log
  info: () => getJSON<Record<string, unknown>>("/info"),
  status: () => getJSON<{ ok: true; busy: boolean; job_id: string | null; log_tail: string[]; progress: Progress | null }>("/status"),
  log: (since = 0) => getJSON<{ ok: true; seq: number; lines: { seq: number; text: string }[] }>(`/forge/log${qs({ since })}`),

  // ------------------------------------------------------------ backbone
  backbone: () => getJSON<{ ok: true; active: string; objective: string; available: { id: string; objective: string; cached: boolean }[] }>("/forge/backbone"),
  setBackbone: (id: string) => sendJSON<{ ok: true; active: string; objective: string; rebuild_sec: number; warnings: string[] }>("/forge/backbone", "POST", { id }),

  // ------------------------------------------------------------ library
  files: (o: { root?: string; q?: string; limit?: number } = {}) =>
    getJSON<{ ok: true; roots: { id: string; label: string; available: boolean }[]; files: { root: string; rel: string; kind: "audio" | "latent"; size: number; mtime: number; ref: AudioRef | LatentRef }[] }>(
      `/forge/files${qs({ root: o.root, q: o.q, limit: o.limit })}`,
    ),
  /** The browser previews any ref through this URL (spec §6.3). */
  audioUrl: (ref: AudioRef) => `/forge/audio?ref=${encodeURIComponent(JSON.stringify(ref))}`,
  upload: async (file: File) => {
    const res = await fetch(`/forge/upload${qs({ filename: file.name })}`, { method: "PUT", body: file });
    const body = (await parseBody(res, "/forge/upload")) as { ok?: boolean; error?: string };
    if (!res.ok || body?.ok === false) throw new ForgeApiError(res.status, body?.error ?? "upload failed");
    return body as unknown as { ok: true; ref: AudioRef; path: string; bytes: number; duration_sec: number; sample_rate: number; channels: number };
  },

  // ------------------------------------------------------------ analysis
  analyze: (audio: AudioRef) =>
    sendJSON<{ ok: true; bpm: number; bpm_candidates: number[]; beats_sec: number[]; downbeats_sec: number[]; duration_sec: number; source: "sidecar" | "librosa" }>("/forge/analyze", "POST", { audio }),
  stretch: (audio: AudioRef, speed: number, semitones: number) =>
    sendJSON<{ ok: true; ref: AudioRef; duration_sec: number }>("/forge/stretch", "POST", { audio, speed, semitones }),
  chroma: (audio: AudioRef) =>
    sendJSON<{ ok: true; frames: number; fps: number; bands: { shape: [number, number, number]; scale: [number, number, number]; data_b64: string }; fold12: { shape: [number, number]; scale: number; data_b64: string } }>("/forge/chroma", "POST", { audio }),
  stats: (latents: LatentRef[], features: string[], max_frames = 20000, max_points = 2000) =>
    sendJSON<{ ok: true; n_frames: number; xcorr: { shape: [number, number]; data_b64: string }; timeseries: { index: number; feature: string; fps: number; values: (number | null)[] }[]; features_available: string[] }>("/forge/stats", "POST", { latents, features, max_frames, max_points }),
  datasetScalars: (x: string, y: string) =>
    getJSON<{ ok: true; fields: string[]; points: { crop_id: string; x: number; y: number; label: string }[] }>(`/forge/dataset_scalars${qs({ x, y })}`),

  // ------------------------------------------------------------ sessions, presets
  // `updated` is the file mtime in epoch SECONDS (a float), not ms and not ISO -- format it with
  // `new Date(updated * 1000)` wherever it is shown (WINTERMUTE 2026-09-25).
  sessions: () => getJSON<{ ok: true; sessions: { name: string; updated: number; n_clips: number }[] }>("/forge/sessions"),
  // Raw: the stored ProjectV2 itself, no {ok} wrapper (see request()).
  session: (name: string) => getJSON<ProjectV2>(`/forge/sessions/${encodeURIComponent(name)}`),
  saveSession: (name: string, project: ProjectV2) => sendJSON<{ ok: true }>(`/forge/sessions/${encodeURIComponent(name)}`, "PUT", project),
  presets: (level: string) => getJSON<{ ok: true; names: string[] }>(`/forge/presets/${encodeURIComponent(level)}`),
  // Raw: the stored payload itself, no {ok} wrapper (see request()).
  preset: (level: string, name: string) => getJSON<Record<string, unknown>>(`/forge/presets/${encodeURIComponent(level)}/${encodeURIComponent(name)}`),
  savePreset: (level: string, name: string, payload: unknown) => sendJSON<{ ok: true }>(`/forge/presets/${encodeURIComponent(level)}/${encodeURIComponent(name)}`, "PUT", payload),
  deletePreset: (level: string, name: string) => sendJSON<{ ok: true }>(`/forge/presets/${encodeURIComponent(level)}/${encodeURIComponent(name)}`, "DELETE"),

  // ------------------------------------------------------------ schedule
  /**
   * The sigma curve the graph draws. The canvas never computes sigma itself (spec §5.3).
   *
   * `duration` is REQUIRED even though the route defaults it: the model shape's dist
   * shift is length-dependent (`latent_len = ceil(duration*SR/DS)`), so omitting it
   * silently charts the server's 47 s default instead of the pass being configured.
   * `signal` exists because the pane debounces and a superseded request must be
   * cancellable. The fields are the route's own, verbatim (M3 Task 2 edit (j)).
   */
  schedule: (
    body: { steps: number; duration: number; sigma_max?: number;
            sampler_type?: string | null; schedule: ScheduleSpec },
    signal?: AbortSignal,
  ) =>
    sendJSON<{
      ok: true; steps: number; duration: number; sigma_max: number;
      dist_shift: number | string | null; shape: string; latent_len: number;
      sigmas: number[]; warnings: string[];
    }>("/schedule", "POST", body, signal),

  // ------------------------------------------------------------ jobs
  submitJob: (op: JobOp, payload: unknown) =>
    sendJSON<{ ok: true; job_id: string; position: number }>("/forge/jobs", "POST", { op, payload }),
  job: (jobId: string) => getJSON<JobRecord>(`/forge/jobs/${encodeURIComponent(jobId)}`),
  jobs: (limit = 50) => getJSON<{ ok: true; jobs: JobRecord[] }>(`/forge/jobs${qs({ limit })}`),
  cancelJob: (jobId: string) => sendJSON<{ ok: true; state: string }>(`/forge/jobs/${encodeURIComponent(jobId)}`, "DELETE"),

  /**
   * Poll a job to completion, reporting each progress tick. 500 ms while
   * running (spec §9.5 — the same cadence that drives the raster border).
   * Rejects on `error` state, on abort, and on transport failure.
   */
  async pollJob(jobId: string, onProgress: (p: Progress) => void, signal?: AbortSignal): Promise<JobRecord> {
    for (;;) {
      if (signal?.aborted) throw new ForgeApiError(0, `polling aborted for ${jobId}`);
      const rec = await forgeApi.job(jobId);
      if (rec.progress) onProgress(rec.progress);
      if (rec.state === "done") return rec;
      if (rec.state === "error") throw new ForgeApiError(500, rec.error ?? `job ${jobId} failed`);
      if (rec.state === "cancelled") throw new ForgeApiError(0, `job ${jobId} was cancelled`);
      await new Promise<void>((resolve, reject) => {
        // Check FIRST: if the signal already fired, an "abort" listener added
        // now would never run and this promise would never settle. Verified —
        // without this line the abort test hangs instead of rejecting.
        if (signal?.aborted) { reject(new ForgeApiError(0, `polling aborted for ${jobId}`)); return; }
        const t = setTimeout(resolve, POLL_MS);
        signal?.addEventListener("abort", () => { clearTimeout(t); reject(new ForgeApiError(0, `polling aborted for ${jobId}`)); }, { once: true });
      });
    }
  },
};
