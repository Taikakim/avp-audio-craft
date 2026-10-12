import { describe, expect, it } from "vitest";
import type { ForgeClip } from "../../forge/types";
import { circularMeanPhase, downbeatPhaseShifts, meanNativeBpm, shortestPhaseDelta } from "../tempoMatch";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false,
    audio: { kind: "crop", crop_id: "x" }, previewAudio: null, native_bpm: null,
    detune_cents: 0, downbeats_sec: [], render: {}, a2a: null, latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

describe("MATCH BPM meets at the mean native tempo (spec §4.3)", () => {
  it("averages the clips that have a known native_bpm", () => {
    const clips = [clip({ native_bpm: 120 }), clip({ native_bpm: 140 }), clip({ native_bpm: null })];
    expect(meanNativeBpm(clips)).toBeCloseTo(130, 9);
  });

  it("is null with no clip carrying a native_bpm", () => {
    expect(meanNativeBpm([clip({}), clip({})])).toBeNull();
  });

  it("is just that one tempo with a single known clip", () => {
    expect(meanNativeBpm([clip({ native_bpm: 90 })])).toBe(90);
  });
});

describe("circular mean of bar phases", () => {
  it("averages two phases either side of zero without wrapping the wrong way", () => {
    expect(circularMeanPhase([0.95, 0.05])).toBeCloseTo(0, 6);
  });

  it("is null when nothing is given", () => {
    expect(circularMeanPhase([])).toBeNull();
  });

  it("is null when phases cancel exactly (uniformly spread around the bar)", () => {
    expect(circularMeanPhase([0, 1 / 3, 2 / 3])).toBeNull();
  });
});

describe("shortest phase delta", () => {
  it("goes the short way round the bar in either direction", () => {
    expect(shortestPhaseDelta(0.1, 0.9)).toBeCloseTo(-0.2, 9);
    expect(shortestPhaseDelta(0.9, 0.1)).toBeCloseTo(0.2, 9);
  });

  it("is zero when already aligned", () => {
    expect(shortestPhaseDelta(0.4, 0.4)).toBe(0);
  });
});

describe("MATCH DOWNBEATS shifts by the shortest path onto the common phase (spec §4.3)", () => {
  it("leaves a solo clip alone -- nothing to align to", () => {
    const clips = [clip({ id: "a", start_sec: 0, downbeats_sec: [0] })];
    expect(downbeatPhaseShifts(clips, 120, 4).size).toBe(0);
  });

  it("moves two clips onto their circular-mean phase, tempo untouched", () => {
    // 120 BPM 4/4 -> bar = 2s. a's downbeat at 0.1s (phase 0.05), b's at 1.9s (phase 0.95).
    // Circular mean of [0.05, 0.95] is 0 -- each moves the short way (0.1s).
    const clips = [
      clip({ id: "a", start_sec: 0, downbeats_sec: [0.1] }),
      clip({ id: "b", start_sec: 0, downbeats_sec: [1.9] }),
    ];
    const shifts = downbeatPhaseShifts(clips, 120, 4);
    expect(shifts.get("a")).toBeCloseTo(-0.1, 9);
    expect(shifts.get("b")).toBeCloseTo(0.1, 9);
  });

  it("ignores a clip with no downbeat data", () => {
    const clips = [
      clip({ id: "a", start_sec: 0, downbeats_sec: [0.1] }),
      clip({ id: "b", start_sec: 0, downbeats_sec: [1.9] }),
      clip({ id: "c", start_sec: 0, downbeats_sec: [] }),
    ];
    expect(downbeatPhaseShifts(clips, 120, 4).has("c")).toBe(false);
  });

  // C2 fix wave: this is the real consumer path clipDownbeats' own tests don't
  // cover -- a clip whose native_bpm differs from the project bpm must have
  // its downbeat phase computed in the STRETCHED (scaled) domain, not the raw
  // source-second value straight from /forge/analyze.
  it("scales a clip's downbeat by native_bpm/projectBpm before computing its phase", () => {
    // 120 BPM project, 4/4 -> bar = 2s. Clip "a" native 120 (no scaling, phase
    // stays 0.05 at raw 0.1s). Clip "b" native 240 in a 120 project (scale
    // 240/120 = 2): a RAW source downbeat at 0.95s would misread as phase
    // 0.475 (barely moves); scaled to 1.9s in the timeline it is phase 0.95,
    // the mirror of a's 0.05 -- exactly the "two clips converge" case the
    // plain (unscaled) tempoMatch.test.ts case above already covers, just
    // reached through a native_bpm that actually needs scaling to get there.
    const clips = [
      clip({ id: "a", native_bpm: 120, start_sec: 0, downbeats_sec: [0.1] }),
      clip({ id: "b", native_bpm: 240, start_sec: 0, downbeats_sec: [0.95] }),
    ];
    const shifts = downbeatPhaseShifts(clips, 120, 4);
    expect(shifts.get("a")).toBeCloseTo(-0.1, 9);
    expect(shifts.get("b")).toBeCloseTo(0.1, 9);
  });
});
