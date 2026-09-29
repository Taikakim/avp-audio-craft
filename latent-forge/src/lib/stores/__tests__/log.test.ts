import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { forgeApi } from "../../forge/api";
import { LOG_RING, logStore, logTone } from "../log.svelte";

beforeEach(() => logStore.clear());
afterEach(() => {
  logStore.stop();
  vi.restoreAllMocks();
});

describe("logTone colours a line the way the TERMINAL draws it", () => {
  it("separates errors, shell echoes and ordinary output", () => {
    expect(logTone("RuntimeError: non-finite latents in lane 2")).toBe("error");
    expect(logTone("commit failed after stage 4")).toBe("error");
    expect(logTone("$ player /status → ok")).toBe("dim");
    expect(logTone("warning: sigma_min below the schedule floor")).toBe("accent");
    expect(logTone("lane 2  decode 000412.npy  [256,4096] → 45.0 s audio")).toBe("text");
  });
});

describe("append obeys the $state proxy rule", () => {
  it("returns the array's live element, not the object it pushed", () => {
    const line = logStore.append("lane 1  encode", 7);
    expect(line).toBe(logStore.lines[logStore.lines.length - 1]);
    line.tone = "error";
    expect(logStore.lines[0].tone).toBe("error");
  });

  it("keeps at most the server's own ring of 400 lines", () => {
    for (let i = 1; i <= LOG_RING + 25; i += 1) logStore.append(`line ${i}`, i);
    expect(logStore.lines).toHaveLength(LOG_RING);
    expect(logStore.lines[0].text).toBe("line 26");
    expect(logStore.seq).toBe(LOG_RING + 25);
  });
});

describe("poll reads /forge/log incrementally and /status for the busy dot", () => {
  it("asks for lines after the last sequence it holds and lights the dot", async () => {
    const log = vi.spyOn(forgeApi, "log").mockResolvedValue({
      ok: true,
      seq: 12,
      lines: [
        { seq: 11, text: "lane 2  bungee  stretch 127.6 → 124.0 bpm" },
        { seq: 12, text: "master  decode → 45.0 s   peak -0.4 dBFS" },
      ],
    });
    vi.spyOn(forgeApi, "status").mockResolvedValue({
      ok: true,
      busy: true,
      job_id: "forge-20260916-120000-1",
      log_tail: [],
      progress: null,
    });

    await logStore.poll();
    expect(log).toHaveBeenCalledWith(0);
    expect(logStore.lines.map((l) => l.seq)).toEqual([11, 12]);
    expect(logStore.seq).toBe(12);
    expect(logStore.busy).toBe(true);

    await logStore.poll();
    expect(log).toHaveBeenLastCalledWith(12);
  });

  it("reports a dead server as one red line and does not repeat it every tick", async () => {
    vi.spyOn(forgeApi, "log").mockRejectedValue(new Error("render server unreachable (empty response from /forge/log)"));
    vi.spyOn(forgeApi, "status").mockRejectedValue(new Error("render server unreachable (empty response from /status)"));

    await logStore.poll();
    await logStore.poll();

    expect(logStore.lines).toHaveLength(1);
    expect(logStore.lines[0].tone).toBe("error");
    expect(logStore.lines[0].text).toContain("render server unreachable");
    expect(logStore.busy).toBe(false);
  });

  it("stops polling when the tab is left", async () => {
    const log = vi.spyOn(forgeApi, "log").mockResolvedValue({ ok: true, seq: 0, lines: [] });
    vi.spyOn(forgeApi, "status").mockResolvedValue({
      ok: true, busy: false, job_id: null, log_tail: [], progress: null,
    });
    vi.useFakeTimers();
    logStore.start(1000);
    await vi.advanceTimersByTimeAsync(2500);
    const seenWhileRunning = log.mock.calls.length;
    logStore.stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(log.mock.calls.length).toBe(seenWhileRunning);
    expect(seenWhileRunning).toBeGreaterThanOrEqual(3);
    vi.useRealTimers();
  });
});
