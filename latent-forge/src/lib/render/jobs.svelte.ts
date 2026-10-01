// The one place that knows a render is in flight (spec §7.1: "While any job runs, every render
// control is disabled; the control that started it reads SAMPLING · N steps left").
//
// At most ONE active job. A second click while one runs does not queue: §7.1, "A second click
// queues nothing; the queue exists for the Dash explorer and scripted use." `submit` therefore
// supersedes -- it aborts the in-flight poll and takes over -- and the superseded call resolves
// null without writing `active` or `history` again.
//
// #token is the superseding guard. `signal.aborted` is checked FIRST everywhere a listener could
// be added (HANDOUT: "An abort listener added after the signal already fired never runs"), and
// after every await the token is re-compared, because an abort only stops the POLLER -- it cannot
// stop a promise that is already resolving.

import { forgeApi, ForgeApiError } from "../forge/api";
import type { JobOp, JobRecord, Progress, RenderHistoryEntry } from "../forge/types";
import { logStore } from "../stores/log.svelte";
import { history } from "./history.svelte";

export type RenderKind = "gen" | "a2a" | "inpaint" | "mix";

export interface ActiveJob {
  forgeJobId: string;
  op: JobOp;
  kind: RenderKind;
  sourceClipId: string | null;
  targetKey: string;
  progress: Progress | null;
}

export interface SubmitRequest {
  op: JobOp;
  payload: unknown;
  kind: RenderKind;
  sourceClipId: string | null;
  targetKey: string;
}

const KIND_LABEL: Record<RenderKind, string> = { gen: "GEN", a2a: "A2A", inpaint: "INPAINT", mix: "MIX" };

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** `result.urls[0].split("/").pop()` -- the brief's Result→entry rule, and the shape M2 T15 /
 *  M8 T11 record. A result with no urls is a server bug, not a crash here. */
function fileOf(rec: JobRecord): string {
  const url = rec.result?.urls?.[0];
  return url ? (url.split("/").pop() ?? "") : "";
}

function durationOf(rec: JobRecord): number {
  const meta = (rec.result?.meta ?? {}) as Record<string, unknown>;
  const d = meta.duration_sec;
  return typeof d === "number" && Number.isFinite(d) ? d : 0;
}

export class JobsStore {
  /** At most one -- §7.1: every render control is disabled while a job runs. */
  active = $state<ActiveJob | null>(null);

  /** §9.7's inline error, keyed by the target that asked for the render. Cleared by the next one. */
  lastError = $state<{ targetKey: string; message: string } | null>(null);

  /** `/status.busy` with a job id that is not ours → "GPU busy — <job_id>". */
  gpuBusyOther = $state<string | null>(null);

  #token = 0;
  #abort: AbortController | null = null;
  #statusTimer: ReturnType<typeof setInterval> | null = null;

  get busy(): boolean {
    return this.active !== null || this.gpuBusyOther !== null;
  }

  /** May be 0: `steps_total` is 0 for a commit with no sampling passes, and for decode/bend
   *  (M8 plan_passes, `sum(...)` over an empty list). 0 is a real answer; null means "no progress
   *  yet". Never divide by either without a guard. */
  get stepsLeft(): number | null {
    return this.active?.progress?.steps_left_total ?? null;
  }

  async submit(req: SubmitRequest): Promise<RenderHistoryEntry | null> {
    const token = ++this.#token;
    this.#abort?.abort();
    const ac = new AbortController();
    this.#abort = ac;
    this.lastError = null;

    try {
      const { job_id } = await forgeApi.submitJob(req.op, req.payload);
      if (token !== this.#token) return null;
      this.active = {
        forgeJobId: job_id, op: req.op, kind: req.kind,
        sourceClipId: req.sourceClipId, targetKey: req.targetKey, progress: null,
      };
      const rec = await forgeApi.pollJob(job_id, (p) => {
        // A superseded poller must not keep writing `active` -- that is how the OLD job's step
        // count ends up under the NEW job's control.
        if (token !== this.#token || this.active === null) return;
        this.active.progress = p;
      }, ac.signal);
      if (token !== this.#token) return null;
      this.active = null;
      return history.add({
        job_id: rec.result?.job_id ?? rec.job_id,
        forge_job_id: rec.job_id,
        file: fileOf(rec),
        label: `${KIND_LABEL[req.kind]} ${new Date().toISOString().slice(11, 19)}`,
        kind: req.kind,
        dur_sec: durationOf(rec),
        source_clip_id: req.sourceClipId,
        created: Math.floor(Date.now() / 1000),       // epoch SECONDS, like the server's own fields
      });
    } catch (e) {
      if (token !== this.#token) return null;         // superseded: the new job owns the surfaces
      this.active = null;
      const text = message(e);
      this.lastError = { targetKey: req.targetKey, message: text };
      logStore.append(`[forge] ${req.op} failed: ${text}`, logStore.seq, "error");
      return null;
    } finally {
      if (token === this.#token) this.#abort = null;
    }
  }

  /**
   * Queued only. A RUNNING pass answers 409 `cannot cancel a running pass` (M2 plan:1829) -- that
   * is surfaced as a message, not thrown, and the job stays active because it really is still
   * running. NOTE (Fact 6): M1's mock also 409s a FINISHED job where the real server answers 200.
   * The code is written for the server; the mock's variant is covered in the recorded-contract file.
   */
  async cancel(): Promise<void> {
    const job = this.active;
    if (job === null) return;
    try {
      await forgeApi.cancelJob(job.forgeJobId);
      this.#token += 1;            // the poller's result is no longer wanted
      this.#abort?.abort();
      this.#abort = null;
      this.active = null;
    } catch (e) {
      this.lastError = { targetKey: job.targetKey, message: message(e) };
      if (!(e instanceof ForgeApiError) || e.status !== 409) throw e;
    }
  }

  /**
   * One `/status` read. M1 OQ 16 asked who owns `/status`: BOTH may call it and the answers are
   * independent (`logStore.busy` drives the TERMINAL dot, this drives render-control disabling), so
   * nothing is removed from the log store -- see open question A2. A dead render server is a normal
   * state on this box, so a failure clears the flag rather than surfacing anything.
   */
  async pollStatusOnce(): Promise<void> {
    try {
      const s = await forgeApi.status();
      const mine = this.active?.forgeJobId ?? null;
      this.gpuBusyOther = s.busy && s.job_id !== null && s.job_id !== mine ? s.job_id : null;
    } catch {
      this.gpuBusyOther = null;
    }
  }

  /** Started by App once; 1000 ms, the log store's own cadence, not pollJob's 500. */
  startStatusPolling(intervalMs = 1000): void {
    if (this.#statusTimer !== null) return;
    void this.pollStatusOnce();
    this.#statusTimer = setInterval(() => void this.pollStatusOnce(), intervalMs);
  }

  stopStatusPolling(): void {
    if (this.#statusTimer === null) return;
    clearInterval(this.#statusTimer);
    this.#statusTimer = null;
  }
}

export const jobs = new JobsStore();
