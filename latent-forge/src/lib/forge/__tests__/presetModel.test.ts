import { afterEach, describe, expect, it, vi } from "vitest";
import { MASTER_DEFAULT } from "../defaults";
import { arrangement } from "../../stores/arrangement.svelte";
import { settings } from "../../stores/settings.svelte";
import { buildMasterPresetPayload, validateMasterPreset } from "../projectSerializer.svelte";
import { confirmText, describeModel, modelChanges, type PresetModel } from "../presetModel";
import { SessionController, type SessionDeps } from "../sessionController.svelte";

// Shape written by eval/forge/make_dj_mix_presets.py: model + render + source, no layout.
const DJ: Record<string, unknown> = {
  model: { backbone: "medium", ckpt_path: "/r/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt",
           family: "adapter", strength: 1.0, weights: null },
  render: { prompt: "mid 90s goa trance, techno, space dark mood, 140 bpm", seed: 278158216,
            cfg_scale: 1.0, steps: 8, duration_sec: 47.55 },
  source: { mix: "v7", position: 1 },
};

describe("presetModel", () => {
  it("names only what differs", () => {
    const want: PresetModel = { backbone: "medium", ckpt_path: "/a/run/x.ckpt" };
    expect(modelChanges(want, { backbone: "medium", ckpt_path: "/a/run/x.ckpt" })).toEqual([]);
    expect(modelChanges(want, { backbone: "medium-base", ckpt_path: "/a/run/x.ckpt" })).toEqual(["backbone"]);
    expect(modelChanges(want, { backbone: "medium", ckpt_path: null })).toEqual(["checkpoint"]);
    // A preset with no backbone (a server recipe) never asks for a backbone switch.
    expect(modelChanges({ backbone: null, ckpt_path: null }, { backbone: "medium", ckpt_path: null })).toEqual([]);
  });

  it("describes a model by run dir and file, and the question names both sides", () => {
    expect(describeModel({ backbone: "medium", ckpt_path: "/a/b/run7/epoch=7.ckpt" })).toBe("medium + run7 / epoch=7.ckpt");
    expect(describeModel({ backbone: "medium-base", ckpt_path: null })).toBe("medium-base, no adapter");
    const t = confirmText({ backbone: "medium", ckpt_path: "/a/run7/e.ckpt" }, { backbone: "medium-base", ckpt_path: null }, "dj-v7-01");
    expect(t).toContain("dj-v7-01");
    expect(t).toContain("medium + run7 / e.ckpt");
    expect(t).toContain("medium-base, no adapter");
  });
});

describe("partial master presets (2026-10-13)", () => {
  afterEach(() => {
    arrangement.master = { ...MASTER_DEFAULT };
  });

  it("accepts a model+render preset and refuses an empty or mistyped one", () => {
    expect(() => validateMasterPreset(DJ)).not.toThrow();
    expect(() => validateMasterPreset({ source: {} })).toThrow(/every field/);
    expect(() => validateMasterPreset({ ...DJ, model: 5 })).toThrow(/model/);
  });

  it("SAVE records the loaded model", () => {
    settings.activeBackbone = "medium-base";
    settings.ckptPath = "/x/y.ckpt";
    expect(buildMasterPresetPayload().model).toEqual({ backbone: "medium-base", ckpt_path: "/x/y.ckpt" });
  });

  it("recall asks for the model FIRST, then sets the session defaults and leaves the arrangement alone", async () => {
    const order: string[] = [];
    arrangement.master = { ...MASTER_DEFAULT, noise: 42 };
    const deps: SessionDeps = {
      api: {
        session: vi.fn(), saveSession: vi.fn(), setBackbone: vi.fn(),
        preset: vi.fn(async () => {
          order.push("fetch");
          return structuredClone(DJ);
        }),
        savePreset: vi.fn(),
      },
      log: vi.fn(), prompt: vi.fn(() => null), confirm: vi.fn(() => true), exists: vi.fn(() => false),
      scheduleStretch: vi.fn(),
      ensureModel: vi.fn(async (m: PresetModel) => {
        order.push(`model:${m.backbone}`);
        expect(settings.defaults.steps).not.toBe(8);   // render settings not applied yet
      }),
    };
    const ok = await new SessionController(deps).recallMasterPreset("dj-v7-01");
    expect(ok).toBe(true);
    expect(order).toEqual(["fetch", "model:medium"]);
    expect(settings.defaults.prompt).toBe("mid 90s goa trance, techno, space dark mood, 140 bpm");
    expect(settings.defaults.steps).toBe(8);
    expect(settings.defaults.cfg_scale).toBe(1.0);
    expect(settings.defaults.seed).toBe(278158216);
    expect(settings.defaults.duration_sec).toBe(47.55);
    expect(arrangement.master.noise).toBe(42);
  });
});
