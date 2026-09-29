// A pure, timer-free model of the server's job queue (spec §6.2). The lifecycle
// advances exactly one tick per get(), so the whole thing is deterministic under
// vitest and behaves correctly in the browser too: forgeApi.pollJob() polls every
// 500 ms, and each poll moves the job on by one step.
//
// Everything here returns {status, body} -- exactly what the plugin writes to the
// response -- so the middleware stays a thin adapter with no logic of its own.

import type { JobOp, JobRecord, JobResponse, Progress } from "../src/lib/forge/types";

/** spec §6.2 -- at most 4 queued-or-running jobs, otherwise 409 `job queue full`. */
export const MAX_ACTIVE_JOBS = 4;

/** spec §8.1 -- the nine commit stages; these labels are also the signal path. */
export const COMMIT_STAGES: string[] = [
  "DECODE latent → audio",
  "BUNGEE stretch / pitch",
  "ENCODE audio → latent",
  "LANE CHAINS",
  "A2A RE-NOISE",
  "INPAINT OVERLAPS",
  "MIX",
  "MASTER CHAIN",
  "DECODE latent → audio",
];

/**
 * Stage labels per op. Only `commit` is fixed by the spec (§8.1); the rest are the
 * mock's own minimal lists so the progress line has something honest to show. When
 * M2 records real job fixtures, the recorded labels win (see Open questions).
 */
// CORRECTED (WINTERMUTE, 2026-09-16): only `commit` has a stage vocabulary. M2's
// `_existing_runner` calls `progress.begin(job_id, op, steps * passes)` with NO labels, so every
// other op — the six wrapped ones AND `a2a_clip` / `inpaint` — emits `stage_count: 0` and
// `stage: ""`, steps only. The mock must not invent labels the server will never send.
export const STAGES_BY_OP: Record<JobOp, string[]> = {
  generate: [],
  a2a_track: [],
  a2a_mix: [],
  longform: [],
  decode: [],
  bend: [],
  a2a_clip: [],
  inpaint: [],
  commit: COMMIT_STAGES,
};

export interface MockJobConfig {
  /** polls the job spends in `queued` before it starts running */
  queuedPolls: number;
  /** the job's `steps_total` */
  stepsTotal: number;
  /** how much `steps_left_total` drops per running poll */
  stepsPerPoll: number;
  /** epoch seconds; injected so ids and timestamps are reproducible in tests */
  now: () => number;
}

export const MOCK_JOB_CONFIG: MockJobConfig = {
  queuedPolls: 1,
  stepsTotal: 24,
  stepsPerPoll: 8,
  now: () => Math.floor(Date.now() / 1000),
};

export interface MockResult<T = unknown> {
  status: number;
  body: T;
}
export type SubmitResult = MockResult<{ ok: true; job_id: string; position: number } | { ok: false; error: string }>;
export type GetResult = MockResult<JobRecord | { ok: false; error: string }>;
export type CancelResult = MockResult<{ ok: true; state: string } | { ok: false; error: string }>;
export type ListResult = MockResult<{ ok: true; jobs: JobRecord[] }>;

/** `yyyymmdd-HHMMSS` in UTC, the forge counter's stamp (spec §6.2). */
export function stamp(epochSec: number): string {
  const d = new Date(epochSec * 1000);
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return (
    `${p(d.getUTCFullYear(), 4)}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}` +
    `-${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}`
  );
}

/**
 * spec §6.2: `result.job_id` is the SERVER's own output-dir id, used in
 * `/audio/{job_id}/{file}` -- not the forge job id. Strip the prefix and counter.
 */
export function serverJobId(forgeJobId: string): string {
  return forgeJobId.replace(/^forge-/, "").replace(/-\d+$/, "");
}

function progressOf(rec: JobRecord, done: number, left: number, total: number): Progress {
  const stages = STAGES_BY_OP[rec.op];
  // stage_index is 1-BASED and 0 means "not started" (WINTERMUTE, 2026-09-16: M2's
  // `progress.begin()` leaves it 0 and each stage entry calls `progress.stage(i + 1, label)`).
  // An op with no stage vocabulary — everything except `commit` — reports stage "" and
  // stage_count 0, steps only. Do NOT invent labels the server will never send.
  // Multiply before dividing: (done/total)*stages is a knife-edge for floor() -- 8/24*9 comes out
  // 2.9999999999999996 and lands on the wrong stage, while (8*9)/24 is exactly 3.
  const slot = stages.length
    ? Math.min(stages.length - 1, Math.floor((done * stages.length) / (total || 1)))
    : -1;
  return {
    job_id: rec.job_id,
    op: rec.op,
    stage: slot >= 0 ? stages[slot] : "",
    stage_index: slot >= 0 ? slot + 1 : 0,
    stage_count: stages.length,
    step: done,
    steps: total,
    steps_left_total: left,
    steps_total: total,
  };
}

function resultOf(rec: JobRecord): JobResponse {
  const outId = serverJobId(rec.job_id);
  const file = rec.op === "commit" ? "mix.wav" : "out_00.wav";
  const latent = rec.op === "commit" ? "mix.z0.npy" : "out_00.z0.npy";
  return {
    status: "ok",
    job_id: outId,
    files: [`/SERVER/out/${outId}/${file}`],
    latents: [`/SERVER/out/${outId}/${latent}`],
    urls: [`/audio/${outId}/${file}`],
    seed: 424242,
    timings: { total_sec: 12.5, per_stage: { sample: 11.2, decode: 1.3 } },
    warnings: [],
    meta: { mock: true, backbone: "medium-base", objective: "rectified_flow", resolved_seeds: { session: 424242 } },
  };
}

export class MockJobQueue {
  private readonly cfg: MockJobConfig;
  private readonly jobs: JobRecord[] = [];
  private readonly polls = new Map<string, number>();
  private seq = 0;

  constructor(cfg: Partial<MockJobConfig> = {}) {
    this.cfg = { ...MOCK_JOB_CONFIG, ...cfg };
  }

  /** `/status.busy` (spec §6.4) -- true while any job is running. */
  get busy(): boolean {
    return this.jobs.some((j) => j.state === "running");
  }

  submit(op: JobOp, payload: unknown): SubmitResult {
    const active = this.jobs.filter((j) => j.state === "queued" || j.state === "running");
    if (active.length >= MAX_ACTIVE_JOBS) {
      return { status: 409, body: { ok: false, error: "job queue full" } };
    }
    this.seq += 1;
    const created = this.cfg.now();
    const job_id = `forge-${stamp(created)}-${this.seq}`;
    const position = active.length;
    this.jobs.push({
      ok: true, job_id, op, payload, state: "queued", position,
      progress: null, result: null, error: null, created, started: null, finished: null,
    });
    this.polls.set(job_id, 0);
    return { status: 202, body: { ok: true, job_id, position } };
  }

  get(jobId: string): GetResult {
    const rec = this.jobs.find((j) => j.job_id === jobId);
    if (!rec) return { status: 404, body: { ok: false, error: `no such job: ${jobId}` } };
    this.advance(rec);
    return { status: 200, body: rec };
  }

  list(limit = 50): ListResult {
    return { status: 200, body: { ok: true, jobs: this.jobs.slice().reverse().slice(0, Math.max(0, limit)) } };
  }

  cancel(jobId: string): CancelResult {
    const rec = this.jobs.find((j) => j.job_id === jobId);
    if (!rec) return { status: 404, body: { ok: false, error: `no such job: ${jobId}` } };
    if (rec.state === "running") {
      return { status: 409, body: { ok: false, error: "cannot cancel a running pass" } };
    }
    if (rec.state !== "queued") {
      return { status: 409, body: { ok: false, error: `job ${jobId} is already ${rec.state}` } };
    }
    rec.state = "cancelled";
    rec.position = null;
    rec.finished = this.cfg.now();
    return { status: 200, body: { ok: true, state: "cancelled" } };
  }

  /** One tick. Terminal states never move again. */
  private advance(rec: JobRecord): void {
    if (rec.state !== "queued" && rec.state !== "running") return;
    const n = (this.polls.get(rec.job_id) ?? 0) + 1;
    this.polls.set(rec.job_id, n);

    const { queuedPolls, stepsTotal, stepsPerPoll } = this.cfg;
    if (n <= queuedPolls) {
      rec.state = "queued";
      rec.progress = null;
      return;
    }
    const runPoll = n - queuedPolls;                               // 1-based
    const done = Math.min(stepsTotal, runPoll * stepsPerPoll);
    const left = Math.max(0, stepsTotal - done);
    if (rec.started === null) {
      rec.started = this.cfg.now();
      rec.position = null;
    }
    rec.state = "running";
    rec.progress = progressOf(rec, done, left, stepsTotal);
    if (left === 0) {
      rec.state = "done";
      rec.progress = null;
      rec.result = resultOf(rec);
      rec.finished = this.cfg.now();
    }
  }
}
