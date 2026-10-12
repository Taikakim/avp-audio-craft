import { describe, expect, it } from "vitest";
import type { ForgeClip } from "../../forge/types";
import {
  clipDownbeats, coincidence, COINCIDENCE_DIVISION, COINCIDENCE_RAMP_EXP, coincidenceToleranceSec,
  downbeatColor, laneDownbeats,
} from "../downbeats";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false,
    audio: { kind: "crop", crop_id: "x" }, native_bpm: null, detune_cents: 0,
    downbeats_sec: [], render: {}, a2a: null, latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

describe("a clip's downbeats are its own, moved onto the timeline", () => {
  it("offsets by start and trim", () => {
    // 0 is trimmed away (before offset); 2 -> 4 + (2-1) = 5; 4 -> 7
    const c = clip({ start_sec: 4, offset_sec: 1, dur_sec: 4, downbeats_sec: [0, 2, 4] });
    expect(clipDownbeats(c, 120)).toEqual([5, 7]);
  });

  it("drops downbeats past the clip's end", () => {
    const c = clip({ start_sec: 0, offset_sec: 0, dur_sec: 3, downbeats_sec: [0, 2, 4] });
    expect(clipDownbeats(c, 120)).toEqual([0, 2]);
  });

  it("returns nothing when the clip was never analysed", () => {
    expect(clipDownbeats(clip({}), 120)).toEqual([]);
  });

  // C2 fix wave: downbeats_sec is SOURCE seconds at the clip's own native_bpm
  // (forge/types.ts), NOT the stretched timeline domain offset_sec/dur_sec live
  // in -- a consumer must scale by native_bpm/projectBpm first. Every fixture
  // above uses native_bpm: null (identity), which is exactly why this bug
  // shipped invisibly: none of them could ever have caught it.
  it("scales source-second downbeats by native_bpm/projectBpm before offsetting", () => {
    // Clip native 140 BPM placed in a 120 BPM project: stretched SLOWER, so
    // longer in time -- scale = 140/120. A raw downbeat at 2s (source) lands
    // at 2 * 140/120 = 7/3 s in the timeline, then the offset/start shift as usual.
    const c = clip({
      native_bpm: 140, start_sec: 0, offset_sec: 0, dur_sec: 10, downbeats_sec: [0, 2, 4],
    });
    const out = clipDownbeats(c, 120);
    expect(out[0]).toBeCloseTo(0, 9);
    expect(out[1]).toBeCloseTo((2 * 140) / 120, 9);
    expect(out[2]).toBeCloseTo((4 * 140) / 120, 9);
  });

  it("scale is applied BEFORE the offset/trim subtraction, not after", () => {
    // native 140 in a 120 project (scale 7/6). Raw downbeat at 1.5s scales to
    // 1.75s, THEN the 1s offset is subtracted -> 0.75s relative -> start_sec 4 -> 4.75.
    // Scaling AFTER (wrong order) would give (1.5 - 1) * 7/6 = 0.5833... + 4 = 4.5833,
    // a different, and wrong, answer -- this test fails under that ordering.
    const c = clip({
      native_bpm: 140, start_sec: 4, offset_sec: 1, dur_sec: 4, downbeats_sec: [1.5],
    });
    expect(clipDownbeats(c, 120)[0]).toBeCloseTo(4.75, 9);
  });
});

describe("lane downbeats gather every clip in one lane", () => {
  it("merges and sorts, ignoring other lanes", () => {
    const clips = [
      clip({ id: "a", lane: 1, start_sec: 4, downbeats_sec: [0, 2] }),
      clip({ id: "b", lane: 1, start_sec: 0, downbeats_sec: [0] }),
      clip({ id: "c", lane: 2, start_sec: 0, downbeats_sec: [1] }),
    ];
    expect(laneDownbeats(clips, 1, 120)).toEqual([0, 4, 6]);
  });
});

describe("coincidence within one 32nd note (spec 4.3)", () => {
  it("uses a 32nd of the project tempo as the tolerance", () => {
    expect(COINCIDENCE_DIVISION).toBe(32);
    // 120 BPM: whole note 2 s, so a 32nd is 0.0625 s
    expect(coincidenceToleranceSec(120)).toBeCloseTo(0.0625, 12);
    expect(coincidenceToleranceSec(60)).toBeCloseTo(0.125, 12);
  });

  it("is 1 on an exact hit and 0 well outside", () => {
    expect(coincidence(4.0, [4.0], 120)).toBe(1);
    expect(coincidence(4.0, [4.5], 120)).toBe(0);
  });

  it("ramps with the spec's 0.7 exponent, not linearly", () => {
    expect(COINCIDENCE_RAMP_EXP).toBe(0.7);
    // Half a 32nd away: linear would be 0.50; spec 4.3 is 0.5 ** 0.7.
    expect(coincidence(4.0, [4.03125], 120)).toBeCloseTo(0.6155722, 6);
  });

  it("is concave, so a near miss stays visible instead of fading out", () => {
    // Every point strictly inside the window sits ABOVE the linear ramp.
    for (const frac of [0.1, 0.25, 0.5, 0.75, 0.9]) {
      const dt = 0.0625 * frac;
      expect(coincidence(4.0, [4.0 + dt], 120)).toBeGreaterThan(1 - frac);
    }
  });

  it("takes the closest of several", () => {
    expect(coincidence(4.0, [4.5, 4.01, 9.0], 120)).toBeGreaterThan(0.8);
  });
});

describe("the marker colour ramps in OKLCH and builds its own string", () => {
  it("is the spec's dim endpoint at 0 and its hit endpoint at 1", () => {
    expect(downbeatColor(0)).toBe("oklch(78.00% 0.080 250.0)");
    expect(downbeatColor(1)).toBe("oklch(85.00% 0.170 95.0)");
  });

  it("interpolates every channel at the midpoint", () => {
    expect(downbeatColor(0.5)).toBe("oklch(81.50% 0.125 172.5)");
  });

  it("clamps out-of-range t rather than extrapolating", () => {
    expect(downbeatColor(-1)).toBe(downbeatColor(0));
    expect(downbeatColor(9)).toBe(downbeatColor(1));
  });

  it("emits oklch, never rgb -- a custom property is a token stream, not channels", () => {
    expect(downbeatColor(0.3).startsWith("oklch(")).toBe(true);
  });
});
