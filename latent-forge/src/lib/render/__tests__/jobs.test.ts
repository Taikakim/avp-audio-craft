import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError, forgeApi } from "../../forge/api";
import type { JobRecord, Progress, RenderHistoryEntry } from "../../forge/types";
import { logStore } from "../../stores/log.svelte";
import { history } from "../history.svelte";
import { jobs } from "../jobs.svelte";

function progress(patch: Partial<Progress> = {}): Progress {
  return {
    job_id: "forge-1", op: "commit", stage: "", stage_index: 0, stage_count: 0,
    step: 0, steps: 0, steps_left_total: 12, steps_total: 24, ...patch,
  };
}

function done(patch: Partial<JobRecord> = {}): JobRecord {
  return {
    ok: true, job_id: "forge-1", op: "generate", payload: {}, state: "done", position: null,
    progress: null, error: null, created: 1_700_000_000, started: 1_700_000_001,
    finished: 1_700_000_040,
    result: {
      status: "ok", job_id: "gen-20260926-1", files: ["/SERVER/out/gen-1/out_00.wav"],
      latents: [], urls: ["/audio/gen-20260926-1/out_00.wav"], seed: 7,
      timings: { total_sec: 39, per_stage: {} }, warnings: [], meta: { duration_sec: 45 },
    },
    ...patch,
  };
}

const SUBMIT = { op: "generate" as const, payload: { prompt: "dub" }, kind: "gen" as const, sourceClipId: null, targetKey: "session" };

beforeEach(() => {
  jobs.active = null;
  jobs.lastError = null;
  jobs.gpuBusyOther = null;
  history.clear();
  logStore.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("submit", () => {
  it("holds one ActiveJob while it runs and clears it when the job finishes", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    let seen: unknown = "not started";
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async () => {
      seen = jobs.active && { ...jobs.active };
      return done();
    });
    await jobs.submit(SUBMIT);
    expect(seen).toMatchObject({ forgeJobId: "forge-1", op: "generate", kind: "gen", targetKey: "session" });
    expect(jobs.active).toBeNull();
  });

  it("busy is true for the whole round trip and false again afterwards", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    const busyDuring: boolean[] = [];
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async () => { busyDuring.push(jobs.busy); return done(); });
    expect(jobs.busy).toBe(false);
    await jobs.submit(SUBMIT);
    expect(busyDuring).toEqual([true]);
    expect(jobs.busy).toBe(false);
  });

  it("busy is also true when the GPU is held by a job this client did not start", () => {
    expect(jobs.busy).toBe(false);
    jobs.gpuBusyOther = "dash-77";
    expect(jobs.busy).toBe(true);
  });

  it("stepsLeft tracks progress.steps_left_total and is null with no progress", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    const seen: (number | null)[] = [];
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async (_id, onProgress) => {
      seen.push(jobs.stepsLeft);
      onProgress(progress({ steps_left_total: 12 }));
      seen.push(jobs.stepsLeft);
      onProgress(progress({ steps_left_total: 3 }));
      seen.push(jobs.stepsLeft);
      return done();
    });
    await jobs.submit(SUBMIT);
    expect(seen).toEqual([null, 12, 3]);
    expect(jobs.stepsLeft).toBeNull();
  });

  it("survives steps_total 0 -- a commit with no sampling passes, decode, bend (Fact 5)", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async (_id, onProgress) => {
      onProgress(progress({ steps_total: 0, steps_left_total: 0 }));
      expect(jobs.stepsLeft).toBe(0);
      expect(Number.isFinite(jobs.active?.progress?.steps_total ?? NaN)).toBe(true);
      return done();
    });
    await expect(jobs.submit(SUBMIT)).resolves.not.toBeNull();
  });

  it("builds the history entry from the result: job_id, the basename of urls[0], the kind", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(done());
    const entry = (await jobs.submit(SUBMIT)) as RenderHistoryEntry;
    expect(entry).toMatchObject({
      job_id: "gen-20260926-1", forge_job_id: "forge-1", file: "out_00.wav",
      kind: "gen", source_clip_id: null,
    });
    expect(entry.created).toBeGreaterThan(1_600_000_000);
    expect(history.renders).toHaveLength(1);
  });

  it("returns the store's live entry, not the object it built ($state proxy rule)", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(done());
    const entry = await jobs.submit(SUBMIT);
    expect(entry).toBe(history.renders[history.renders.length - 1]);
  });

  it("clears the previous inline error when a new render starts (§9.7)", async () => {
    jobs.lastError = { targetKey: "session", message: "old" };
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(done());
    await jobs.submit(SUBMIT);
    expect(jobs.lastError).toBeNull();
  });

  it("surfaces a 400 as lastError on the target that asked, logs it red, and resolves null", async () => {
    vi.spyOn(forgeApi, "submitJob").mockRejectedValue(new ForgeApiError(400, "unknown render field(s): duration_sec"));
    await expect(jobs.submit({ ...SUBMIT, targetKey: "clip:c1" })).resolves.toBeNull();
    expect(jobs.lastError).toEqual({ targetKey: "clip:c1", message: "unknown render field(s): duration_sec" });
    expect(jobs.active).toBeNull();
    expect(logStore.lines.at(-1)).toMatchObject({ tone: "error" });
    expect(logStore.lines.at(-1)?.text).toContain("duration_sec");
  });

  it("surfaces a 409 queue-full as a message rather than throwing", async () => {
    vi.spyOn(forgeApi, "submitJob").mockRejectedValue(new ForgeApiError(409, "job queue full"));
    await expect(jobs.submit(SUBMIT)).resolves.toBeNull();
    expect(jobs.lastError?.message).toContain("job queue full");
  });

  it("surfaces a mid-poll server error and leaves no active job behind", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockRejectedValue(new ForgeApiError(500, "non-finite latents in lane 2"));
    await expect(jobs.submit(SUBMIT)).resolves.toBeNull();
    expect(jobs.lastError?.message).toContain("non-finite latents");
    expect(jobs.active).toBeNull();
    expect(history.renders).toHaveLength(0);
  });

  it("a superseded job never writes active again, and never adds a second history entry", async () => {
    // Abort ordering, HANDOUT: "An abort listener added after the signal already fired never runs."
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    let release: (r: JobRecord) => void = () => {};
    vi.spyOn(forgeApi, "pollJob")
      .mockImplementationOnce(() => new Promise<JobRecord>((res) => { release = res; }))
      .mockImplementationOnce(async () => done({ job_id: "forge-2" }));
    const first = jobs.submit(SUBMIT);
    // `submit` suspends at `await forgeApi.submitJob(...)`, so the first call has not reached
    // `pollJob` yet -- start the second only once it has, or the second consumes the first mock
    // (the never-resolving one) and `await second` hangs.
    await vi.waitFor(() => expect(jobs.active?.forgeJobId).toBe("forge-1"));
    const second = jobs.submit({ ...SUBMIT, targetKey: "clip:c9" });
    release(done({ job_id: "forge-1" }));
    await expect(first).resolves.toBeNull();
    await second;
    expect(jobs.active).toBeNull();
    expect(history.renders).toHaveLength(1);
    expect(history.renders[0].forge_job_id).toBe("forge-2");
  });
});

describe("cancel", () => {
  it("cancels a queued job and clears active", async () => {
    vi.spyOn(forgeApi, "cancelJob").mockResolvedValue({ ok: true, state: "cancelled" });
    jobs.active = { forgeJobId: "forge-1", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mix", progress: null };
    await jobs.cancel();
    expect(forgeApi.cancelJob).toHaveBeenCalledWith("forge-1");
    expect(jobs.active).toBeNull();
  });

  it("surfaces the 409 on a running pass instead of throwing, and keeps the job active", async () => {
    vi.spyOn(forgeApi, "cancelJob").mockRejectedValue(new ForgeApiError(409, "cannot cancel a running pass"));
    jobs.active = { forgeJobId: "forge-1", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mix", progress: null };
    await expect(jobs.cancel()).resolves.toBeUndefined();
    expect(jobs.lastError?.message).toContain("cannot cancel a running pass");
    expect(jobs.active?.forgeJobId).toBe("forge-1");
  });

  it("is a no-op with nothing running", async () => {
    const spy = vi.spyOn(forgeApi, "cancelJob");
    await jobs.cancel();
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("gpuBusyOther (§9.7 `GPU busy — <job_id>`)", () => {
  it("is set from /status when the GPU holds a job this client did not start", async () => {
    vi.spyOn(forgeApi, "status").mockResolvedValue({ ok: true, busy: true, job_id: "dash-77", log_tail: [], progress: null });
    await jobs.pollStatusOnce();
    expect(jobs.gpuBusyOther).toBe("dash-77");
  });

  it("stays null for this client's own job and clears when the GPU goes idle", async () => {
    jobs.active = { forgeJobId: "forge-1", op: "generate", kind: "gen", sourceClipId: null, targetKey: "session", progress: null };
    // The real shape: /status.job_id is the server's output-dir id; the queue id is in progress.
    vi.spyOn(forgeApi, "status").mockResolvedValue({
      ok: true, busy: true, job_id: "20261001-120000-forgecommit", log_tail: [], progress: progress({ job_id: "forge-1" }),
    });
    await jobs.pollStatusOnce();
    expect(jobs.gpuBusyOther).toBeNull();
    vi.spyOn(forgeApi, "status").mockResolvedValue({ ok: true, busy: false, job_id: null, log_tail: [], progress: null });
    await jobs.pollStatusOnce();
    expect(jobs.gpuBusyOther).toBeNull();
  });

  it("names another forge client's job by its queue id (review 2026-10-01)", async () => {
    jobs.active = { forgeJobId: "forge-1", op: "generate", kind: "gen", sourceClipId: null, targetKey: "session", progress: null };
    vi.spyOn(forgeApi, "status").mockResolvedValue({
      ok: true, busy: true, job_id: "20261001-120000-forgeinpaint", log_tail: [], progress: progress({ job_id: "forge-9" }),
    });
    await jobs.pollStatusOnce();
    expect(jobs.gpuBusyOther).toBe("forge-9");
  });

  it("swallows a dead server -- a stopped render server is a normal state on this box", async () => {
    jobs.gpuBusyOther = "dash-77";
    vi.spyOn(forgeApi, "status").mockRejectedValue(new ForgeApiError(502, "render server unreachable"));
    await expect(jobs.pollStatusOnce()).resolves.toBeUndefined();
    expect(jobs.gpuBusyOther).toBeNull();
  });
});
