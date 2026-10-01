import { beforeEach, describe, expect, it } from "vitest";
import { BASE_DEFAULTS, POST_DEFAULTS, cloneRenderSettings } from "../../forge/defaults";
import type { RenderSettings, Target } from "../../forge/types";
import { SettingsStore, STAGE_BACKBONE, STAGE_FIELDS, STAGE_OBJECTIVE } from "../settings.svelte";

const CLIP: Target = { kind: "clip", id: "c1" };
const OVERLAP: Target = { kind: "overlap", key: "c1-c2" };
const NONE: Target = { kind: "none" };

/** Stand-in for M5's arrangement store: it owns the objects, we only resolve to them. */
function fakeSource() {
  const clips: Record<string, RenderSettings> = { c1: cloneRenderSettings(BASE_DEFAULTS) };
  const overlaps: Record<string, RenderSettings> = { "c1-c2": cloneRenderSettings(BASE_DEFAULTS) };
  return {
    clips,
    overlaps,
    clipSettings: (id: string) => clips[id] ?? null,
    overlapSettings: (key: string) => overlaps[key] ?? null,
  };
}

let s: SettingsStore;
beforeEach(() => {
  s = new SettingsStore();
});

describe("with nothing attached, every target is the session defaults", () => {
  it("resolves all three target kinds to the same object", () => {
    expect(s.current(NONE)).toBe(s.defaults);
    expect(s.current(CLIP)).toBe(s.defaults);
    expect(s.current(OVERLAP)).toBe(s.defaults);
  });

  it("says so, rather than pretending to edit a clip", () => {
    expect(s.scope(CLIP)).toBe("session");
    expect(s.scope(OVERLAP)).toBe("session");
    expect(s.scope(NONE)).toBe("session");
  });
});

describe("with a source attached, a target edits its own settings", () => {
  it("resolves a clip to the source's object, not a copy of it", () => {
    const src = fakeSource();
    s.attach(src);
    expect(s.current(CLIP)).toBe(src.clips.c1);
    expect(s.scope(CLIP)).toBe("clip");
    expect(s.current(OVERLAP)).toBe(src.overlaps["c1-c2"]);
    expect(s.scope(OVERLAP)).toBe("overlap");
  });

  it("falls back to the session defaults for a target the source does not know", () => {
    s.attach(fakeSource());
    expect(s.current({ kind: "clip", id: "gone" })).toBe(s.defaults);
    expect(s.scope({ kind: "clip", id: "gone" })).toBe("session");
  });

  it("writes through to the source's object and leaves the defaults alone", () => {
    const src = fakeSource();
    s.attach(src);
    s.patch(CLIP, { steps: 40 });
    s.patchSchedule(CLIP, { rho: 7 });
    expect(src.clips.c1.steps).toBe(40);
    expect(src.clips.c1.schedule.rho).toBe(7);
    expect(s.defaults.steps).toBe(BASE_DEFAULTS.steps);
    expect(s.defaults.schedule.rho).toBe(BASE_DEFAULTS.schedule.rho);
  });

  it("detaches back to the session defaults", () => {
    s.attach(fakeSource());
    s.detach();
    expect(s.current(CLIP)).toBe(s.defaults);
  });
});

describe("the model stage is session-level (spec 5.3, 10 X4)", () => {
  it("maps to a backbone id and an objective", () => {
    expect(STAGE_BACKBONE).toEqual({ POST: "medium", BASE: "medium-base" });
    expect(STAGE_OBJECTIVE).toEqual({ POST: "rf_denoiser", BASE: "rectified_flow" });
    expect(s.stage).toBe("BASE");
    expect(s.backboneId).toBe("medium-base");
    expect(s.objective).toBe("rectified_flow");
  });

  it("loads the stage's sampling defaults into the session defaults", () => {
    s.setStage("POST");
    expect(s.defaults.steps).toBe(POST_DEFAULTS.steps);
    expect(s.defaults.sampler_type).toBe(POST_DEFAULTS.sampler_type);
    expect(s.defaults.schedule.shape).toBe(POST_DEFAULTS.schedule.shape);
    // not lam_min: BASE and POST both hold -6.2, so it would pass on a store
    // that never loaded the schedule at all.
    expect(s.defaults.schedule).not.toBe(POST_DEFAULTS.schedule);
  });

  it("does NOT overwrite the prompt, the negative prompt or the seed", () => {
    s.defaults.prompt = "a slow marimba figure";
    s.defaults.negative_prompt = "drums";
    s.defaults.seed = 4242;
    s.setStage("POST");
    expect(s.defaults.prompt).toBe("a slow marimba figure");
    expect(s.defaults.negative_prompt).toBe("drums");
    expect(s.defaults.seed).toBe(4242);
  });

  it("names exactly the fields it overwrites", () => {
    expect([...STAGE_FIELDS].sort()).toEqual(["sampler_type", "schedule", "steps"]);
  });

  it("keeps existing per-target settings (spec 5.3)", () => {
    const src = fakeSource();
    s.attach(src);
    s.patch(CLIP, { steps: 40 });
    s.setStage("POST");
    expect(src.clips.c1.steps).toBe(40);
  });

  it("does not share a schedule object with the defaults table it loaded from", () => {
    s.setStage("POST");
    s.defaults.schedule.rho = 9;
    expect(POST_DEFAULTS.schedule.rho).toBe(1);
  });

  it("round-trips back to BASE without eating the CFG the user set", () => {
    s.defaults.cfg_scale = 9.0;
    s.setStage("POST");
    expect(s.defaults.cfg_scale).toBe(9.0);
    s.setStage("BASE");
    expect(s.defaults.steps).toBe(BASE_DEFAULTS.steps);
    expect(s.defaults.cfg_scale).toBe(9.0);
  });
});

describe("CFG is off in POST, but the stored value survives the trip", () => {
  it("reports cfg disabled only in POST", () => {
    expect(s.cfgDisabled).toBe(false);
    s.setStage("POST");
    expect(s.cfgDisabled).toBe(true);
  });

  it("sends 1.0 in POST without destroying the value the user set in BASE", () => {
    const src = fakeSource();
    s.attach(src);
    s.patch(CLIP, { cfg_scale: 9.5 });
    expect(s.effectiveCfg(CLIP)).toBe(9.5);
    s.setStage("POST");
    expect(s.effectiveCfg(CLIP)).toBe(1.0);
    expect(src.clips.c1.cfg_scale).toBe(9.5);
    s.setStage("BASE");
    expect(s.effectiveCfg(CLIP)).toBe(9.5);
    expect(s.defaults.cfg_scale).toBe(BASE_DEFAULTS.cfg_scale);
  });
});

describe("resetSampling", () => {
  it("restores the current stage's sampling fields and keeps the text", () => {
    const src = fakeSource();
    s.attach(src);
    s.patch(CLIP, { steps: 99, prompt: "kept" });
    s.patchSchedule(CLIP, { rho: 12 });
    s.resetSampling(CLIP);
    expect(src.clips.c1.steps).toBe(BASE_DEFAULTS.steps);
    expect(src.clips.c1.schedule.rho).toBe(BASE_DEFAULTS.schedule.rho);
    expect(src.clips.c1.prompt).toBe("kept");
  });

  it("gives the reset object its own schedule", () => {
    s.resetSampling(NONE);
    s.defaults.schedule.rho = 5;
    expect(BASE_DEFAULTS.schedule.rho).toBe(1.0);
  });
});
