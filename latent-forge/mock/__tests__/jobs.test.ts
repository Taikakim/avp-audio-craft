import { beforeEach, describe, expect, it } from "vitest";
import {
  COMMIT_STAGES, MAX_ACTIVE_JOBS, MockJobQueue, serverJobId, stamp,
} from "../jobs";

/** A frozen clock: the mock's ids and timestamps must be reproducible. */
function clockAt(epochSec: number) {
  let t = epochSec;
  return { now: () => t, advance: (dt: number) => (t += dt) };
}

function queueAt(epochSec = 1789560000) {
  const clock = clockAt(epochSec);
  return {
    clock,
    q: new MockJobQueue({ queuedPolls: 1, stepsTotal: 24, stepsPerPoll: 8, now: clock.now }),
  };
}

describe("job ids", () => {
  it("stamps the injected clock and counts up", () => {
    const { q } = queueAt(1789560000); // 2026-09-16T12:00:00Z
    const a = q.submit("generate", {});
    const b = q.submit("commit", {});
    expect(a.body).toMatchObject({ ok: true, job_id: "forge-20260916-120000-1", position: 0 });
    expect(b.body).toMatchObject({ ok: true, job_id: "forge-20260916-120000-2", position: 1 });
  });

  it("formats the stamp as yyyymmdd-HHMMSS in UTC", () => {
    expect(stamp(1789560000)).toBe("20260916-120000");
    expect(stamp(0)).toBe("19700101-000000");
  });

  it("derives the server output-dir id from the forge job id (spec §6.2)", () => {
    expect(serverJobId("forge-20260916-120000-7")).toBe("20260916-120000");
  });
});

describe("submission", () => {
  it("answers 202 with the queue position", () => {
    const { q } = queueAt();
    const r = q.submit("generate", { prompt: "dub" });
    expect(r.status).toBe(202);
  });

  it("refuses a fifth queued-or-running job with 409 job queue full (spec §6.2)", () => {
    const { q } = queueAt();
    for (let i = 0; i < MAX_ACTIVE_JOBS; i++) q.submit("generate", {});
    const overflow = q.submit("generate", {});
    expect(overflow.status).toBe(409);
    expect(overflow.body).toEqual({ ok: false, error: "job queue full" });
  });
});

describe("lifecycle, one tick per poll", () => {
  let q: MockJobQueue;
  let jobId: string;

  beforeEach(() => {
    const made = queueAt();
    q = made.q;
    jobId = (made.q.submit("generate", { prompt: "dub" }).body as { job_id: string }).job_id;
  });

  it("walks queued -> running -> done", () => {
    const seen: string[] = [];
    for (let i = 0; i < 4; i++) seen.push((q.get(jobId).body as { state: string }).state);
    expect(seen).toEqual(["queued", "running", "running", "done"]);
  });

  it("decreases steps_left_total and never reports it below zero", () => {
    q.get(jobId); // queued
    const left: number[] = [];
    for (let i = 0; i < 2; i++) {
      const p = (q.get(jobId).body as { progress: { steps_left_total: number; steps_total: number } }).progress;
      left.push(p.steps_left_total);
      expect(p.steps_total).toBe(24);
    }
    expect(left).toEqual([16, 8]);
    const done = q.get(jobId).body as { state: string; progress: null };
    expect(done.state).toBe("done");
    expect(done.progress).toBe(null);
  });

  it("returns a JobResponse with /SERVER paths, /audio urls and the server's own job id", () => {
    for (let i = 0; i < 3; i++) q.get(jobId);
    const rec = q.get(jobId).body as { state: string; result: { job_id: string; files: string[]; urls: string[]; seed: number } };
    expect(rec.state).toBe("done");
    expect(rec.result.job_id).toBe("20260916-120000");
    expect(rec.result.files).toEqual(["/SERVER/out/20260916-120000/out_00.wav"]);
    expect(rec.result.urls).toEqual(["/audio/20260916-120000/out_00.wav"]);
    expect(rec.result.seed).toBe(424242);
  });

  it("reports the nine commit stages of spec §8.1, 1-based", () => {
    const { q: q2 } = queueAt();
    const id = (q2.submit("commit", {}).body as { job_id: string }).job_id;
    expect(COMMIT_STAGES).toHaveLength(9);
    q2.get(id); // queued
    const first = (q2.get(id).body as { progress: { stage: string; stage_index: number; stage_count: number } }).progress;
    expect(first.stage_count).toBe(9);
    // slot 3 of the array, reported as stage_index 4 — 1-based, 0 = not started.
    expect(first.stage_index).toBe(4);
    expect(first.stage).toBe(COMMIT_STAGES[3]);
    expect(COMMIT_STAGES[0]).toBe("DECODE latent → audio");
    expect(COMMIT_STAGES[2]).toBe("ENCODE audio → latent");
  });

  it("gives a wrapped op no stage vocabulary at all (steps only)", () => {
    const { q: q3 } = queueAt();
    const id = (q3.submit("generate", {}).body as { job_id: string }).job_id;
    q3.get(id); // queued
    const p = (q3.get(id).body as { progress: { stage: string; stage_index: number; stage_count: number; steps: number } }).progress;
    expect(p.stage).toBe("");
    expect(p.stage_index).toBe(0);
    expect(p.stage_count).toBe(0);
    expect(p.steps).toBeGreaterThan(0);
  });
});

describe("cancel and lookup", () => {
  it("cancels a queued job and refuses to cancel a running one (spec §6.2)", () => {
    const { q } = queueAt();
    const id = (q.submit("generate", {}).body as { job_id: string }).job_id;
    q.get(id); // queued
    q.get(id); // running
    const running = q.cancel(id);
    expect(running.status).toBe(409);
    expect(running.body).toEqual({ ok: false, error: "cannot cancel a running pass" });

    const id2 = (q.submit("generate", {}).body as { job_id: string }).job_id;
    const queued = q.cancel(id2);
    expect(queued.status).toBe(200);
    expect(queued.body).toEqual({ ok: true, state: "cancelled" });
    expect((q.get(id2).body as { state: string }).state).toBe("cancelled");
  });

  it("404s an unknown job id", () => {
    const { q } = queueAt();
    const r = q.get("forge-nope-1");
    expect(r.status).toBe(404);
    expect(r.body).toEqual({ ok: false, error: "no such job: forge-nope-1" });
  });

  it("lists jobs newest first and honours limit", () => {
    const { q } = queueAt();
    for (let i = 0; i < 3; i++) q.submit("generate", { i });
    const body = q.list(2).body as { ok: true; jobs: { job_id: string }[] };
    expect(body.jobs.map((j) => j.job_id)).toEqual([
      "forge-20260916-120000-3",
      "forge-20260916-120000-2",
    ]);
  });
});
