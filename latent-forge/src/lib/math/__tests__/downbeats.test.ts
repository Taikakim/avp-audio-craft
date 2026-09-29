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
    expect(clipDownbeats(c)).toEqual([5, 7]);
  });

  it("drops downbeats past the clip's end", () => {
    const c = clip({ start_sec: 0, offset_sec: 0, dur_sec: 3, downbeats_sec: [0, 2, 4] });
    expect(clipDownbeats(c)).toEqual([0, 2]);
  });

  it("returns nothing when the clip was never analysed", () => {
    expect(clipDownbeats(clip({}))).toEqual([]);
  });
});

describe("lane downbeats gather every clip in one lane", () => {
  it("merges and sorts, ignoring other lanes", () => {
    const clips = [
      clip({ id: "a", lane: 1, start_sec: 4, downbeats_sec: [0, 2] }),
      clip({ id: "b", lane: 1, start_sec: 0, downbeats_sec: [0] }),
      clip({ id: "c", lane: 2, start_sec: 0, downbeats_sec: [1] }),
    ];
    expect(laneDownbeats(clips, 1)).toEqual([0, 4, 6]);
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
