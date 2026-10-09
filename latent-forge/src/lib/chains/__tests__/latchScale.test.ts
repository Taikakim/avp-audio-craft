import { describe, expect, it } from "vitest";
import type { LatchHeadInfo } from "../latch";
import type { LatchSlot } from "../../forge/types";
import {
  defaultGain, defaultRamp, effectiveGain, formatGain, isRamp, posToWeight, rampEnds, roundWeight,
  setRampFrom, setRampTo, targetReadout, targetScale, unitsOf, usableMaxWeight, weightReadout,
  weightToPos, WEIGHT_MAX, zScore,
} from "../latchScale";

// The three heads that matter: a dB head with a wide range, hardness with a narrow one, a chroma head.
const RMS: LatchHeadInfo = {
  name: "rms_energy_bass", family: "medium", default_gain: 512, health: "ok",
  supports_kinds: ["constant", "ramp_up", "ramp_down", "beat_grid"],
  slider_min: -35.2, slider_max: -0.13, value_default: -17.7, std_mean: -17.67, std_std: 8.77,
  usable_max_gain: 8192, usable_max_weight: 16,
};
const HARDNESS: LatchHeadInfo = {
  name: "hardness", family: "medium", default_gain: 512, health: "ok",
  supports_kinds: ["constant", "ramp_up", "ramp_down", "beat_grid"],
  slider_min: 59.2, slider_max: 73.2, value_default: 66.2, std_mean: 66.2, std_std: 3.5,
  usable_max_gain: 128, usable_max_weight: 0.25,
};
// what a server that predates the new /info fields sends
const OLD: LatchHeadInfo = {
  name: "rms_drums", family: "medium", default_gain: 512, health: "ok", supports_kinds: ["constant"],
  slider_min: -50, slider_max: 0, value_default: -25,
};

describe("weight: a cubic slider over 0..50", () => {
  it("round-trips the values that matter and is monotone", () => {
    for (const w of [0, 0.25, 1, 4, 16, 50]) expect(posToWeight(weightToPos(w))).toBe(w);
    let last = -1;
    for (let i = 0; i <= 1000; i++) {
      const w = posToWeight(i / 1000);
      expect(w).toBeGreaterThanOrEqual(last);
      last = w;
    }
    expect(posToWeight(0)).toBe(0);
    expect(posToWeight(1)).toBe(WEIGHT_MAX);
  });

  it("gives hardness's whole usable range (0..0.25) 17 % of the travel, where the linear slider gave it 0.5 %", () => {
    expect(weightToPos(0.25)).toBeCloseTo(0.171, 3);
    expect(weightToPos(1)).toBeCloseTo(0.271, 3);
    expect(weightToPos(16)).toBeCloseTo(0.684, 3);
    expect(0.25 / WEIGHT_MAX).toBeLessThan(0.006);            // the old position of the same weight
  });

  it("clamps outside 0..1 and rounds to what the slider can resolve", () => {
    expect(posToWeight(-1)).toBe(0);
    expect(posToWeight(2)).toBe(50);
    expect(roundWeight(0.126)).toBe(0.13);
    expect(roundWeight(12.34)).toBe(12.3);
    expect(weightToPos(-3)).toBe(0);
    expect(weightToPos(500)).toBe(1);
  });
});

describe("the head's clean limit and the strength a weight really applies", () => {
  it("reads usable_max_weight, or derives it from usable_max_gain, or knows nothing", () => {
    expect(usableMaxWeight(HARDNESS)).toBe(0.25);
    expect(usableMaxWeight({ ...HARDNESS, usable_max_weight: undefined })).toBe(0.25);   // 128 / 512
    expect(usableMaxWeight(OLD)).toBeNull();
    expect(usableMaxWeight(undefined)).toBeNull();
  });

  it("is max(rho, mu) x default gain x weight", () => {
    expect(defaultGain(RMS)).toBe(512);
    expect(defaultGain(undefined)).toBe(512);
    expect(effectiveGain(RMS, 1, { rho: 1, mu: 1 })).toBe(512);
    expect(effectiveGain(RMS, 2, { rho: 1, mu: 3 })).toBe(3072);
    expect(effectiveGain(HARDNESS, 0.25, { rho: 1, mu: 1 })).toBe(128);
  });

  it("warns when the strength passes the limit, and counts rho / mu as much as the weight", () => {
    expect(weightReadout(HARDNESS, 0.25, { rho: 1, mu: 1 })).toEqual({ text: "gain 128 · limit 128", warn: false });
    expect(weightReadout(HARDNESS, 1, { rho: 1, mu: 1 })).toEqual({ text: "gain 512 · past 128, breaks up", warn: true });
    expect(weightReadout(HARDNESS, 0.25, { rho: 4, mu: 1 }).warn).toBe(true);   // weight is fine, rho is not
    expect(weightReadout(RMS, 16, { rho: 1, mu: 1 }).warn).toBe(false);
  });

  it("shows only the gain when no limit is known", () => {
    expect(weightReadout(OLD, 1, { rho: 1, mu: 1 })).toEqual({ text: "gain 512", warn: false });
    expect(weightReadout(undefined, 2, { rho: 1, mu: 1 })).toEqual({ text: "gain 1024", warn: false });
    expect(formatGain(12.34)).toBe("12.3");
    expect(formatGain(511.6)).toBe("512");
  });
});

describe("target: unit, scale and where the value sits in the head's data", () => {
  it("names the unit: the server's, else dB for rms, bpm for a beat grid, nothing otherwise", () => {
    expect(unitsOf(RMS, "constant")).toBe("dB");
    expect(unitsOf({ ...HARDNESS, units: "" }, "constant")).toBe("");
    expect(unitsOf({ ...RMS, units: "dBFS" }, "constant")).toBe("dBFS");
    expect(unitsOf(HARDNESS, "constant")).toBe("");
    expect(unitsOf(RMS, "beat_grid")).toBe("bpm");
    expect(unitsOf(undefined, "constant")).toBe("");
  });

  it("spans the head's own range with a power-of-ten step, 60..200 for a beat grid", () => {
    expect(targetScale(RMS, "constant")).toEqual({ min: -35.2, max: -0.13, step: 0.1, decimals: 1 });
    expect(targetScale(HARDNESS, "ramp_up")).toEqual({ min: 59.2, max: 73.2, step: 0.1, decimals: 1 });
    expect(targetScale({ ...RMS, slider_min: 0, slider_max: 1 }, "constant")).toEqual({ min: 0, max: 1, step: 0.01, decimals: 2 });
    expect(targetScale(RMS, "beat_grid")).toEqual({ min: 60, max: 200, step: 1, decimals: 0 });
    expect(targetScale(undefined, "constant")).toEqual({ min: 0, max: 1, step: 0.01, decimals: 2 });
  });

  it("measures a target in standard deviations from the head's mean", () => {
    expect(zScore(66.2, HARDNESS, "constant")).toBeCloseTo(0, 6);
    expect(zScore(69.7, HARDNESS, "constant")).toBeCloseTo(1, 6);
    expect(zScore(0, HARDNESS, "constant")).toBeCloseTo(-18.9, 1);       // the sampler's ramp start for hardness
    expect(zScore(66, OLD, "constant")).toBeNull();
    expect(zScore(120, HARDNESS, "beat_grid")).toBeNull();
    expect(zScore(1, { ...HARDNESS, std_std: 0 }, "constant")).toBeNull();
  });

  it("reads out the distance, and warns past 3 sigma", () => {
    expect(targetReadout(69.7, HARDNESS, "constant")).toEqual({ text: "+1.0σ", warn: false });
    expect(targetReadout(62.7, HARDNESS, "constant")).toEqual({ text: "−1.0σ", warn: false });
    const far = targetReadout(0, HARDNESS, "constant");
    expect(far?.warn).toBe(true);
    expect(far?.text).toContain("outside the trained range");
    expect(targetReadout(5, OLD, "constant")).toBeNull();
  });
});

describe("ramps have two ends, inside the head's range", () => {
  const slot = (o: Partial<LatchSlot>): LatchSlot => ({
    head: "hardness", kind: "ramp_up", value: 66.2, weight: 0.25, start_pct: 0, end_pct: 0.6, ...o,
  });

  it("knows which kinds are ramps", () => {
    expect(isRamp("ramp_up") && isRamp("ramp_down")).toBe(true);
    expect(isRamp("constant") || isRamp("beat_grid")).toBe(false);
  });

  it("shows an old slot as the sampler's own 0 -> value / value -> 0 ramp, so nothing changes until a field is touched", () => {
    expect(rampEnds(slot({ kind: "ramp_up" }))).toEqual({ from: 0, to: 66.2 });
    expect(rampEnds(slot({ kind: "ramp_down" }))).toEqual({ from: 66.2, to: 0 });
    expect(rampEnds(slot({ value_from: null }))).toEqual({ from: 0, to: 66.2 });
  });

  it("an explicit start is the start, whichever direction", () => {
    expect(rampEnds(slot({ value_from: 62.7, value: 69.7 }))).toEqual({ from: 62.7, to: 69.7 });
    expect(rampEnds(slot({ kind: "ramp_down", value_from: 69.7, value: 62.7 }))).toEqual({ from: 69.7, to: 62.7 });
  });

  it("editing the start keeps the end, and an old ramp_down keeps its meaning (value -> 0 becomes 0's replacement)", () => {
    const up = slot({});
    setRampFrom(up, 62.7);
    expect(up).toMatchObject({ value_from: 62.7, value: 66.2 });
    const down = slot({ kind: "ramp_down" });          // old meaning: 66.2 -> 0
    setRampFrom(down, 69.7);
    expect(down).toMatchObject({ value_from: 69.7, value: 0 });   // the end it had (0) is kept, the start is what was typed
  });

  it("editing the end keeps the start", () => {
    const up = slot({});                                // old meaning: 0 -> 66.2
    setRampTo(up, 69.7);
    expect(up).toMatchObject({ value_from: 0, value: 69.7 });
    const down = slot({ kind: "ramp_down" });          // old meaning: 66.2 -> 0
    setRampTo(down, 59.2);
    expect(down).toMatchObject({ value_from: 66.2, value: 59.2 });
  });

  it("a fresh ramp spans the middle half of the head's range, rising for up and falling for down", () => {
    expect(defaultRamp(HARDNESS, "ramp_up")).toEqual({ from: 62.7, to: 69.7 });
    expect(defaultRamp(HARDNESS, "ramp_down")).toEqual({ from: 69.7, to: 62.7 });
    const r = defaultRamp(RMS, "ramp_up");
    expect(r && r.from < r.to).toBe(true);
    expect(defaultRamp(HARDNESS, "constant")).toBeNull();
    expect(defaultRamp(undefined, "ramp_up")).toBeNull();
  });

  it("the default ramp is within 1 sigma of the mean for hardness -- not 19 sigma out like 0 -> value", () => {
    const r = defaultRamp(HARDNESS, "ramp_up");
    expect(r).not.toBeNull();
    for (const v of [r!.from, r!.to]) expect(Math.abs(zScore(v, HARDNESS, "ramp_up")!)).toBeLessThanOrEqual(1.01);
  });
});
