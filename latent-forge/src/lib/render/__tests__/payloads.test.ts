import { describe, expect, it } from "vitest";
import type { Envelope, ForgeClip, ForgeLane, OverlapParams, RenderSettings } from "../../forge/types";
import { BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings } from "../../forge/defaults";
import type { LatchHeadInfo } from "../../chains/latch";
import {
  CAP_SEC, PayloadError, RENDER_WIRE_KEYS, a2aClipPayload, commitPayload,
  generatePayload, inpaintPayload, opPayload, renderWire,
} from "../payloads";

// M8 RENDER_DEFAULTS, m8 plan:262-264 -- the ONLY keys parse_render tolerates. duration_sec is
// deliberately absent: _merge 400s on it.
const M8_RENDER_KEYS = [
  "apg_scale", "cfg_interval_progress", "cfg_scale", "negative_prompt", "prompt",
  "sampler_type", "scale_phi", "schedule", "seed", "steps",
];
// M3 parse_spec DEFAULTS, m3 plan:205-206.
const M8_SCHEDULE_KEYS = ["lam_max", "lam_min", "plateaus", "rho", "shape", "sigma_min", "stepped", "tilt"];

const HEADS: Record<string, LatchHeadInfo> = {
  recurrence: { name: "recurrence", default_gain: 10 } as LatchHeadInfo,
  density: { name: "density", default_gain: 4 } as LatchHeadInfo,
};
const ENV: Envelope = { points: [0.2, 0.6, 0.6, 0.2], curves: [0, 0, 0] };
const REF = { kind: "upload", sha256: "a".repeat(64) } as const;

function settings(patch: Partial<RenderSettings> = {}): RenderSettings {
  return { ...cloneRenderSettings(BASE_DEFAULTS), ...patch };
}

function lane(index: 0 | 1 | 2 | 3): ForgeLane {
  return {
    index, name: `LANE ${index + 1}`, muted: false, solo: false, gain: 1,
    chain: structuredClone(CHAIN_DEFAULTS),
  };
}

function clip(patch: Partial<ForgeClip> = {}): ForgeClip {
  return {
    id: "c1", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false, audio: REF,
    native_bpm: 120, detune_cents: 0, downbeats_sec: [], render: settings(),
    a2a: null, latentState: "none", history: [], ...patch,
  } as ForgeClip;
}

function overlapParams(patch: Partial<OverlapParams> = {}): OverlapParams {
  return {
    curve: { points: [0, 0.35, 0.7, 1], curves: [0, 0, 0] }, chroma_xfade: true,
    override: false, steps: 28, cfg: 3.0, render: settings({ steps: 24, cfg_scale: 6 }), ...patch,
  };
}

function commitArgs(patch: Record<string, unknown> = {}) {
  return {
    bpm: 120,
    durationSec: 40,
    defaults: settings(),
    lanes: [lane(0), lane(1), lane(2), lane(3)],
    clips: [clip()],
    overlaps: [],
    overlapParamsOf: () => overlapParams(),
    mix: {
      order: "tree" as const,
      nodes: { M1: { interp: "lerp" as const, t: 0.5 }, M2: { interp: "lerp" as const, t: 0.5 }, MX: { interp: "lerp" as const, t: 0.5 } },
      quad_weights: [1, 1, 1, 1] as [number, number, number, number],
    },
    master: { latch_on: false, head: "none", gain: 64, norm_on: true },
    decodeLanes: false,
    heads: HEADS,
    cfgOf: (s: RenderSettings) => s.cfg_scale,
    ...patch,
  };
}

describe("renderWire -- the only object that may reach M8 parse_render", () => {
  it("emits exactly M8 RENDER_DEFAULTS' key set and drops duration_sec", () => {
    const wire = renderWire(settings({ duration_sec: 47.556 }));
    expect(Object.keys(wire).sort()).toEqual(M8_RENDER_KEYS);
    expect("duration_sec" in wire).toBe(false);
    expect(RENDER_WIRE_KEYS.slice().sort()).toEqual(M8_RENDER_KEYS);
  });

  it("emits exactly M3 parse_spec's schedule key set, as a copy", () => {
    const s = settings();
    const wire = renderWire(s);
    expect(Object.keys(wire.schedule).sort()).toEqual(M8_SCHEDULE_KEYS);
    expect(wire.schedule).not.toBe(s.schedule);
    expect(wire.cfg_interval_progress).not.toBe(s.cfg_interval_progress);
  });

  it("takes the caller's cfg so POST can send 1.0 without mutating the target (spec 5.3)", () => {
    expect(renderWire(settings({ cfg_scale: 6 }), 1.0).cfg_scale).toBe(1.0);
    expect(renderWire(settings({ cfg_scale: 6 })).cfg_scale).toBe(6);
  });

  it("refuses a non-finite number rather than sending NaN that 400s server-side", () => {
    expect(() => renderWire(settings({ steps: Number.NaN }))).toThrow(PayloadError);
  });
});

describe("generatePayload", () => {
  it("sends the wire name `duration`, never `duration_sec` (M1 Normative; HANDOUT)", () => {
    const p = generatePayload(settings({ duration_sec: 45, prompt: "dub" }));
    expect(p.duration).toBe(45);
    expect("duration_sec" in p).toBe(false);
    expect(p.prompt).toBe("dub");
  });

  it("carries the picked adapter as top-level ckpt_path, null when none", () => {
    expect(generatePayload(settings({ prompt: "dub" })).ckpt_path).toBeNull();
    const p = generatePayload(settings({ prompt: "dub" }), 6, "/runs/x/epoch=1.ckpt");
    expect(p.ckpt_path).toBe("/runs/x/epoch=1.ckpt");
  });

  it("refuses a length over the 184 s cap before the round trip", () => {
    // The prompt guard runs before the cap (the server's own precedence in `_generate_impl`), so
    // this case must carry a prompt or it throws `prompt is required` and never reaches /184/.
    expect(() => generatePayload(settings({ prompt: "dub", duration_sec: CAP_SEC + 1 }))).toThrow(/184/);
  });

  it("refuses an empty prompt -- _generate_impl raises `prompt is required`", () => {
    expect(() => generatePayload(settings({ prompt: "   " }))).toThrow(/prompt/);
  });
});

describe("opPayload -- the clip's OP when A2A is off (spec 7.1)", () => {
  it("decode needs a latent source and sends it unchanged", () => {
    expect(opPayload("decode", { cropId: "000412" })).toEqual({ crop_id: "000412" });
    expect(opPayload("decode", { latentPath: "/SERVER/z/a.npy" })).toEqual({ latent_path: "/SERVER/z/a.npy" });
    expect(() => opPayload("decode", {})).toThrow(/latent_path or crop_id/);
  });

  it("bend sends a non-empty ops list beside the same latent source", () => {
    const p = opPayload("bend", { cropId: "000412", ops: [{ op: "roll", amount: 0.2 }], seed: 7 });
    expect(p).toEqual({ crop_id: "000412", ops: [{ op: "roll", amount: 0.2 }], seed: 7 });
    expect(() => opPayload("bend", { cropId: "000412", ops: [] })).toThrow(/ops/);
  });

  it("longform sends the prompt-ARC STRING under `prompt_arc` and no ScheduleSpec object", () => {
    // M3 T2 (h): _longform_impl reads the arc grammar from req["prompt_arc"]; `schedule` is the
    // ScheduleSpec key everywhere, so the arc must not be sent there any more.
    const p = opPayload("longform", { arc: "0:pad|45:break", steps: 24, cfgScale: 6, seed: -1, durationSec: 120 });
    expect(p.prompt_arc).toBe("0:pad|45:break");
    expect(typeof p.prompt_arc).toBe("string");
    expect(p.schedule).toBeUndefined();
    expect(p.duration).toBe(120);
  });

  it("longform refuses an empty arc and a length over the cap", () => {
    expect(() => opPayload("longform", { arc: "  ", steps: 24, cfgScale: 6, seed: -1, durationSec: 60 })).toThrow(/arc/);
    expect(() => opPayload("longform", { arc: "0:pad", steps: 24, cfgScale: 6, seed: -1, durationSec: CAP_SEC + 1 })).toThrow(/184/);
  });
});

describe("a2aClipPayload -- spec 6.7, validated by M8 validate_a2a_clip", () => {
  it("emits exactly the six keys validate_a2a_clip reads, with a duration_sec-free render", () => {
    const p = a2aClipPayload({
      audio: REF, render: settings({ duration_sec: 47 }), a2a: { on: true, noise: 0.35, envelope: ENV },
      chain: structuredClone(CHAIN_DEFAULTS), heads: HEADS, ckptPath: "/SERVER/x.ckpt", cfgScale: 6,
    });
    expect(Object.keys(p).sort()).toEqual(["audio", "chain", "ckpt_path", "envelope", "noise_level", "render"]);
    expect(Object.keys(p.render as object).sort()).toEqual(M8_RENDER_KEYS);
  });

  it("sends the envelope when the clip has one, and null with a flat noise_level when it does not", () => {
    const withEnv = a2aClipPayload({
      audio: REF, render: settings(), a2a: { on: true, noise: 0.35, envelope: ENV },
      chain: null, heads: HEADS, ckptPath: null, cfgScale: 6,
    });
    expect(withEnv.envelope).toEqual(ENV);
    expect(withEnv.noise_level).toBe(0.35);
    const flat = a2aClipPayload({
      audio: REF, render: settings(), a2a: { on: true, noise: 0.35, envelope: null as unknown as Envelope },
      chain: null, heads: HEADS, ckptPath: null, cfgScale: 6,
    });
    expect(flat.envelope).toBeNull();
    expect(flat.noise_level).toBe(0.35);
  });

  it("sends chainRequest's object, with lora.slot null, and null when the lane has no chain", () => {
    const chain = structuredClone(CHAIN_DEFAULTS);
    chain.lora = { ckpt_path: "/SERVER/lora.ckpt", slot: 3, strength: 0.8 };
    const p = a2aClipPayload({ audio: REF, render: settings(), a2a: { on: true, noise: 0.4, envelope: null as unknown as Envelope }, chain, heads: HEADS, ckptPath: null, cfgScale: 6 });
    expect((p.chain as { lora: unknown }).lora).toEqual({ ckpt_path: "/SERVER/lora.ckpt", slot: null, strength: 0.8 });
    const none = a2aClipPayload({ audio: REF, render: settings(), a2a: { on: true, noise: 0.4, envelope: null as unknown as Envelope }, chain: null, heads: HEADS, ckptPath: null, cfgScale: 6 });
    expect(none.chain).toBeNull();
  });

  it("refuses a noise level outside 0..1 -- validate_a2a_clip's _num(…, 0, 1)", () => {
    expect(() => a2aClipPayload({
      audio: REF, render: settings(), a2a: { on: true, noise: 1.5, envelope: null as unknown as Envelope },
      chain: null, heads: HEADS, ckptPath: null, cfgScale: 6,
    })).toThrow(/noise_level/);
  });
});

describe("inpaintPayload -- spec 6.8, validated by M8 validate_inpaint", () => {
  const args = {
    a: { audio: REF, start_sec: 0, offset_sec: 0, dur_sec: 20 },
    b: { audio: { kind: "upload", sha256: "b".repeat(64) } as const, start_sec: 16, offset_sec: 0, dur_sec: 20 },
    region: { start_sec: 16, end_sec: 20 },
    params: overlapParams(),
    cfgScale: 6,
  };

  it("emits exactly the seven keys validate_inpaint reads, with pad_sec defaulting to 8", () => {
    const p = inpaintPayload(args);
    expect(Object.keys(p).sort()).toEqual(["a", "b", "chroma_xfade", "curve", "pad_sec", "region", "render"]);
    expect(p.pad_sec).toBe(8);
    expect(Object.keys(p.render as object).sort()).toEqual(M8_RENDER_KEYS);
  });

  it("applies the overlap's LOCAL steps/cfg into the render when override is on", () => {
    const p = inpaintPayload({ ...args, params: overlapParams({ override: true, steps: 28, cfg: 3 }) });
    expect((p.render as { steps: number; cfg_scale: number }).steps).toBe(28);
    expect((p.render as { steps: number; cfg_scale: number }).cfg_scale).toBe(3);
    const off = inpaintPayload({ ...args, params: overlapParams({ override: false }) });
    expect((off.render as { steps: number }).steps).toBe(24);
  });

  it("refuses start >= end, and a padded span over the cap, before the round trip", () => {
    expect(() => inpaintPayload({ ...args, region: { start_sec: 20, end_sec: 16 } })).toThrow(/start_sec/);
    expect(() => inpaintPayload({ ...args, region: { start_sec: 0, end_sec: 180 } })).toThrow(/184/);
  });
});

describe("commitPayload -- spec 6.9, validated by M8 validate_commit", () => {
  it("emits exactly validate_commit's nine top-level keys with duration_sec at the top", () => {
    const p = commitPayload(commitArgs());
    expect(Object.keys(p).sort()).toEqual([
      "clips", "decode_lanes", "defaults", "duration_sec", "lanes", "master", "mix", "overlaps", "project_bpm",
    ]);
    expect(p.duration_sec).toBe(40);
    expect(Object.keys(p.defaults as object).sort()).toEqual(M8_RENDER_KEYS);
  });

  it("sends lanes 0,1,2,3 exactly once, each with a chainRequest chain", () => {
    const p = commitPayload(commitArgs());
    const lanes = p.lanes as { index: number; chain: Record<string, unknown> }[];
    expect(lanes.map((l) => l.index).sort()).toEqual([0, 1, 2, 3]);
    for (const l of lanes) expect(Object.keys(l.chain).sort()).toEqual(Object.keys(CHAIN_DEFAULTS).sort());
    expect(Object.keys(lanes[0]).sort()).toEqual(["chain", "gain", "index", "muted", "solo"]);
  });

  it("maps the client's {on, noise, envelope} + clip.render onto the wire's null | {render, envelope}", () => {
    const on = commitPayload(commitArgs({ clips: [clip({ a2a: { on: true, noise: 0.4, envelope: ENV } })] }));
    const wired = (on.clips as { a2a: { render: object; envelope: Envelope } | null }[])[0].a2a!;
    expect(Object.keys(wired).sort()).toEqual(["envelope", "render"]);
    expect(Object.keys(wired.render).sort()).toEqual(M8_RENDER_KEYS);
    expect(wired.envelope).toEqual(ENV);
    const off = commitPayload(commitArgs({ clips: [clip({ a2a: { on: false, noise: 0.4, envelope: ENV } })] }));
    expect((off.clips as { a2a: unknown }[])[0].a2a).toBeNull();
    const absent = commitPayload(commitArgs({ clips: [clip({ a2a: null })] }));
    expect((absent.clips as { a2a: unknown }[])[0].a2a).toBeNull();
  });

  it("emits a flat noise envelope when A2A is on with no curve, so the wire is never {render, null}", () => {
    const p = commitPayload(commitArgs({ clips: [clip({ a2a: { on: true, noise: 0.25, envelope: null as unknown as Envelope } })] }));
    const wired = (p.clips as { a2a: { envelope: Envelope } }[])[0].a2a;
    expect(wired.envelope).toEqual({ points: [0.25, 0.25, 0.25, 0.25], curves: [0, 0, 0] });
  });

  it("emits each clip with exactly validate_commit's ten clip keys", () => {
    const p = commitPayload(commitArgs());
    expect(Object.keys((p.clips as object[])[0]).sort()).toEqual([
      "a2a", "audio", "detune_cents", "dur_sec", "id", "lane", "loop", "native_bpm", "offset_sec", "start_sec",
    ]);
  });

  it("turns the derived Overlap[] plus the OverlapParams record into a LIST of nine-key rows", () => {
    const p = commitPayload(commitArgs({
      clips: [clip({ id: "a", start_sec: 0, dur_sec: 10 }), clip({ id: "b", start_sec: 6, dur_sec: 10 })],
      overlaps: [{ key: "a-b", lane: 0 as const, start_sec: 6, end_sec: 10, a_id: "a", b_id: "b" }],
    }));
    const rows = p.overlaps as Record<string, unknown>[];
    expect(Array.isArray(rows)).toBe(true);
    expect(Object.keys(rows[0]).sort()).toEqual([
      "a_id", "b_id", "chroma_xfade", "curve", "end_sec", "key", "lane", "render", "start_sec",
    ]);
  });

  it("applies each overlap's LOCAL steps/cfg into its render before sending", () => {
    const p = commitPayload(commitArgs({
      clips: [clip({ id: "a", start_sec: 0, dur_sec: 10 }), clip({ id: "b", start_sec: 6, dur_sec: 10 })],
      overlaps: [{ key: "a-b", lane: 0 as const, start_sec: 6, end_sec: 10, a_id: "a", b_id: "b" }],
      overlapParamsOf: () => overlapParams({ override: true, steps: 28, cfg: 3 }),
    }));
    expect(((p.overlaps as { render: { steps: number; cfg_scale: number } }[])[0]).render).toMatchObject({ steps: 28, cfg_scale: 3 });
  });

  it("refuses an empty arrangement with the hint the MIXDOWN button shows", () => {
    expect(() => commitPayload(commitArgs({ clips: [] }))).toThrow(/no clips/);
  });

  it("refuses a stretch ratio outside 0.5..2 and a detune outside +/-100", () => {
    expect(() => commitPayload(commitArgs({ bpm: 120, clips: [clip({ native_bpm: 40 })] }))).toThrow(/0\.5\.\.2/);
    expect(() => commitPayload(commitArgs({ clips: [clip({ detune_cents: 150 })] }))).toThrow(/detune/);
  });

  it("refuses a master head the registry does not list while latch_on", () => {
    expect(() => commitPayload(commitArgs({ master: { latch_on: true, head: "ghost", gain: 64, norm_on: true } }))).toThrow(/master head/);
    expect(() => commitPayload(commitArgs({ master: { latch_on: false, head: "ghost", gain: 64, norm_on: true } }))).not.toThrow();
  });

  it("refuses a duration over the cap", () => {
    expect(() => commitPayload(commitArgs({ durationSec: CAP_SEC + 0.1 }))).toThrow(/184/);
  });
});
