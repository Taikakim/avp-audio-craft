import { beforeEach, describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../forge/defaults";
import type { RenderSettings } from "../../forge/types";
import {
  applyPromptPreset, applyRenderPreset, isValidPresetName, PROMPT_GROUP_LABEL,
  presetOptions, promptPresetBody, RENDER_GROUP_LABEL, renderPresetBody, SEED_SENTINEL,
} from "../renderPresets";

let s: RenderSettings;
beforeEach(() => {
  s = cloneRenderSettings(BASE_DEFAULTS);
});

describe("the two levels share one select (4.5, 9.3)", () => {
  it("lists render presets first, then prompt presets under their own group", () => {
    expect(presetOptions(["warm pad"], ["bright"])).toEqual([
      { level: "render", name: "warm pad", group: RENDER_GROUP_LABEL },
      { level: "prompt", name: "bright", group: PROMPT_GROUP_LABEL },
    ]);
    expect(PROMPT_GROUP_LABEL).toBe("prompt only");
  });

  it("copes with either level being empty", () => {
    expect(presetOptions([], [])).toEqual([]);
    expect(presetOptions(["a"], [])).toHaveLength(1);
    expect(presetOptions([], ["a"])).toHaveLength(1);
  });

  it("keeps the server's order rather than sorting", () => {
    expect(presetOptions(["z", "a"], []).map((o) => o.name)).toEqual(["z", "a"]);
  });
});

describe("preset names are filenames", () => {
  it("accepts the same shape 6.3 gives session names", () => {
    expect(isValidPresetName("warm-pad_2.v1")).toBe(true);
  });

  it("rejects anything that could escape the presets directory", () => {
    expect(isValidPresetName("../secrets")).toBe(false);
    expect(isValidPresetName("a/b")).toBe(false);
    expect(isValidPresetName("")).toBe(false);
    expect(isValidPresetName("x".repeat(81))).toBe(false);
    expect(isValidPresetName("has space")).toBe(false);
  });
});

describe("what gets saved", () => {
  it("a render preset is the whole RenderSettings, deep-copied", () => {
    const body = renderPresetBody(s);
    expect(body).toEqual(s);
    expect(body).not.toBe(s);
    expect(body.schedule).not.toBe(s.schedule);
    expect(body.cfg_interval_progress).not.toBe(s.cfg_interval_progress);
  });

  it("a prompt preset is only the two text fields (9.3)", () => {
    s.prompt = "p";
    s.negative_prompt = "n";
    expect(promptPresetBody(s)).toEqual({ prompt: "p", negative_prompt: "n" });
  });
});

describe("applyPromptPreset", () => {
  it("replaces only the two text fields", () => {
    s.steps = 40;
    const r = applyPromptPreset(s, { prompt: "new", negative_prompt: "no" });
    expect(s.prompt).toBe("new");
    expect(s.negative_prompt).toBe("no");
    expect(s.steps).toBe(40);
    expect(r).toEqual({ applied: ["prompt", "negative_prompt"], rejected: [] });
  });

  it("takes a prompt without a negative prompt", () => {
    const r = applyPromptPreset(s, { prompt: "new" });
    expect(s.prompt).toBe("new");
    expect(r.applied).toEqual(["prompt"]);
  });

  it("rejects a non-string and leaves the field alone", () => {
    s.prompt = "kept";
    const r = applyPromptPreset(s, { prompt: 7 });
    expect(s.prompt).toBe("kept");
    expect(r.rejected).toEqual(["prompt"]);
  });

  it("survives a body that is not an object at all", () => {
    expect(applyRenderPreset(s, null)).toEqual({ applied: [], rejected: ["<body>"] });
    expect(applyPromptPreset(s, "nope")).toEqual({ applied: [], rejected: ["<body>"] });
    expect(applyPromptPreset(s, [1, 2])).toEqual({ applied: [], rejected: ["<body>"] });
    expect(s.prompt).toBe(BASE_DEFAULTS.prompt);
  });
});

describe("applyRenderPreset validates every field before it lands", () => {
  it("applies a complete, valid preset", () => {
    // A round trip of the app's own defaults, seed sentinel and all: `rejected` must be
    // empty, or saving and recalling an untouched target reads as corrupt.
    const body = renderPresetBody(cloneRenderSettings(BASE_DEFAULTS));
    body.steps = 40;
    body.cfg_scale = 9;
    body.schedule.shape = "geometric";
    body.schedule.rho = 3;
    const r = applyRenderPreset(s, body);
    expect(s.steps).toBe(40);
    expect(s.cfg_scale).toBe(9);
    expect(s.schedule.shape).toBe("geometric");
    expect(s.schedule.rho).toBe(3);
    expect(r.rejected).toEqual([]);
  });

  it("does not share the preset's schedule object with the settings it wrote into", () => {
    const body = renderPresetBody(cloneRenderSettings(BASE_DEFAULTS));
    applyRenderPreset(s, body);
    s.schedule.rho = 11;
    expect(body.schedule.rho).toBe(BASE_DEFAULTS.schedule.rho);
  });

  it("rejects an out-of-range number and keeps the old value", () => {
    s.steps = 24;
    const r = applyRenderPreset(s, { steps: 9000 });
    expect(s.steps).toBe(24);
    expect(r.rejected).toEqual(["steps"]);
  });

  it("rejects a non-integer where the range says int", () => {
    const r = applyRenderPreset(s, { steps: 24.5 });
    expect(r.rejected).toEqual(["steps"]);
  });

  it("rejects a string where a number belongs", () => {
    const r = applyRenderPreset(s, { cfg_scale: "loud" });
    expect(s.cfg_scale).toBe(BASE_DEFAULTS.cfg_scale);
    expect(r.rejected).toEqual(["cfg_scale"]);
  });

  it("rejects an unknown schedule shape", () => {
    const r = applyRenderPreset(s, { schedule: { shape: "karras" } });
    expect(s.schedule.shape).toBe(BASE_DEFAULTS.schedule.shape);
    expect(r.rejected).toEqual(["schedule.shape"]);
  });

  it("applies the good fields of a partly bad preset and names the bad ones", () => {
    const r = applyRenderPreset(s, { steps: 40, cfg_scale: 999, prompt: "ok" });
    expect(s.steps).toBe(40);
    expect(s.prompt).toBe("ok");
    expect(s.cfg_scale).toBe(BASE_DEFAULTS.cfg_scale);
    expect(r.applied).toContain("steps");
    expect(r.applied).toContain("prompt");
    expect(r.rejected).toEqual(["cfg_scale"]);
  });

  it("ignores keys that are not RenderSettings fields", () => {
    const r = applyRenderPreset(s, { steps: 40, nonsense: 1, __proto__: { polluted: true } });
    expect(r.applied).toEqual(["steps"]);
    expect(r.rejected).toEqual([]);
    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });

  it("takes the cfg interval only as an ordered pair in range", () => {
    expect(applyRenderPreset(s, { cfg_interval_progress: [0.2, 0.8] }).applied)
      .toEqual(["cfg_interval_progress"]);
    expect(s.cfg_interval_progress).toEqual([0.2, 0.8]);
    expect(applyRenderPreset(s, { cfg_interval_progress: [0.8, 0.2] }).rejected)
      .toEqual(["cfg_interval_progress"]);
    expect(applyRenderPreset(s, { cfg_interval_progress: [0, 2] }).rejected)
      .toEqual(["cfg_interval_progress"]);
    expect(applyRenderPreset(s, { cfg_interval_progress: [0.1] }).rejected)
      .toEqual(["cfg_interval_progress"]);
    expect(s.cfg_interval_progress).toEqual([0.2, 0.8]);
  });

  it("takes sampler_type as a string or null, nothing else", () => {
    expect(applyRenderPreset(s, { sampler_type: "rk4" }).applied).toEqual(["sampler_type"]);
    expect(s.sampler_type).toBe("rk4");
    expect(applyRenderPreset(s, { sampler_type: null }).applied).toEqual(["sampler_type"]);
    expect(s.sampler_type).toBeNull();
    expect(applyRenderPreset(s, { sampler_type: 3 }).rejected).toEqual(["sampler_type"]);
  });

  it("takes stepped only as a boolean", () => {
    expect(applyRenderPreset(s, { schedule: { stepped: true } }).applied)
      .toEqual(["schedule.stepped"]);
    expect(s.schedule.stepped).toBe(true);
    expect(applyRenderPreset(s, { schedule: { stepped: "yes" } }).rejected)
      .toEqual(["schedule.stepped"]);
  });

  it("does not require a seed to be present, but validates one that is", () => {
    expect(applyRenderPreset(s, {}).applied).toEqual([]);
    expect(applyRenderPreset(s, { seed: -5 }).rejected).toEqual(["seed"]);
    expect(applyRenderPreset(s, { seed: 12 }).applied).toEqual(["seed"]);
    // -1 is M1's server-resolve sentinel and the value the app's own defaults carry.
    expect(applyRenderPreset(s, { seed: SEED_SENTINEL }).applied).toEqual(["seed"]);
    expect(s.seed).toBe(SEED_SENTINEL);
  });
});
