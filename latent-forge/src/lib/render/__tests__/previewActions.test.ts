import { beforeEach, describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings, LENGTH_CAP_SEC } from "../../forge/defaults";
import type { RenderHistoryEntry, Target } from "../../forge/types";
import { settings } from "../../stores/settings.svelte";
import {
  applyPayloadSettings, NOT_THIS_CLIP_HINT, NO_PREVIEW_HINT, NO_SETTINGS_HINT,
  payloadSettings, RENDER_RUNNING_HINT, replaceClipBlock, useSettingsBlock,
} from "../previewActions";

const NONE: Target = { kind: "none" };
const CLIP: Target = { kind: "clip", id: "c1" };
const OVERLAP: Target = { kind: "overlap", key: "c1-c2" };

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 30, source_clip_id: null, created: 1, ...p,
  };
}

// Writer A T1's generatePayload: `{ ...renderWire(s, cfg), duration: cap(s.duration_sec) }`.
const GENERATE_PAYLOAD = {
  prompt: "a room", negative_prompt: "", steps: 40, cfg_scale: 7, seed: -1, apg_scale: 0,
  cfg_interval_progress: [0.1, 0.9], scale_phi: 0, sampler_type: "dpmpp-3m-sde",
  schedule: { shape: "model", rho: 7, sigma_min: 0.03, lam_min: -8, lam_max: 8, stepped: false, plateaus: [], tilt: 0 },
  duration: 62.5,
};

describe("payloadSettings — one shape per op, and the payload is never passed through whole", () => {
  it("takes generate's own body as the settings and its `duration` as the length", () => {
    const ps = payloadSettings("generate", GENERATE_PAYLOAD);
    expect(ps.durationSec).toBe(62.5);
    expect(ps.body).not.toBeNull();
    expect("duration" in (ps.body as object)).toBe(false);
    expect(ps.body).toMatchObject({ prompt: "a room", steps: 40, sampler_type: "dpmpp-3m-sde" });
  });

  it("takes a2a_clip's NESTED render object, and no length — the clip supplies that", () => {
    const ps = payloadSettings("a2a_clip", {
      audio: { kind: "upload", sha256: "a" }, render: { steps: 24, prompt: "x" },
      envelope: null, noise_level: 0.4, chain: null, ckpt_path: null,
    });
    expect(ps.body).toEqual({ steps: 24, prompt: "x" });
    expect(ps.durationSec).toBeNull();
  });

  it("takes inpaint's nested render object, and no length — the region supplies that", () => {
    const ps = payloadSettings("inpaint", {
      a: {}, b: {}, region: { start_sec: 1, end_sec: 3 }, curve: null, chroma_xfade: true,
      render: { steps: 32 }, pad_sec: 8,
    });
    expect(ps.body).toEqual({ steps: 32 });
    expect(ps.durationSec).toBeNull();
  });

  it("takes commit's top-level duration_sec and offers no settings — every lane has its own", () => {
    const ps = payloadSettings("commit", { lanes: [], clips: [], overlaps: [], duration_sec: 120 });
    expect(ps.body).toBeNull();
    expect(ps.durationSec).toBe(120);
  });

  it("never hands longform's arc string to the schedule field", () => {
    const ps = payloadSettings("longform", {
      schedule: "0:a|45:b", steps: 24, cfg_scale: 6, seed: 7, duration: 120,
    });
    expect(ps.body).toEqual({ steps: 24, cfg_scale: 6, seed: 7 });
    expect("schedule" in (ps.body as object)).toBe(false);
    expect(ps.durationSec).toBe(120);
  });

  it("offers bend's seed and nothing else", () => {
    expect(payloadSettings("bend", { crop_id: "000412", ops: [{}], seed: 11 }))
      .toEqual({ body: { seed: 11 }, durationSec: null });
  });

  it("says honestly that a decode carries no settings at all", () => {
    expect(payloadSettings("decode", { crop_id: "000412" }))
      .toEqual({ body: null, durationSec: null });
  });

  it("survives a payload that is not an object — JobRecord.payload is `unknown`", () => {
    expect(payloadSettings("generate", null)).toEqual({ body: null, durationSec: null });
    expect(payloadSettings("generate", "nope")).toEqual({ body: null, durationSec: null });
    expect(payloadSettings("a2a_clip", { render: "nope" })).toEqual({ body: null, durationSec: null });
  });

  it("ignores a non-finite or out-of-range duration rather than writing it", () => {
    expect(payloadSettings("generate", { ...GENERATE_PAYLOAD, duration: "long" }).durationSec).toBeNull();
    expect(payloadSettings("generate", { ...GENERATE_PAYLOAD, duration: 0 }).durationSec).toBeNull();
    expect(payloadSettings("generate", { ...GENERATE_PAYLOAD, duration: NaN }).durationSec).toBeNull();
  });
});
