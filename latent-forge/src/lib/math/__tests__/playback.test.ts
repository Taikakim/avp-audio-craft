import { describe, expect, it } from "vitest";
import type { ForgeClip, ForgeLane } from "../../forge/types";
import { loopWrap, toPlaybackClips, toPlaybackLanes } from "../playback";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    audio: { kind: "crop", crop_id: "000412" }, native_bpm: null, detune_cents: 0,
    downbeats_sec: [], render: {} as never, a2a: null, latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

function lane(over: Partial<ForgeLane>): ForgeLane {
  return { index: 0, name: "LANE 1", muted: false, solo: false, gain: 1, chain: {} as never, ...over };
}

describe("toPlaybackClips resolves audio through forgeApi.audioUrl, never a stored previewUrl", () => {
  it("maps every field Transport.play needs", () => {
    const c = clip({ id: "c1", lane: 2, start_sec: 3, dur_sec: 5, offset_sec: 1 });
    expect(toPlaybackClips([c])).toEqual([
      { id: "c1", laneIndex: 2, startSec: 3, durationSec: 5, offsetSec: 1,
        previewUrl: `/forge/audio?ref=${encodeURIComponent('{"kind":"crop","crop_id":"000412"}')}` },
    ]);
  });
});

describe("toPlaybackLanes carries only what the engine's gain logic needs", () => {
  it("maps index/muted/solo/gain", () => {
    const l = lane({ index: 1, muted: true, solo: false, gain: 0.5 });
    expect(toPlaybackLanes([l])).toEqual([{ index: 1, muted: true, solo: false, gain: 0.5 }]);
  });
});

describe("loopWrap (spec: LOOP region toggle)", () => {
  it("returns null when looping is off", () => {
    expect(loopWrap(10, false, 0, 4)).toBeNull();
  });

  it("returns null while inside the region", () => {
    expect(loopWrap(2, true, 0, 4)).toBeNull();
  });

  it("returns the loop start once the playhead reaches the end", () => {
    expect(loopWrap(4, true, 0, 4)).toBe(0);
    expect(loopWrap(5, true, 1, 4)).toBe(1);
  });

  it("is inert on a degenerate or backwards region", () => {
    expect(loopWrap(9, true, 4, 4)).toBeNull();
    expect(loopWrap(9, true, 4, 2)).toBeNull();
  });
});
