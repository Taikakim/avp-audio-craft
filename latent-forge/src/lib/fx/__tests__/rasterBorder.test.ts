// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Progress } from "../../forge/types";
import { PALETTES } from "../phosphor-border.js";
import { RASTER_CONFIG, SWEEP_END, SWEEP_START, createRasterDriver, sweepHzFor } from "../rasterBorder";

const HERE = dirname(fileURLToPath(import.meta.url));
const HANDOFF = resolve(HERE, "../../../../../docs/sa3-studio/design_handoff/phosphor-border.js");
const COPY = resolve(HERE, "../phosphor-border.js");

function progress(patch: Partial<Progress> = {}): Progress {
  return {
    job_id: "forge-1", op: "commit", stage: "", stage_index: 0, stage_count: 0,
    step: 0, steps: 0, steps_left_total: 24, steps_total: 24, ...patch,
  };
}

/** A canvas whose getContext is a no-op: jsdom has no 2d context, and this task's unit is the
 *  DRIVER, not the simulation. createPhosphorBorder itself is stubbed per test. */
function canvas(width = 300, height = 170): HTMLCanvasElement {
  const el = document.createElement("canvas");
  el.width = width;
  el.height = height;
  return el;
}

afterEach(() => vi.restoreAllMocks());

describe("the copied module", () => {
  it("is byte-identical to the design handoff (spec §9.5: copied verbatim)", () => {
    expect(readFileSync(COPY, "utf8")).toBe(readFileSync(HANDOFF, "utf8"));
  });

  it("exports PALETTES whose values are ARRAYS of hex strings -- `palette: \"teal\"` would paint NaN", () => {
    expect(Array.isArray(PALETTES.teal)).toBe(true);
    expect(PALETTES.teal.length).toBeGreaterThan(1);
    for (const c of PALETTES.teal) expect(c).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("RASTER_CONFIG -- spec §9.5's settled config, corrected for the module's real API", () => {
  it("passes the palette ARRAY, alphaOut true, and every other settled value", () => {
    expect(RASTER_CONFIG).toEqual({
      thickness: 4, linesPerColour: 3, jitter: 0.59, persistence: 0.002, chromaBleed: 1.5,
      supersample: 8, gain: 0.8, spotSpread: 0.16, palette: PALETTES.teal, alphaOut: true,
      sweepHz: SWEEP_START,
    });
  });

  it("carries no sweepStart/sweepEnd -- set() would accept and then ignore them", () => {
    expect("sweepStart" in RASTER_CONFIG).toBe(false);
    expect("sweepEnd" in RASTER_CONFIG).toBe(false);
    expect([SWEEP_START, SWEEP_END]).toEqual([95, 0]);
  });
});

describe("sweepHzFor", () => {
  it("is sweepStart at no progress and sweepEnd at the last step", () => {
    expect(sweepHzFor(progress({ steps_left_total: 24, steps_total: 24 }))).toBe(SWEEP_START);
    expect(sweepHzFor(progress({ steps_left_total: 0, steps_total: 24 }))).toBe(SWEEP_END);
  });

  it("ramps linearly in between -- spec §9.5's sweepStart + (sweepEnd − sweepStart)·(1 − left/total)", () => {
    expect(sweepHzFor(progress({ steps_left_total: 12, steps_total: 24 }))).toBeCloseTo(47.5, 6);
    expect(sweepHzFor(progress({ steps_left_total: 6, steps_total: 24 }))).toBeCloseTo(23.75, 6);
  });

  it("returns sweepStart, never NaN, when steps_total is 0 (Fact 5: commit with no passes, decode, bend)", () => {
    const hz = sweepHzFor(progress({ steps_left_total: 0, steps_total: 0 }));
    expect(Number.isFinite(hz)).toBe(true);
    expect(hz).toBe(SWEEP_START);
  });

  it("returns sweepStart for a job with no progress yet", () => {
    expect(sweepHzFor(null)).toBe(SWEEP_START);
  });

  it("clamps a left count outside 0..total instead of sweeping backwards", () => {
    expect(sweepHzFor(progress({ steps_left_total: 99, steps_total: 24 }))).toBe(SWEEP_START);
    expect(sweepHzFor(progress({ steps_left_total: -3, steps_total: 24 }))).toBe(SWEEP_END);
  });
});

describe("createRasterDriver", () => {
  function stubFx() {
    const fx = { start: vi.fn(), stop: vi.fn(), set: vi.fn(), resize: vi.fn(), destroy: vi.fn() };
    const create = vi.fn((_canvas: unknown, _opts: unknown) => fx);
    return { fx, create };
  }

  it("creates and starts the effect on the first active job, and only once", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.update(progress({ steps_left_total: 20 }));
    expect(create).toHaveBeenCalledTimes(1);
    expect(fx.start).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][1]).toMatchObject({ alphaOut: true, palette: PALETTES.teal });
  });

  it("writes sweepHz on every tick and nothing else", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress({ steps_left_total: 24, steps_total: 24 }));
    d.update(progress({ steps_left_total: 12, steps_total: 24 }));
    expect(fx.set).toHaveBeenLastCalledWith({ sweepHz: 47.5 });
    for (const call of fx.set.mock.calls) expect(Object.keys(call[0])).toEqual(["sweepHz"]);
  });

  it("stops AND destroys when the job ends, so no rAF loop survives an idle app", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.update(null);
    expect(fx.destroy).toHaveBeenCalledTimes(1);
    d.update(null);
    expect(fx.destroy).toHaveBeenCalledTimes(1);
  });

  it("calls destroy as a METHOD on the handle -- the module's destroy() uses `this.stop()`", () => {
    let receiver: unknown = null;
    const fx = {
      start: vi.fn(), stop: vi.fn(), set: vi.fn(), resize: vi.fn(),
      destroy(this: unknown) { receiver = this; },
    };
    const d = createRasterDriver(canvas(), vi.fn((_canvas: unknown, _opts: unknown) => fx));
    d.update(progress());
    d.update(null);
    expect(receiver).toBe(fx);
  });

  it("starts a fresh effect for the next job after a destroy", () => {
    const { create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.update(null);
    d.update(progress());
    expect(create).toHaveBeenCalledTimes(2);
  });

  it("never builds an effect on a zero-sized canvas -- buildRing() bails and step() then throws", () => {
    const { create } = stubFx();
    const d = createRasterDriver(canvas(0, 0), create);
    d.update(progress());
    expect(create).not.toHaveBeenCalled();
  });

  it("stop() tears down whatever is live and is safe to call twice", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.stop();
    d.stop();
    expect(fx.destroy).toHaveBeenCalledTimes(1);
  });
});
