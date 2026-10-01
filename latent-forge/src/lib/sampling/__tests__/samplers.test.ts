import { describe, expect, it } from "vitest";
import type { LatchSlot } from "../../forge/types";
import {
  activeSlots, isLatchActive, LATCH_FORCED_LABEL, LATCH_FORCED_SAMPLER, resolveSampler,
} from "../samplers";

function slot(over: Partial<LatchSlot> = {}): LatchSlot {
  return { head: "onsets", kind: "value", value: 0.5, weight: 1, start_pct: 0, end_pct: 1, ...over };
}

const OFF = { latch_on: false, slots: [] as LatchSlot[] };

describe("a slot counts as active only if it could do something", () => {
  it("needs the chain switched on", () => {
    expect(isLatchActive({ latch_on: false, slots: [slot()] })).toBe(false);
  });

  it("ignores a slot with no head", () => {
    expect(activeSlots({ latch_on: true, slots: [slot({ head: "" })] })).toEqual([]);
    expect(activeSlots({ latch_on: true, slots: [slot({ head: "none" })] })).toEqual([]);
  });

  it("ignores a slot with no weight", () => {
    expect(activeSlots({ latch_on: true, slots: [slot({ weight: 0 })] })).toEqual([]);
  });

  it("keeps a zero-width window — the server still forces Euler on it (5.5)", () => {
    const narrow = slot({ start_pct: 0.5, end_pct: 0.5 });
    expect(activeSlots({ latch_on: true, slots: [narrow] })).toHaveLength(1);
    expect(isLatchActive({ latch_on: true, slots: [narrow] })).toBe(true);
  });

  it("keeps a real one, by reference", () => {
    const s = slot();
    expect(activeSlots({ latch_on: true, slots: [s] })[0]).toBe(s);
    expect(isLatchActive({ latch_on: true, slots: [s] })).toBe(true);
  });
});

describe("samplers offered per objective (spec 5.3)", () => {
  it("offers the four RF samplers on rectified_flow", () => {
    expect(resolveSampler("rectified_flow", null, OFF).options).toEqual(
      ["euler", "rk4", "dpmpp", "pingpong"],
    );
  });

  it("offers only pingpong and euler on rf_denoiser", () => {
    expect(resolveSampler("rf_denoiser", null, OFF).options).toEqual(["pingpong", "euler"]);
  });

  it("falls back to the objective default when nothing is requested", () => {
    expect(resolveSampler("rectified_flow", null, OFF).value).toBe("euler");
    expect(resolveSampler("rf_denoiser", null, OFF).value).toBe("pingpong");
  });

  it("falls back when the requested sampler is not offered by this objective", () => {
    // dpmpp is an rf_denoiser impossibility; switching stage must not leave it selected
    expect(resolveSampler("rf_denoiser", "dpmpp", OFF).value).toBe("pingpong");
  });

  it("honours a requested sampler that is offered", () => {
    const c = resolveSampler("rectified_flow", "rk4", OFF);
    expect(c.value).toBe("rk4");
    expect(c.label).toBe("rk4");
    expect(c.disabled).toBe(false);
    expect(c.forced).toBe(false);
  });
});

describe("any active LatCH slot forces Euler (spec 5.3)", () => {
  const ON = { latch_on: true, slots: [slot()] };

  it("overrides the request, disables the select and says why", () => {
    const c = resolveSampler("rectified_flow", "dpmpp", ON);
    expect(c.value).toBe(LATCH_FORCED_SAMPLER);
    expect(c.value).toBe("euler");
    expect(c.label).toBe(LATCH_FORCED_LABEL);
    expect(c.disabled).toBe(true);
    expect(c.forced).toBe(true);
  });

  it("still forces on rf_denoiser, where euler is not the default", () => {
    expect(resolveSampler("rf_denoiser", null, ON).value).toBe("euler");
  });

  it("does not force when every slot is inert", () => {
    const inert = { latch_on: true, slots: [slot({ weight: 0 }), slot({ head: "none" })] };
    expect(resolveSampler("rectified_flow", "dpmpp", inert).forced).toBe(false);
    expect(resolveSampler("rectified_flow", "dpmpp", inert).value).toBe("dpmpp");
  });
});
