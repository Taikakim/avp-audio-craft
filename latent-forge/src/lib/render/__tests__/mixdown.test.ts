import { beforeEach, describe, expect, it, vi } from "vitest";
import { arrangement } from "../../stores/arrangement.svelte";
import { forgeApi } from "../../forge/api";
import type { JobRecord } from "../../forge/types";
import { signalKeyOf } from "../../mix/signalPath";
import { jobs } from "../jobs.svelte";
import { history } from "../history.svelte";
import { MIXDOWN_TARGET_KEY, mixdown, mixdownBlock, runMixdown, signalInputNow } from "../mixdown.svelte";

const REF = { kind: "upload", sha256: "a".repeat(64) } as const;

function addClip() {
  return arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
}

/** A finished JobRecord, the same shape `jobs.test.ts`'s own `done()` builds. */
function done(patch: Partial<JobRecord> = {}): JobRecord {
  return {
    ok: true, job_id: "forge-1", op: "commit", payload: {}, state: "done", position: 0,
    progress: null, result: { urls: ["/files/renders/mix.wav"], meta: {} }, error: null,
    created: 1, started: 1, finished: 2, ...patch,
  } as JobRecord;
}

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  jobs.active = null;
  jobs.lastError = null;
  jobs.gpuBusyOther = null;
  history.clear();
  mixdown.reset();
  vi.restoreAllMocks();
});

describe("mixdownBlock -- why MIXDOWN is disabled, in the button's own words", () => {
  it("names the empty arrangement, using validate_commit's own sentence", () => {
    expect(mixdownBlock()).toBe("nothing to commit — the arrangement has no clips");
  });

  it("is null once there is something to commit", () => {
    addClip();
    expect(mixdownBlock()).toBeNull();
  });

  it("names the running job -- §7.1 disables every render control while one runs", () => {
    addClip();
    jobs.active = { forgeJobId: "forge-1", op: "generate", kind: "gen", sourceClipId: null, targetKey: "session", progress: null };
    expect(mixdownBlock()).toMatch(/running/i);
    jobs.active = null;
    jobs.gpuBusyOther = "dash-77";
    expect(mixdownBlock()).toBe("GPU busy — dash-77");
  });
});

describe("runMixdown", () => {
  it("submits op `commit`, kind `mix`, on the MIXDOWN target key", async () => {
    addClip();
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    await runMixdown();
    expect(submit).toHaveBeenCalledTimes(1);
    const req = submit.mock.calls[0][0];
    expect(req.op).toBe("commit");
    expect(req.kind).toBe("mix");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey).toBe(MIXDOWN_TARGET_KEY);
    expect(Object.keys(req.payload as object)).toContain("duration_sec");
  });

  it("does not submit when blocked, and shows the reason as the inline error instead", async () => {
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    await runMixdown();
    expect(submit).not.toHaveBeenCalled();
    expect(jobs.lastError).toEqual({ targetKey: MIXDOWN_TARGET_KEY, message: "nothing to commit — the arrangement has no clips" });
  });

  it("turns a client-side payload refusal into the same inline error, never a throw", async () => {
    addClip();
    arrangement.clips[0].detune_cents = 900;         // outside ±100: validate_commit would 400
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    await expect(runMixdown()).resolves.toBeUndefined();
    expect(submit).not.toHaveBeenCalled();
    expect(jobs.lastError?.message).toMatch(/detune/);
  });

  it("stores a finished commit's meta.stages with the signal key of the arrangement it described", async () => {
    addClip();
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    // Mock the TRANSPORT, not `jobs.submit`: the key is stamped by Step 5's `jobs.onDone` hook,
    // which only fires from inside a real `submit`. A `jobs.submit` mock that calls
    // `acceptStages([...])` with one argument defaults `key` to `this.key`, which `reset()` just
    // set to null -- the test would then assert the very wiring it had stubbed out.
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(done({
      job_id: "forge-1",
      op: "commit",
      // cast: the plan's literal omits JobResult fields the code under test never reads
      result: { urls: ["/files/renders/mix.wav"], meta: { stages: [{ label: "MIX", on: true, note: "(1+2) + (3+4)", seconds: 2.5 }] } } as unknown as JobRecord["result"],
    }));
    const expected = signalKeyOf(signalInputNow());
    await runMixdown();
    expect(mixdown.stages).toHaveLength(1);
    expect(mixdown.key).toBe(expected);
  });

  it("leaves the stages untouched when the commit fails", async () => {
    addClip();
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    vi.spyOn(jobs, "submit").mockResolvedValue(null);
    await runMixdown();
    expect(mixdown.stages).toBeNull();
    expect(mixdown.key).toBeNull();
  });
});
