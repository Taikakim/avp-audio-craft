import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PlaybackClip, PlaybackEngine, PlaybackLane } from "../../audio/transport";
import type { AudioRef, RenderHistoryEntry } from "../../forge/types";
import { history } from "../../render/history.svelte";
import { masterSource } from "../../render/masterSource.svelte";
import { arrangement } from "../arrangement.svelte";
import { PlaybackStore } from "../transport.svelte";

const REF: AudioRef = { kind: "upload", sha256: "a".repeat(64) };

function fakeEngine() {
  const calls: { clips: PlaybackClip[]; lanes: PlaybackLane[]; fromSec: number }[] = [];
  const engine: PlaybackEngine = {
    play: vi.fn(async (clips, lanes, fromSec) => { calls.push({ clips, lanes, fromSec }); }),
    pause: vi.fn(), stop: vi.fn(),
    seek: vi.fn(async (sec, clips, lanes) => { calls.push({ clips, lanes, fromSec: sec }); }),
    preload: vi.fn(async () => ({}) as AudioBuffer),
    invalidate: vi.fn(), scrub: vi.fn(), stopScrub: vi.fn(),
    currentTimeSec: 0, playing: false,
  } as unknown as PlaybackEngine;
  return { engine, calls };
}

function mixEntry(): RenderHistoryEntry {
  return {
    job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00",
    kind: "mix", dur_sec: 96, source_clip_id: null, created: 1,
  };
}

beforeEach(() => {
  history.clear();
  masterSource.set("preview");
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
});

describe("the timeline transport follows the A/B toggle (spec §9.6)", () => {
  it("plays the arrangement while PREVIEW is selected", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    const { engine, calls } = fakeEngine();
    await new PlaybackStore(engine).play();
    expect(calls[0].clips).toHaveLength(1);
    expect(calls[0].clips[0].id).not.toBe("mixdown");
  });

  it("plays mix.wav, and only mix.wav, while MIXDOWN is selected", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    history.add(mixEntry());
    history.mixdown = 0;
    masterSource.set("mixdown");

    const { engine, calls } = fakeEngine();
    await new PlaybackStore(engine).play();
    expect(calls[0].clips).toHaveLength(1);
    expect(calls[0].clips[0].id).toBe("mixdown");
    expect(calls[0].clips[0].previewUrl).toContain("mix.wav");
  });

  it("is not silenced by a muted lane 0 — the commit already applied the mute", async () => {
    arrangement.setLaneMuted(0, true);
    history.add(mixEntry());
    history.mixdown = 0;
    masterSource.set("mixdown");

    const { engine, calls } = fakeEngine();
    await new PlaybackStore(engine).play();
    expect(calls[0].lanes).toEqual([{ index: 0, muted: false, solo: false, gain: 1 }]);
  });

  it("re-snapshots on a seek, so switching source mid-play swaps what is heard", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    const store = new PlaybackStore(fakeEngine().engine);
    const { engine, calls } = fakeEngine();
    void store;
    const playing = new PlaybackStore(engine);
    await playing.play();
    masterSource.set("mixdown");
    await playing.seek(40);
    expect(calls[calls.length - 1].clips[0].id).toBe("mixdown");
    expect(calls[calls.length - 1].fromSec).toBe(40);
  });
});
