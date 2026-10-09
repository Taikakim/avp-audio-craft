import { describe, expect, it } from "vitest";
import {
  BASE_DEFAULTS, CHAIN_DEFAULTS, MASTER_DEFAULT, OVERLAP_DEFAULT,
} from "../defaults";
import {
  deepEqual, litModules, MODULE_ORDER, moduleTitle, type ModuleStateSnapshot,
} from "../nonDefault";

/** A structural clone that does not share a single nested object with the source. */
function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
}

const EMPTY: ModuleStateSnapshot = {
  overlap: null, chain: null, sampling: null, master: null,
};

describe("module order and titles (spec §4.6)", () => {
  it("is the spec's five modules in the spec's order", () => {
    expect(MODULE_ORDER).toEqual([
      "overlap", "files", "lane-chain", "advanced-sampling", "master-chain",
    ]);
  });

  it("gives the lane chain a header that follows the active lane", () => {
    expect(moduleTitle("lane-chain", 0)).toBe("LANE 1 CHAIN");
    expect(moduleTitle("lane-chain", 2)).toBe("LANE 3 CHAIN");
    expect(moduleTitle("files", 2)).toBe("FILES");
    expect(moduleTitle("overlap", 0)).toBe("OVERLAP — INPAINT");
    expect(moduleTitle("advanced-sampling", 3)).toBe("ADVANCED SAMPLING");
    expect(moduleTitle("master-chain", 3)).toBe("MASTER CHAIN");
  });
});

describe("deepEqual", () => {
  it("compares nested arrays and objects by value", () => {
    expect(deepEqual({ a: [1, 2, { b: 3 }] }, { a: [1, 2, { b: 3 }] })).toBe(true);
    expect(deepEqual({ a: [1, 2, { b: 3 }] }, { a: [1, 2, { b: 4 }] })).toBe(false);
    expect(deepEqual([1, 2], [1, 2, 3])).toBe(false);
    expect(deepEqual(null, null)).toBe(true);
    expect(deepEqual(null, {})).toBe(false);
    expect(deepEqual(1, "1")).toBe(false);
  });
});

describe("litModules with nothing loaded (the M1 state)", () => {
  it("lights nothing", () => {
    expect(litModules(EMPTY)).toEqual({
      "overlap": false, files: false, "lane-chain": false,
      "advanced-sampling": false, "master-chain": false,
    });
  });
});

describe("litModules lights a module exactly when its settings differ from the defaults", () => {
  it("leaves the lane chain dark at CHAIN_DEFAULTS and lights it on any change", () => {
    expect(litModules({ ...EMPTY, chain: clone(CHAIN_DEFAULTS) })["lane-chain"]).toBe(false);
    const latched = clone(CHAIN_DEFAULTS);
    latched.latch_on = true;
    expect(litModules({ ...EMPTY, chain: latched })["lane-chain"]).toBe(true);
  });

  it("sees a change nested two levels down", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.slots[0].weight = 2;
    expect(litModules({ ...EMPTY, chain })["lane-chain"]).toBe(true);
  });

  it("leaves the master chain dark at MASTER_DEFAULT and lights it on a noise change", () => {
    expect(litModules({ ...EMPTY, master: clone(MASTER_DEFAULT) })["master-chain"]).toBe(false);
    expect(litModules({ ...EMPTY, master: { ...MASTER_DEFAULT, noise: 0.8 } })["master-chain"]).toBe(true);
  });

  it("leaves the overlap dark at OVERLAP_DEFAULT and lights it on a steps change", () => {
    expect(litModules({ ...EMPTY, overlap: clone(OVERLAP_DEFAULT) })["overlap"]).toBe(false);
    const over = clone(OVERLAP_DEFAULT);
    over.steps = 40;
    expect(litModules({ ...EMPTY, overlap: over })["overlap"]).toBe(true);
  });

  it("compares ADVANCED SAMPLING on the schedule and the sampling fields only, never the prompt", () => {
    const withPrompt = clone(BASE_DEFAULTS);
    withPrompt.prompt = "dub techno, tape hiss";
    withPrompt.negative_prompt = "vocals";
    expect(litModules({ ...EMPTY, sampling: withPrompt })["advanced-sampling"]).toBe(false);

    const shaped = clone(BASE_DEFAULTS);
    shaped.schedule.shape = "logsnr";
    expect(litModules({ ...EMPTY, sampling: shaped })["advanced-sampling"]).toBe(true);

    const rescaled = clone(BASE_DEFAULTS);
    rescaled.scale_phi = 0.4;
    expect(litModules({ ...EMPTY, sampling: rescaled })["advanced-sampling"]).toBe(true);

    const banded = clone(BASE_DEFAULTS);
    banded.cfg_interval_progress = [0.2, 1];
    expect(litModules({ ...EMPTY, sampling: banded })["advanced-sampling"]).toBe(true);
  });

  it("never lights FILES — a root and a filter are navigation, not settings", () => {
    expect(litModules({ ...EMPTY, chain: clone(CHAIN_DEFAULTS) }).files).toBe(false);
  });
});
