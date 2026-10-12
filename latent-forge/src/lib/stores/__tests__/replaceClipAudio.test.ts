import { beforeEach, describe, expect, it } from "vitest";
import type { AudioRef } from "../../forge/types";
import { arrangement } from "../arrangement.svelte";

const OLD: AudioRef = { kind: "upload", sha256: "a".repeat(64) };
const NEW: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

function reset() {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
}

beforeEach(reset);

describe("arrangement.replaceClipAudio — the first writer ForgeClip.history has ever had", () => {
  it("swaps the audio and pushes the old ref onto the clip's history", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(c.id, NEW);
    expect(c.audio).toEqual(NEW);
    expect(c.history).toEqual([OLD]);
  });

  it("keeps the order across two replacements, oldest first", () => {
    const mid: AudioRef = { kind: "render", job_id: "gen-1", file: "m.wav" };
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(c.id, mid);
    arrangement.replaceClipAudio(c.id, NEW);
    expect(c.history).toEqual([OLD, mid]);
    expect(c.audio).toEqual(NEW);
  });

  it("stores a snapshot, not the live proxy, so a later swap cannot rewrite history", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(c.id, NEW);
    // Mutating the clip's CURRENT audio must not reach the archived entry.
    (c.audio as { file: string }).file = "tampered.wav";
    expect(c.history[0]).toEqual(OLD);
  });

  it("drops the stretched preview and the analysis, which describe the old file", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD, nativeBpm: 128 });
    arrangement.setDownbeats(c.id, [0.5, 1.0]);
    arrangement.setPreviewAudio(c.id, { kind: "upload", sha256: "b".repeat(64) });
    arrangement.replaceClipAudio(c.id, NEW);
    expect(c.native_bpm).toBeNull();
    expect(c.downbeats_sec).toEqual([]);
    expect(c.previewAudio ?? null).toBeNull();
    expect(c.offset_sec).toBe(0);
  });

  it("marks a valid latent stale, and leaves 'none' alone — M5's duplicateClip rule", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    a.latentState = "valid";
    arrangement.replaceClipAudio(a.id, NEW);
    expect(a.latentState).toBe("stale");

    const b = arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(b.id, NEW);
    expect(b.latentState).toBe("none");
  });

  it("is a no-op for an id that is not there", () => {
    expect(() => arrangement.replaceClipAudio("gone", NEW)).not.toThrow();
    expect(arrangement.clips).toHaveLength(0);
  });
});
