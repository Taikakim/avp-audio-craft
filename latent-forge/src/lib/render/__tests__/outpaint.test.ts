// Owner: WINTERMUTE (created 2026-10-14) -- clip OUTPAINT: handle math, dispatch, payload, tag, grow
import { beforeEach, describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS } from "../../forge/defaults";
import type { AudioRef, ForgeClip, ForgeLane, RenderSettings } from "../../forge/types";
import { arrangement } from "../../stores/arrangement.svelte";
import { targetTag } from "../../../ui/prompt/targetBar";
import { hasOutpaint, renderRequest, type DispatchWorld } from "../dispatch";
import { outpaintPayload, PayloadError } from "../payloads";

const REF: AudioRef = { kind: "upload", sha256: "c".repeat(64) };
const STRETCHED: AudioRef = { kind: "render", job_id: "st", file: "out_00.wav" };

function settings(): RenderSettings {
  return {
    prompt: "goa", negative_prompt: "", steps: 8, cfg_scale: 1, seed: 7, apg_scale: 0,
    cfg_interval_progress: [0, 1], scale_phi: 0, sampler_type: null, duration_sec: 45,
    schedule: { shape: "model", rho: 1, sigma_min: 0.01, lam_min: -6, lam_max: 3, stepped: false, plateaus: 4, tilt: 0.5 },
  } as RenderSettings;
}

function lane(): ForgeLane {
  return { index: 0, name: "LANE 1", muted: false, solo: false, gain: 1, chain: structuredClone(CHAIN_DEFAULTS) };
}

function world(clip: ForgeClip): DispatchWorld {
  return {
    settings: settings(), cfgScale: 1, clip, lane: lane(), heads: {}, ckptPath: "/x/dora.ckpt",
    overlap: null, overlapParams: null, clipById: () => null, arcPrompt: "", bendOps: [], padSec: 8,
  };
}

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
});

describe("outpaint handles (arrangement.setOutpaintEdge)", () => {
  it("dragging out sets pre/post; dragging back onto the clip clears that side, then the whole", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 20, durSec: 30, audio: REF });
    arrangement.setOutpaintEdge(c.id, "end", 90);
    expect(c.outpaint).toEqual({ pre_sec: 0, post_sec: 40 });
    arrangement.setOutpaintEdge(c.id, "start", 5);
    expect(c.outpaint).toEqual({ pre_sec: 15, post_sec: 40 });
    arrangement.setOutpaintEdge(c.id, "start", -10);         // never before 0 s on the timeline
    expect(c.outpaint?.pre_sec).toBe(20);
    arrangement.setOutpaintEdge(c.id, "end", 40);            // back inside the clip
    expect(c.outpaint).toEqual({ pre_sec: 20, post_sec: 0 });
    arrangement.setOutpaintEdge(c.id, "start", 25);
    expect(c.outpaint).toBeNull();
  });

  it("growClipForOutpaint moves the start back and spans the whole new file", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 20, durSec: 30, audio: REF });
    arrangement.setOutpaintEdge(c.id, "end", 60);
    arrangement.growClipForOutpaint(c.id, 8, 48);
    expect([c.start_sec, c.offset_sec, c.dur_sec, c.outpaint]).toEqual([12, 0, 48, null]);
  });
});

describe("outpaint dispatch", () => {
  it("a pending outpaint renders op outpaint with the timeline file and window, over A2A", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 10, durSec: 30, audio: REF });
    c.offset_sec = 4;
    c.previewAudio = STRETCHED;
    c.a2a = { on: true, noise: 0.4, envelope: { points: [0, 0, 0, 0], curves: [0, 0, 0] } };
    arrangement.setOutpaintEdge(c.id, "end", 70);
    expect(hasOutpaint(c)).toBe(true);
    const req = renderRequest({ kind: "clip", id: c.id }, world(c));
    expect([req.op, req.kind, req.sourceClipId]).toEqual(["outpaint", "outpaint", c.id]);
    expect(req.payload).toMatchObject({
      audio: STRETCHED, offset_sec: 4, dur_sec: 30, pre_sec: 0, post_sec: 30, context_sec: 30,
      ckpt_path: "/x/dora.ckpt",
    });
    expect(((req.payload as Record<string, unknown>).render as Record<string, unknown>).prompt).toBe("goa");
  });

  it("the tag reads OUTPAINT only for a clip with a pending outpaint", () => {
    expect(targetTag({ kind: "clip", id: "x" }, true, true)).toBe("OUTPAINT");
    expect(targetTag({ kind: "clip", id: "x" }, true, false)).toBe("A2A");
    expect(targetTag({ kind: "overlap", key: "k" }, false, true)).toBe("INPAINT");
  });

  it("the payload refuses nothing to generate and out-of-range lengths", () => {
    const base = {
      audio: REF, offset_sec: 0, dur_sec: 10, render: settings(), chain: null, heads: {}, ckptPath: null,
    };
    expect(() => outpaintPayload({ ...base, pre_sec: 0, post_sec: 0 })).toThrow(PayloadError);
    expect(() => outpaintPayload({ ...base, pre_sec: 0, post_sec: 601 })).toThrow(/post_sec/);
    expect(outpaintPayload({ ...base, pre_sec: 300, post_sec: 0 }).pre_sec).toBe(300);
  });
});
