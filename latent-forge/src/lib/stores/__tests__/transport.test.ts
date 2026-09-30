// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import type { PlaybackEngine } from "../../audio/transport";
import { arrangement } from "../arrangement.svelte";
import { PlaybackStore } from "../transport.svelte";

function fakeEngine(): PlaybackEngine & { calls: string[]; time: number } {
  const eng = {
    calls: [] as string[],
    time: 0,
    onEnded: undefined as (() => void) | undefined,
    get currentTimeSec() { return eng.time; },
    get playing() { return eng.calls.at(-1) === "play" || eng.calls.at(-1)?.startsWith("seek") === true; },
    async play(_clips: unknown, _lanes: unknown, fromSec: number) { eng.calls.push("play"); eng.time = fromSec; },
    pause() { eng.calls.push("pause"); },
    stop() { eng.calls.push("stop"); eng.time = 0; },
    async seek(sec: number) { eng.calls.push(`seek:${sec}`); eng.time = sec; },
    async preload() { return {} as AudioBuffer; },
    invalidate() {},
    scrub(_buffer: AudioBuffer, atSec: number) { eng.calls.push(`scrub:${atSec}`); },
    stopScrub() { eng.calls.push("stopScrub"); },
    updateLanes(_lanes: unknown) { eng.calls.push("updateLanes"); },
  };
  return eng;
}

function resetArrangement() {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
}

beforeEach(resetArrangement);

describe("play / pause / stop drive the injected engine", () => {
  it("plays from the current playhead", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.play();
    expect(engine.calls).toEqual(["play"]);
    expect(p.playing).toBe(true);
  });

  it("is a no-op to play twice in a row", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.play();
    await p.play();
    expect(engine.calls).toEqual(["play"]);
  });

  it("pausing pulls the engine's clock into the playhead", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.play();
    engine.time = 3.5;
    p.pause();
    expect(p.playheadSec).toBe(3.5);
    expect(p.playing).toBe(false);
    expect(engine.calls).toContain("pause");
  });

  it("stop resets the playhead to zero when not looping", () => {
    const p = new PlaybackStore(fakeEngine());
    p.stop();
    expect(p.playheadSec).toBe(0);
    expect(p.playing).toBe(false);
  });

  it("stop resets the playhead to the loop start when looping", () => {
    const p = new PlaybackStore(fakeEngine());
    p.setLoopRegion(2, 6);
    p.toggleLoop();
    p.stop();
    expect(p.playheadSec).toBe(2);
  });

  it("togglePlay flips between play and pause", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.togglePlay();
    expect(p.playing).toBe(true);
    await p.togglePlay();
    expect(p.playing).toBe(false);
    expect(engine.calls).toEqual(["play", "pause"]);
  });

  it("the engine's onEnded stops the store", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.play();
    engine.onEnded?.();
    expect(p.playing).toBe(false);
  });
});

describe("seek", () => {
  it("clamps at zero and updates the playhead immediately even when stopped", async () => {
    const p = new PlaybackStore(fakeEngine());
    await p.seek(-5);
    expect(p.playheadSec).toBe(0);
    await p.seek(12);
    expect(p.playheadSec).toBe(12);
  });

  it("re-schedules through the engine while playing", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.play();
    await p.seek(9);
    expect(engine.calls).toEqual(["play", "seek:9"]);
  });
});

describe("loop region", () => {
  it("starts off, with an empty region", () => {
    const p = new PlaybackStore(fakeEngine());
    expect(p.loopOn).toBe(false);
    expect(p.loopStartSec).toBe(0);
    expect(p.loopEndSec).toBe(0);
  });

  it("toggles", () => {
    const p = new PlaybackStore(fakeEngine());
    p.toggleLoop();
    expect(p.loopOn).toBe(true);
  });

  it("orders the region regardless of drag direction", () => {
    const p = new PlaybackStore(fakeEngine());
    p.setLoopRegion(6, 2);
    expect(p.loopStartSec).toBe(2);
    expect(p.loopEndSec).toBe(6);
  });
});

describe("syncPlayhead", () => {
  it("does nothing while stopped", () => {
    const p = new PlaybackStore(fakeEngine());
    p.syncPlayhead();
    expect(p.playheadSec).toBe(0);
  });

  it("pulls the engine's clock in while playing", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.play();
    engine.time = 4.2;
    p.syncPlayhead();
    expect(p.playheadSec).toBe(4.2);
  });

  it("wraps to the loop start once the region's end is reached", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    p.setLoopRegion(1, 3);
    p.toggleLoop();
    await p.play();
    engine.time = 3;
    p.syncPlayhead();
    expect(engine.calls).toContain("seek:1");
  });
});

describe("updateLiveLanes pushes mute/solo/gain to the engine mid-playback (I7 fix wave)", () => {
  it("calls the engine's updateLanes, and does so via arrangement's attached hook", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    arrangement.attachLiveLaneUpdater(() => p.updateLiveLanes());
    try {
      await p.play();
      arrangement.toggleMute(0);
      arrangement.toggleSolo(1);
      arrangement.setLaneGain(2, 0.4);
      expect(engine.calls.filter((c) => c === "updateLanes")).toHaveLength(3);
    } finally {
      // undo the lane edits and detach so this doesn't leak into other tests
      arrangement.toggleMute(0);
      arrangement.toggleSolo(1);
      arrangement.setLaneGain(2, 1);
      arrangement.attachLiveLaneUpdater(null);
    }
  });
});

describe("scrubClip (Task 6: Alt+drag audition, spec §10 X2)", () => {
  it("preloads the clip's audio, then scrubs the engine to the given offset", async () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    await p.scrubClip("/forge/audio?ref=x", 1.25);
    expect(engine.calls).toEqual(["scrub:1.25"]);
  });

  it("stopScrub passes straight through to the engine", () => {
    const engine = fakeEngine();
    const p = new PlaybackStore(engine);
    p.stopScrub();
    expect(engine.calls).toEqual(["stopScrub"]);
  });
});
