import { describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS } from "../../forge/defaults";
import type { AudioRef, Envelope, ForgeClip, ForgeLane, OverlapParams, RenderSettings } from "../../forge/types";
import { PayloadError } from "../payloads";
import { PREVIEW_RENDER_IDLE_LABEL, renderLabel, renderRequest, type DispatchWorld } from "../dispatch";
import { mixdownLabel } from "../../../ui/topbar/mixdown";

const CROP: AudioRef = { kind: "crop", crop_id: "000412" };
const UP: AudioRef = { kind: "upload", sha256: "a".repeat(64) };
const FLAT: Envelope = { points: [0.4, 0.4, 0.4, 0.4], curves: [0, 0, 0] };

function settings(p: Partial<RenderSettings> = {}): RenderSettings {
  return {
    prompt: "a room", negative_prompt: "", steps: 24, cfg_scale: 6, seed: -1, apg_scale: 0,
    cfg_interval_progress: [0, 1], scale_phi: 0, sampler_type: null, duration_sec: 45,
    schedule: { shape: "model", rho: 1, sigma_min: 0.01, lam_min: -6, lam_max: 3, stepped: false, plateaus: 4, tilt: 0.5 },
    ...p,
  } as RenderSettings;
}

function clip(p: Partial<ForgeClip> = {}): ForgeClip {
  return {
    id: "c1", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false, audio: UP,
    native_bpm: null, detune_cents: 0, downbeats_sec: [], render: settings(), a2a: null,
    latentState: "none", history: [], op: null, ...p,
  } as ForgeClip;
}

function lane(index: 0 | 1 | 2 | 3 = 0): ForgeLane {
  return {
    index, name: `LANE ${index + 1}`, muted: false, solo: false, gain: 1,
    // The REAL defaults: the plan's slimmed literal had `slots: []`, and chainRequest (rightly) reads
    // slots[0]/[1] -- an empty list is not a valid LaneChain.
    chain: structuredClone(CHAIN_DEFAULTS),
  };
}

function overlapParams(p: Partial<OverlapParams> = {}): OverlapParams {
  return { curve: { points: [0, 0.35, 0.7, 1], curves: [0, 0, 0] }, chroma_xfade: true, override: false, steps: 28, cfg: 3.0, render: settings(), ...p };
}

function world(p: Partial<DispatchWorld> = {}): DispatchWorld {
  return {
    settings: settings(), cfgScale: 6, clip: null, lane: null, heads: {}, ckptPath: null,
    overlap: null, overlapParams: null, clipById: () => null, arcPrompt: "", bendOps: [], padSec: 8,
    ...p,
  };
}

describe("renderRequest — spec §7.1's dispatch table, one row per test", () => {
  it("nothing selected renders `generate` under the session target key", () => {
    const req = renderRequest({ kind: "none" }, world({ settings: settings({ duration_sec: 30 }) }));
    expect(req.op).toBe("generate");
    expect(req.kind).toBe("gen");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey).toBe("session");
  });

  it("a plain generate carries the lane chain (LatCH steers without A2A) and the top-bar ckpt", () => {
    const l = lane(1);
    l.chain.latch_on = true;
    const req = renderRequest({ kind: "none" }, world({ lane: l, ckptPath: "/top.ckpt" }));
    const payload = req.payload as Record<string, unknown>;
    expect((payload.chain as { latch_on: boolean }).latch_on).toBe(true);
    expect(payload.ckpt_path).toBe("/top.ckpt");
    expect((renderRequest({ kind: "none" }, world()).payload as Record<string, unknown>).chain).toBeNull();
  });

  it("sends LENGTH as the wire name `duration`, never `duration_sec` (Fact 1)", () => {
    const req = renderRequest({ kind: "none" }, world({ settings: settings({ duration_sec: 30 }) }));
    const payload = req.payload as Record<string, unknown>;
    expect(payload.duration).toBe(30);
    expect("duration_sec" in payload).toBe(false);
  });

  it("a clip with A2A on renders `a2a_clip` on the clip's whole audio", () => {
    const c = clip({ audio: CROP, a2a: { on: true, noise: 0.4, envelope: FLAT } });
    const req = renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: lane(0) }));
    expect(req.op).toBe("a2a_clip");
    expect(req.kind).toBe("a2a");
    expect(req.sourceClipId).toBe("c1");
    expect(req.targetKey).toBe("clip:c1");
    expect((req.payload as Record<string, unknown>).audio).toEqual(CROP);
    expect((req.payload as Record<string, unknown>).noise_level).toBe(0.4);
  });

  it("a2a_clip uses the CLIP's own lane chain, not the active lane's (§7.1 row 2)", () => {
    const c = clip({ lane: 2, a2a: { on: true, noise: 0.2, envelope: FLAT } });
    const l2 = lane(2);
    l2.chain.bungee_on = true;
    l2.chain.semitones = 5;
    const req = renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: l2 }));
    const chain = (req.payload as Record<string, unknown>).chain as Record<string, unknown>;
    expect(chain.bungee_on).toBe(true);
    expect(chain.semitones).toBe(5);
  });

  it("a clip with A2A off renders the clip's OP, passed to the wire untranslated", () => {
    const c = clip({ audio: CROP, op: "decode", latentState: "valid" });
    const req = renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: lane(0) }));
    expect(req.op).toBe("decode");
    expect(req.kind).toBe("gen");
    expect(req.sourceClipId).toBe("c1");
    expect(req.payload).toEqual({ crop_id: "000412" });
  });

  it("op `longform` sends the prompt ARC under `prompt_arc`, not a ScheduleSpec", () => {
    const c = clip({ op: "longform" });
    const req = renderRequest(
      { kind: "clip", id: c.id },
      world({ clip: c, lane: lane(0), arcPrompt: "0:opening pad|45:driving bass" }),
    );
    expect(req.op).toBe("longform");
    expect((req.payload as Record<string, unknown>).prompt_arc).toBe("0:opening pad|45:driving bass");
    expect((req.payload as Record<string, unknown>).schedule).toBeUndefined();
  });

  it("a clip with neither A2A nor an OP is a caller error, not a silent generate", () => {
    const c = clip({ a2a: null, op: null });
    expect(() => renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: lane(0) })))
      .toThrow(PayloadError);
  });

  it("an overlap renders `inpaint` with both clips' sides and the overlap's span", () => {
    const a = clip({ id: "a", dur_sec: 8, start_sec: 0 });
    const b = clip({ id: "b", dur_sec: 8, start_sec: 6, audio: CROP });
    const req = renderRequest(
      { kind: "overlap", key: "a-b" },
      world({
        overlap: { key: "a-b", lane: 0, start_sec: 6, end_sec: 8, a_id: "a", b_id: "b" },
        overlapParams: overlapParams(),
        clipById: (id) => (id === "a" ? a : id === "b" ? b : null),
      }),
    );
    expect(req.op).toBe("inpaint");
    expect(req.kind).toBe("inpaint");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey).toBe("overlap:a-b");
    const payload = req.payload as Record<string, unknown>;
    expect(payload.region).toEqual({ start_sec: 6, end_sec: 8 });
    expect((payload.a as Record<string, unknown>).audio).toEqual(UP);
    expect((payload.b as Record<string, unknown>).audio).toEqual(CROP);
    expect(payload.pad_sec).toBe(8);
  });

  it("the overlap's LOCAL steps/cfg override reaches the wire already applied (Fact 2)", () => {
    const a = clip({ id: "a" });
    const b = clip({ id: "b" });
    const req = renderRequest(
      { kind: "overlap", key: "a-b" },
      world({
        overlap: { key: "a-b", lane: 0, start_sec: 6, end_sec: 8, a_id: "a", b_id: "b" },
        overlapParams: overlapParams({ override: true, steps: 40, cfg: 2.5 }),
        clipById: (id) => (id === "a" ? a : id === "b" ? b : null),
      }),
    );
    const render = (req.payload as Record<string, unknown>).render as Record<string, unknown>;
    expect(render.steps).toBe(40);
    expect(render.cfg_scale).toBe(2.5);
  });
});

describe("renderLabel is M1's MIXDOWN sentence on the other render control (§7.1)", () => {
  it("is ▸ RENDER while idle and the SAMPLING sentence while a job runs", () => {
    expect(renderLabel(false, 44)).toBe(PREVIEW_RENDER_IDLE_LABEL);
    expect(renderLabel(true, 44)).toBe("SAMPLING · 44 steps left");
    expect(renderLabel(true, 44)).toBe(mixdownLabel(true, 44));
  });

  it("shows 0 steps left rather than nothing when steps_total is 0 (Fact 5)", () => {
    expect(renderLabel(true, 0)).toBe("SAMPLING · 0 steps left");
    expect(renderLabel(true, null)).toBe("SAMPLING · 0 steps left");
  });
});
