import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError } from "../../forge/api";
import type { AudioRef } from "../../forge/types";
import { arrangement } from "../../stores/arrangement.svelte";
import { replaceAudio } from "../lifecycle";

const OLD: AudioRef = { kind: "upload", sha256: "a".repeat(64) };
const NEW: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

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

describe("lifecycle.replaceAudio — the analyze/stretch follow-up, mirroring addClip", () => {
  it("re-analyzes the NEW audio, because native_bpm was cleared", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/forge/analyze") {
        seen.push(JSON.parse(String(init?.body)));
        return jsonResponse({
          ok: true, bpm: 96, bpm_candidates: [], beats_sec: [], downbeats_sec: [0.25],
          duration_sec: 12, source: "librosa",
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    }));

    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD, nativeBpm: 128 });
    await replaceAudio({ clipId: c.id, ref: NEW, durationSec: 12 });

    expect(c.native_bpm).toBe(96);
    expect(c.downbeats_sec).toEqual([0.25]);
    expect(JSON.stringify(seen)).toContain("gen-7");
  });

  it("shrinks dur_sec to the render when the render is shorter, so the clip never claims silence", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({
      ok: true, bpm: null, bpm_candidates: [], beats_sec: [], downbeats_sec: [], duration_sec: 12, source: "librosa",
    })));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    await replaceAudio({ clipId: c.id, ref: NEW, durationSec: 12 });
    expect(c.dur_sec).toBe(12);
  });

  it("leaves dur_sec alone when the render is longer — a replace never creates an overlap", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({
      ok: true, bpm: null, bpm_candidates: [], beats_sec: [], downbeats_sec: [], duration_sec: 90, source: "librosa",
    })));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    await replaceAudio({ clipId: c.id, ref: NEW, durationSec: 90 });
    expect(c.dur_sec).toBe(30);
  });

  it("keeps the swap when analysis fails, and hands the error back — §7.3's honest degradation", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ ok: false, error: "no drive" }, 503)));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    const out = await replaceAudio({ clipId: c.id, ref: NEW, durationSec: null });
    expect(c.audio).toEqual(NEW);
    expect(c.history).toEqual([OLD]);
    expect(out.analyzeError).toBeInstanceOf(ForgeApiError);
  });

  it("does nothing at all for a clip that was removed first", async () => {
    const out = await replaceAudio({ clipId: "gone", ref: NEW, durationSec: 12 });
    expect(out.analyzeError).toBeNull();
    expect(arrangement.clips).toHaveLength(0);
  });
});
