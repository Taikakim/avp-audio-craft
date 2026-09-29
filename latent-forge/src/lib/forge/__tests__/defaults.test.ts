import { describe, expect, it } from "vitest";
import {
  A2A_ENVELOPE_DEFAULT, BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings,
  ENVELOPE_DEFAULT, LENGTH_CAP_SEC, MASTER_DEFAULT, MIX_DEFAULT, OVERLAP_DEFAULT,
  POST_DEFAULTS, SAMPLERS_BY_OBJECTIVE, SCHEDULE_DEFAULT,
} from "../defaults";

describe("BASE defaults are the server's validated defaults (spec §5.3)", () => {
  it("is 24 steps, cfg 6, euler, model shape, full cfg interval", () => {
    expect(BASE_DEFAULTS.steps).toBe(24);
    expect(BASE_DEFAULTS.cfg_scale).toBe(6.0);
    expect(BASE_DEFAULTS.sampler_type).toBe("euler");
    expect(BASE_DEFAULTS.duration_sec).toBeCloseTo(47.556, 3);
    expect(BASE_DEFAULTS.schedule.shape).toBe("model");
    expect(BASE_DEFAULTS.cfg_interval_progress).toEqual([0, 1]);
  });
});

describe("POST defaults (spec §5.3)", () => {
  it("is 8 steps, pingpong, logsnr lam[-6.2, 2.0], rho 1, cfg disabled as 1.0", () => {
    expect(POST_DEFAULTS.steps).toBe(8);
    expect(POST_DEFAULTS.sampler_type).toBe("pingpong");
    expect(POST_DEFAULTS.duration_sec).toBeCloseTo(47.556, 3);
    expect(POST_DEFAULTS.schedule.shape).toBe("logsnr");
    expect(POST_DEFAULTS.schedule.lam_min).toBe(-6.2);
    expect(POST_DEFAULTS.schedule.lam_max).toBe(2.0);
    expect(POST_DEFAULTS.schedule.rho).toBe(1);
    expect(POST_DEFAULTS.cfg_scale).toBe(1.0);
  });
});

describe("ScheduleSpec defaults (spec §5.3)", () => {
  it("matches the spec block field for field", () => {
    expect(SCHEDULE_DEFAULT).toEqual({
      shape: "model", rho: 1.0, sigma_min: 0.01,
      lam_min: -6.2, lam_max: 2.0, stepped: false, plateaus: 6, tilt: 0.15,
    });
  });
});

describe("envelopes (spec §5.2)", () => {
  it("crossfade curve default is [0, 0.35, 0.7, 1] with flat curves", () => {
    expect(ENVELOPE_DEFAULT).toEqual({ points: [0, 0.35, 0.7, 1], curves: [0, 0, 0] });
  });

  it("a2a noise envelope default is flat 0.4", () => {
    expect(A2A_ENVELOPE_DEFAULT).toEqual({ points: [0.4, 0.4, 0.4, 0.4], curves: [0, 0, 0] });
  });
});

describe("overlap defaults (spec §7.2)", () => {
  it("is chroma on, override off, 28 steps, cfg 3.0", () => {
    expect(OVERLAP_DEFAULT.chroma_xfade).toBe(true);
    expect(OVERLAP_DEFAULT.override).toBe(false);
    expect(OVERLAP_DEFAULT.steps).toBe(28);
    expect(OVERLAP_DEFAULT.cfg).toBe(3.0);
    expect(OVERLAP_DEFAULT.curve).toEqual(ENVELOPE_DEFAULT);
  });
});

describe("lane chain defaults (spec §5.5)", () => {
  it("has two off slots, weight 1, start 0 end 0.6, and the shared hparams", () => {
    expect(CHAIN_DEFAULTS.latch_on).toBe(false);
    expect(CHAIN_DEFAULTS.slots).toHaveLength(2);
    expect(CHAIN_DEFAULTS.slots[0].weight).toBe(1);
    expect(CHAIN_DEFAULTS.slots[0].start_pct).toBe(0);
    expect(CHAIN_DEFAULTS.slots[0].end_pct).toBe(0.6);
    expect(CHAIN_DEFAULTS.hparams).toEqual({ rho: 1, mu: 1, gamma: 0.3, n_iter: 4, log_norms: false });
  });

  it("defaults FiLM target to 4.0 onsets/s, FiLM gain to the server's 1.75, and master gain to 64 (spec §4.6, §5.5)", () => {
    expect(CHAIN_DEFAULTS.film.value).toBe(4.0);
    expect(CHAIN_DEFAULTS.film.gain).toBe(1.75);   // = /info.film_default.gain (FILM_DEFAULT_GAIN)
    expect(MASTER_DEFAULT.gain).toBe(64);
    expect(MASTER_DEFAULT.norm_on).toBe(true);
  });
});

describe("mix defaults (spec §4.5)", () => {
  it("is the tree order with all nodes at slerp t=0.5", () => {
    expect(MIX_DEFAULT.order).toBe("tree");
    expect(MIX_DEFAULT.nodes.MX).toEqual({ interp: "slerp", t: 0.5 });
    expect(MIX_DEFAULT.quad_weights).toEqual([1, 1, 1, 1]);
  });
});

describe("hard limits", () => {
  it("caps forge passes at 184 s (spec §2.2, X12)", () => {
    expect(LENGTH_CAP_SEC).toBe(184);
  });

  it("offers RF samplers only, and rf_denoiser gets the shorter list (spec §5.3, X5)", () => {
    expect(SAMPLERS_BY_OBJECTIVE.rectified_flow).toEqual(["euler", "rk4", "dpmpp", "pingpong"]);
    expect(SAMPLERS_BY_OBJECTIVE.rf_denoiser).toEqual(["pingpong", "euler"]);
  });
});

describe("cloneRenderSettings is deep", () => {
  it("does not share the schedule or the cfg interval with its source", () => {
    const a = cloneRenderSettings(BASE_DEFAULTS);
    a.schedule.rho = 9;
    a.cfg_interval_progress[0] = 0.5;
    expect(BASE_DEFAULTS.schedule.rho).toBe(1.0);
    expect(BASE_DEFAULTS.cfg_interval_progress[0]).toBe(0);
  });
});
