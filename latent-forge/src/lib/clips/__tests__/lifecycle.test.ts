import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError } from "../../forge/api";
import type { AudioRef } from "../../forge/types";
import { arrangement } from "../../stores/arrangement.svelte";
import { addClip, scheduleStretch, stretchCacheKey, stretchSpeed } from "../lifecycle";

const REF: AudioRef = { kind: "crop", crop_id: "000412" };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function reset() {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  arrangement.setBpm(120);
}

beforeEach(reset);
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("adding a clip from an OS file drop (spec §7.3)", () => {
  it("uploads first and takes the clip's duration from the upload response", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/forge/upload")) {
        return jsonResponse({
          ok: true, ref: { kind: "upload", sha256: "abc" }, path: "/x", bytes: 1,
          duration_sec: 5.5, sample_rate: 44100, channels: 2,
        });
      }
      if (url === "/forge/analyze") {
        return jsonResponse({
          ok: true, bpm: 128, bpm_candidates: [], beats_sec: [], downbeats_sec: [0.1],
          duration_sec: 5.5, source: "librosa",
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File([new Uint8Array([1, 2, 3])], "kick.wav", { type: "audio/wav" });
    const { clip, analyzeError } = await addClip({ lane: 0, startSec: 0, file });

    expect(analyzeError).toBeNull();
    // 5.5 is the SOURCE duration the upload reported. Analysis then supplies
    // native_bpm 128 against a 120 bpm project, which moves the clip into the
    // stretched domain -- lifecycle.ts's own stretchSpeed doc pins the rule:
    //   dur_sec = nativeDur * (native_bpm / projectBpm) = 5.5 * 128/120
    // This assertion used to expect the raw 5.5, which is what the missing
    // rescale in setClipBpm actually produced. It was encoding the bug: a
    // 128 bpm clip in a 120 bpm project needs MORE than 5.5 s of timeline to
    // play whole, so the old value cut its stretched preview short.
    expect(clip.dur_sec).toBeCloseTo(5.5 * (128 / 120), 9);
    expect(clip.native_bpm).toBe(128);
    expect(clip.audio).toEqual({ kind: "upload", sha256: "abc" });
    expect(fetchMock.mock.calls[0][0]).toBe("/forge/upload?filename=kick.wav");
  });
});

describe("analysis (spec §7.3: fills native_bpm and downbeats_sec unless already known)", () => {
  it("skips analyze when the caller already knows both", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("must not be called");
    });
    vi.stubGlobal("fetch", fetchMock);
    const { clip } = await addClip({
      lane: 0, startSec: 0, ref: REF, durationSec: 4, nativeBpm: 120, downbeatsSec: [0, 2],
    });
    expect(clip.native_bpm).toBe(120);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("caches analyze per ref: two clips of the same source ask once", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/forge/analyze") {
        calls++;
        return jsonResponse({
          ok: true, bpm: 90, bpm_candidates: [], beats_sec: [], downbeats_sec: [], duration_sec: 4,
          source: "librosa",
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    }));
    await addClip({ lane: 0, startSec: 0, ref: REF, durationSec: 4 });
    await addClip({ lane: 1, startSec: 0, ref: REF, durationSec: 4 });
    expect(calls).toBe(1);
  });

  it("degrades honestly: a failed analyze leaves native_bpm null and the clip on the timeline", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/forge/analyze") return jsonResponse({ ok: false, error: "librosa failed" }, 500);
      throw new Error(`unexpected fetch ${url}`);
    }));
    const { clip, analyzeError } = await addClip({ lane: 0, startSec: 0, ref: REF, durationSec: 4 });
    expect(clip.native_bpm).toBeNull();
    expect(analyzeError).toBeInstanceOf(ForgeApiError);
    expect(arrangement.clips.some((c) => c.id === clip.id)).toBe(true);
  });
});

describe("stretch speed and cache key", () => {
  it("speed is projectBpm / nativeBpm, matching the non-elastic duration math in T1", () => {
    expect(stretchSpeed(120, 140)).toBeCloseTo(140 / 120, 9);
  });

  it("rounds the same way the server's cache key does (spec §6.3)", () => {
    expect(stretchCacheKey(REF, 1.166667, -0.5)).toBe(`${JSON.stringify(REF)}::1.166667::-0.5000`);
  });
});

describe("stretch (spec §7.3: debounced 400ms, cached, non-blocking on failure)", () => {
  it("is debounced: an edit inside the window pushes the call out instead of adding a second one", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/forge/stretch") return jsonResponse({ ok: true, ref: { kind: "path", path: "/x" }, duration_sec: 3 });
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const { clip } = await addClip({ lane: 0, startSec: 0, ref: REF, durationSec: 4, nativeBpm: 100 });
    // addClip already armed one stretch at t=0; a further edit at t=200 must push it out.
    await vi.advanceTimersByTimeAsync(200);
    scheduleStretch(clip.id);
    await vi.advanceTimersByTimeAsync(200);
    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("caches by (ref, speed, semitones): two clips that meet at the same speed share one call", async () => {
    vi.useFakeTimers();
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/forge/stretch") {
        calls++;
        return jsonResponse({ ok: true, ref: { kind: "path", path: "/x" }, duration_sec: 3 });
      }
      throw new Error(`unexpected fetch ${url}`);
    }));
    const a = await addClip({ lane: 0, startSec: 0, ref: REF, durationSec: 4, nativeBpm: 100 });
    const b = await addClip({ lane: 1, startSec: 0, ref: REF, durationSec: 4, nativeBpm: 100 });
    await vi.advanceTimersByTimeAsync(400);
    expect(calls).toBe(1);
    expect(arrangement.clips.find((c) => c.id === a.clip.id)!.previewAudio).toEqual({ kind: "path", path: "/x" });
    expect(arrangement.clips.find((c) => c.id === b.clip.id)!.previewAudio).toEqual({ kind: "path", path: "/x" });
  });

  it("is identity (no call) when native_bpm already matches the project and detune is 0", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn(async () => {
      throw new Error("must not be called");
    });
    vi.stubGlobal("fetch", fetchMock);
    await addClip({ lane: 0, startSec: 0, ref: REF, durationSec: 4, nativeBpm: 120 });
    await vi.advanceTimersByTimeAsync(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("a stretch failure surfaces through onError and never removes the clip", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/forge/stretch") return jsonResponse({ ok: false, error: "bungee crashed" }, 500);
      throw new Error(`unexpected fetch ${url}`);
    }));
    const { clip } = await addClip({ lane: 0, startSec: 0, ref: REF, durationSec: 4, nativeBpm: 100 });
    const onError = vi.fn();
    scheduleStretch(clip.id, onError); // re-arm with the callback attached
    await vi.advanceTimersByTimeAsync(400);
    expect(onError).toHaveBeenCalledWith(expect.any(ForgeApiError));
    expect(arrangement.clips.some((c) => c.id === clip.id)).toBe(true);
  });
});
