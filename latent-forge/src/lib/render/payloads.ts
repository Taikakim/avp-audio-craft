// Pure builders for every /forge/jobs payload (spec §6.7-6.9, §7.1). Nothing here touches a store
// or a rune: the caller reads state and hands it in, so each builder is a table-testable function.
//
// THE RULE THIS FILE EXISTS FOR: M8's `_merge` REJECTS unknown keys --
//   unknown = sorted(set(obj) - set(defaults))
//   if unknown: raise ForgeError(400, f"unknown {what} field(s): {', '.join(unknown)}")
// (m8 plan:284-292). `RENDER_DEFAULTS` has no `duration_sec` (m8 plan:262-264), but M1's
// RenderSettings does (§4.5 LENGTH). So a render object is built key by key from
// RENDER_WIRE_KEYS and NEVER spread from RenderSettings. `generate` is the one op that carries a
// length, under the wire name `duration` (_generate_impl reads `duration`; a `duration_sec` there
// is silently ignored and renders 47 s -- HANDOUT, "A payload key the server does not read is
// silently ignored").

import { chainRequest, type ChainRequest, type LatchHeadInfo } from "../chains/latch";
import { SAMPLERS_BY_OBJECTIVE } from "../forge/defaults";
import { settings, type Objective } from "../stores/settings.svelte";
import type {
  AudioRef, Envelope, ForgeClip, ForgeLane, JobOp, MasterChain, MixSpec, OverlapParams,
  RenderSettings, ScheduleSpec,
} from "../forge/types";

/** Client-side refusal, raised before the round trip. Carries the server's own wording where the
 *  server has one, so an operator sees the same sentence whichever side caught it. */
export class PayloadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PayloadError";
  }
}

/** eval/forge/contract.py:301 `CAP_SEC = 184.0`. check_cap's message is quoted verbatim below. */
export const CAP_SEC = 184;
const CAP_MESSAGE = "forge passes are capped at 184 s locally (T<2048)";

/** M8 RENDER_DEFAULTS' key set, in the spec's field order (m8 plan:262-264). */
export const RENDER_WIRE_KEYS = [
  "prompt", "negative_prompt", "steps", "cfg_scale", "seed", "apg_scale",
  "cfg_interval_progress", "schedule", "scale_phi", "sampler_type",
] as const;

export interface RenderWire {
  prompt: string;
  negative_prompt: string;
  steps: number;
  cfg_scale: number;
  seed: number;
  apg_scale: number;
  cfg_interval_progress: [number, number];
  schedule: ScheduleSpec;
  scale_phi: number;
  sampler_type: string | null;
}

function num(v: number, lo: number, hi: number, what: string): number {
  if (typeof v !== "number" || !Number.isFinite(v) || v < lo || v > hi) {
    throw new PayloadError(`${what}=${String(v)} outside ${lo}..${hi}`);
  }
  return v;
}

function cap(durationSec: number, what: string): number {
  if (typeof durationSec !== "number" || !Number.isFinite(durationSec) || durationSec <= 0) {
    throw new PayloadError(`${what}: duration must be a positive number`);
  }
  if (durationSec > CAP_SEC) throw new PayloadError(CAP_MESSAGE);
  return durationSec;
}

/** M3 parse_spec's eight keys, copied one by one (m3 plan:205-206). */
function scheduleWire(s: ScheduleSpec): ScheduleSpec {
  return {
    shape: s.shape,
    rho: num(s.rho, 0.1, 15, "schedule.rho"),
    sigma_min: num(s.sigma_min, 0.001, 0.5, "schedule.sigma_min"),
    lam_min: num(s.lam_min, -12, 0, "schedule.lam_min"),
    lam_max: num(s.lam_max, 0, 6, "schedule.lam_max"),
    stepped: s.stepped === true,
    plateaus: num(s.plateaus, 2, 24, "schedule.plateaus"),
    tilt: num(s.tilt, 0, 1, "schedule.tilt"),
  };
}

/**
 * The ONLY object that may be handed to M8's parse_render. `cfgScale` is a parameter rather than a
 * read of `s.cfg_scale` so the POST stage can send 1.0 (spec §5.3, `settings.effectiveCfg`) without
 * mutating the target the user is editing. Ranges mirror parse_render's `_num` calls so a bad field
 * is named here instead of coming back as an opaque 400 a minute later.
 */
/** The sampler the SAMPLER select shows (samplers.ts resolveSampler, minus the LatCH case, which the
 *  server forces itself). A target's stored sampler survives a POST/BASE switch -- setStage only
 *  rewrites the session defaults -- so sending it raw put e.g. `dpmpp` on rf_denoiser while the UI
 *  showed `pingpong` (review 2026-10-01). Empty/null stays null: the server's per-objective default. */
export function wireSampler(requested: string | null | undefined, objective: Objective): string | null {
  if (requested === "" || requested == null) return null;
  const options: readonly string[] = SAMPLERS_BY_OBJECTIVE[objective] ?? [];
  return options.includes(requested) ? requested : (options[0] ?? null);
}

export function renderWire(
  s: RenderSettings, cfgScale: number = s.cfg_scale, objective: Objective = settings.objective,
): RenderWire {
  const cip = s.cfg_interval_progress;
  const lo = num(cip?.[0] ?? 0, 0, 1, "cfg_interval_progress[0]");
  const hi = num(cip?.[1] ?? 1, 0, 1, "cfg_interval_progress[1]");
  if (lo > hi) throw new PayloadError("render.cfg_interval_progress lo must be <= hi");
  return {
    prompt: s.prompt ?? "",
    negative_prompt: s.negative_prompt ?? "",
    steps: num(s.steps, 1, 150, "render.steps"),
    cfg_scale: num(cfgScale, 0, 64, "render.cfg_scale"),
    seed: num(s.seed, -1, 2 ** 31 - 1, "render.seed"),
    apg_scale: num(s.apg_scale, 0, 1, "render.apg_scale"),
    cfg_interval_progress: [lo, hi],
    schedule: scheduleWire(s.schedule),
    scale_phi: num(s.scale_phi, 0, 1, "render.scale_phi"),
    sampler_type: wireSampler(s.sampler_type, objective),
  };
}

// ------------------------------------------------------------------ generate (spec §7.1 row 1)

/**
 * `generate` does NOT go through parse_render: M2 registers the first six ops with
 * `_validate_existing`, which only checks the cap (m2 plan:1747-1751), and `_generate_impl` reads
 * the request key by key. The wire length is `duration` (server:1122 `duration = _f(req, "duration", 47.0)`).
 * No `chain` is sent: _generate_impl reads top-level `latch`/`film`/`dora` in chain_to_request's
 * ALREADY-MAPPED shape, which needs the head gains the client deliberately does not compute
 * (M7 T1's WHY). §7.1 row 1 is session defaults only, so nothing is lost.
 */
export function generatePayload(
  s: RenderSettings, cfgScale: number = s.cfg_scale, ckptPath: string | null = null,
  chain: ChainRequest | null = null,
): Record<string, unknown> {
  const wire = renderWire(s, cfgScale);
  if (!wire.prompt.trim()) throw new PayloadError("prompt is required");
  // The server folds a top-level ckpt_path into its dora request (resolve_dora_req); without it the
  // top bar's adapter pick never reached a generate (dora=none in the server log, 2026-10-09).
  // `chain` is the lane's LatCH/FiLM/LoRA; forge_api turns it into latch/film/dora (a lane LoRA
  // that is ON wins over the top-bar pick).
  return { ...wire, duration: cap(s.duration_sec, "generate"), ckpt_path: ckptPath || null, chain };
}

// ------------------------------------------------------------------ the clip's OP (spec §7.1 row 3)

export interface OpArgs {
  cropId?: string;
  latentPath?: string;
  ops?: unknown[];
  seed?: number;
  arc?: string;
  steps?: number;
  cfgScale?: number;
  durationSec?: number;
}

function latentSource(a: OpArgs): Record<string, unknown> {
  if (a.latentPath) return { latent_path: a.latentPath };
  if (a.cropId) return { crop_id: a.cropId };
  // _decode_impl / _bend_impl both raise exactly this (server:1977, 2032).
  throw new PayloadError("need latent_path or crop_id");
}

/**
 * `decode`, `longform`, `bend` -- the three of §7.1's OP column M9 can reach. `a2a_track`/`a2a_mix`
 * need a server-side audio PATH rather than an AudioRef and have no UI in this milestone; they stay
 * unbuilt rather than half-built (open question A3).
 *
 * The `longform` key collision (the arc string vs a ScheduleSpec object, both once under
 * `schedule`) is resolved server-side by M3 T2 (h): the ARC is `prompt_arc` now, and this builder
 * sends it there and NO ScheduleSpec on longform (the t2a longform path refuses non-model shapes).
 */
export function opPayload(op: Extract<JobOp, "decode" | "longform" | "bend">, a: OpArgs): Record<string, unknown> {
  if (op === "decode") return latentSource(a);
  if (op === "bend") {
    if (!Array.isArray(a.ops) || a.ops.length === 0) {
      throw new PayloadError("ops must be a non-empty list of bend-op dicts");
    }
    return { ...latentSource(a), ops: a.ops, seed: a.seed ?? -1 };
  }
  const arc = (a.arc ?? "").trim();
  if (!arc) throw new PayloadError("prompt_arc is required ('0:promptA|45:promptB|...' arc grammar)");
  return {
    // M3 T2 (h): the ARC moved off `schedule` to `prompt_arc`, so `schedule` stays free for the
    // ScheduleSpec on every path (the server still accepts an arc STRING under `schedule` for old callers).
    prompt_arc: arc,
    steps: num(a.steps ?? 24, 1, 150, "steps"),
    cfg_scale: num(a.cfgScale ?? 6, 0, 64, "cfg_scale"),
    seed: a.seed ?? -1,
    duration: cap(a.durationSec ?? 120, "longform"),
  };
}

// ------------------------------------------------------------------ a2a_clip (spec §6.7)

export interface A2AClipArgs {
  audio: AudioRef;
  render: RenderSettings;
  a2a: { on: boolean; noise: number; envelope: Envelope | null };
  chain: ForgeLane["chain"] | null;
  heads: Record<string, LatchHeadInfo>;
  ckptPath: string | null;
  cfgScale?: number;
}

/**
 * Six keys, exactly validate_a2a_clip's (m8 plan:1944-1954). The source is the WHOLE FILE: M8 takes
 * no offset, dur or stretch here (`duration = check_cap(audio.shape[1] / SR, "a2a_clip")`), so a
 * trimmed clip is A2A'd whole. That is the server's behaviour, not a client simplification --
 * Writer B's REPLACE CLIP has to keep the clip's own trim afterwards (open question A4).
 */
export function a2aClipPayload(a: A2AClipArgs): Record<string, unknown> {
  return {
    audio: a.audio,
    render: renderWire(a.render, a.cfgScale ?? a.render.cfg_scale),
    envelope: a.a2a.envelope ?? null,
    noise_level: num(a.a2a.noise, 0, 1, "noise_level"),
    chain: a.chain === null ? null : chainRequest(a.chain, a.heads),
    ckpt_path: a.ckptPath || null,
  };
}

// ------------------------------------------------------------------ inpaint (spec §6.8)

export interface InpaintSide { audio: AudioRef; start_sec: number; offset_sec: number; dur_sec: number }

export interface InpaintArgs {
  a: InpaintSide;
  b: InpaintSide;
  region: { start_sec: number; end_sec: number };
  params: OverlapParams;
  padSec?: number;
  cfgScale?: number;
}

/** LOCAL is the overlap's own steps/cfg override (spec §7.2: `{curve, chroma_xfade, override,
 *  steps, cfg, render}`). §6.8 says the render arrives with "steps/cfg already resolved by the
 *  client", so the override is folded in here and nowhere else. */
function withLocal(params: OverlapParams, cfgScale?: number): RenderWire {
  const base = renderWire(params.render, cfgScale ?? params.render.cfg_scale);
  if (!params.override) return base;
  return { ...base, steps: num(params.steps, 1, 150, "overlap.steps"), cfg_scale: num(params.cfg, 0, 64, "overlap.cfg") };
}

export function inpaintPayload(a: InpaintArgs): Record<string, unknown> {
  const { start_sec: rs, end_sec: re } = a.region;
  num(rs, 0, 1e5, "region.start_sec");
  num(re, 0, 1e5, "region.end_sec");
  if (!(rs < re)) throw new PayloadError("region start_sec < end_sec required");
  const pad = num(a.padSec ?? 8, 0, 60, "pad_sec");
  cap(re + pad - Math.max(0, rs - pad), "inpaint");
  return {
    a: { audio: a.a.audio, start_sec: a.a.start_sec, offset_sec: a.a.offset_sec, dur_sec: a.a.dur_sec },
    b: { audio: a.b.audio, start_sec: a.b.start_sec, offset_sec: a.b.offset_sec, dur_sec: a.b.dur_sec },
    region: { start_sec: rs, end_sec: re },
    curve: a.params.curve,
    chroma_xfade: a.params.chroma_xfade,
    render: withLocal(a.params, a.cfgScale),
    pad_sec: pad,
  };
}

// ------------------------------------------------------------------ commit (spec §6.9)

export interface DerivedOverlap {
  key: string; lane: 0 | 1 | 2 | 3; start_sec: number; end_sec: number; a_id: string; b_id: string;
}

export interface CommitArgs {
  bpm: number;
  durationSec: number;
  defaults: RenderSettings;
  lanes: ForgeLane[];
  clips: ForgeClip[];
  overlaps: DerivedOverlap[];
  overlapParamsOf: (key: string) => OverlapParams;
  mix: MixSpec;
  master: MasterChain;
  decodeLanes: boolean;
  heads: Record<string, LatchHeadInfo>;
  cfgOf?: (s: RenderSettings) => number;
}

const FLAT_CURVES: [number, number, number] = [0, 0, 0];

/** A2A on with no drawn envelope is a FLAT curve at the noise level, not a null: the wire shape is
 *  `null | {render, envelope}` and validate_envelope 400s on a null envelope inside an a2a object
 *  (m8 plan:1437-1441). The per-clip noise level has no other home on this op. */
function clipEnvelope(a2a: { noise: number; envelope: Envelope | null }): Envelope {
  if (a2a.envelope) return a2a.envelope;
  const n = num(a2a.noise, 0, 1, "clip a2a noise");
  return { points: [n, n, n, n], curves: [...FLAT_CURVES] as [number, number, number] };
}

export function commitPayload(a: CommitArgs): Record<string, unknown> {
  const cfgOf = a.cfgOf ?? ((s: RenderSettings) => s.cfg_scale);
  num(a.bpm, 20, 300, "project_bpm");
  cap(a.durationSec, "commit");
  if (a.clips.length === 0) throw new PayloadError("nothing to commit — the arrangement has no clips");

  const indexes = a.lanes.map((l) => l.index).sort();
  if (indexes.length !== 4 || indexes.join(",") !== "0,1,2,3") {
    throw new PayloadError("lanes must list indexes 0, 1, 2, 3 exactly once");
  }

  const clips = a.clips.map((c) => {
    if (c.native_bpm != null) {
      const ratio = a.bpm / c.native_bpm;
      if (!(ratio >= 0.5 && ratio <= 2)) {
        throw new PayloadError(`clip ${c.id}: stretch ratio ${ratio.toFixed(3)} outside 0.5..2`);
      }
    }
    return {
      id: c.id,
      lane: c.lane,
      start_sec: num(c.start_sec, 0, CAP_SEC, `clip ${c.id} start_sec`),
      offset_sec: num(c.offset_sec, 0, 1e5, `clip ${c.id} offset_sec`),
      dur_sec: num(c.dur_sec, 1e-3, CAP_SEC, `clip ${c.id} dur_sec`),
      loop: c.loop === true,
      audio: c.audio,
      native_bpm: c.native_bpm,
      detune_cents: num(c.detune_cents, -100, 100, `clip ${c.id} detune`),
      // The client keeps {on, noise, envelope} + clip.render; the wire is null | {render, envelope}.
      a2a: c.a2a && c.a2a.on
        ? { render: renderWire(c.render, cfgOf(c.render)), envelope: clipEnvelope(c.a2a) }
        : null,
    };
  });

  // `arrangement.overlaps` is a DERIVED list with no params on it; the params live in a record
  // keyed by "<a>-<b>". M8 wants ONE list with both halves merged (Fact 2).
  const overlaps = a.overlaps.map((o) => {
    const p = a.overlapParamsOf(o.key);
    return {
      key: o.key, lane: o.lane, start_sec: o.start_sec, end_sec: o.end_sec,
      a_id: o.a_id, b_id: o.b_id, curve: p.curve, chroma_xfade: p.chroma_xfade,
      render: withLocal(p, cfgOf(p.render)),
    };
  });

  if (a.master.latch_on && !Object.prototype.hasOwnProperty.call(a.heads, a.master.head)) {
    throw new PayloadError(`unknown master head ${JSON.stringify(a.master.head)}`);
  }

  return {
    project_bpm: a.bpm,
    duration_sec: a.durationSec,              // top level, NOT inside `defaults` (Fact 1)
    defaults: renderWire(a.defaults, cfgOf(a.defaults)),
    lanes: a.lanes
      .slice()
      .sort((x, y) => x.index - y.index)
      .map((l) => ({
        index: l.index, muted: l.muted === true, solo: l.solo === true,
        gain: num(l.gain, 0, 2, "lane.gain"), chain: chainRequest(l.chain, a.heads),
      })),
    clips,
    overlaps,
    mix: {
      order: a.mix.order,
      nodes: {
        M1: { interp: a.mix.nodes.M1.interp, t: num(a.mix.nodes.M1.t, 0, 1, "mix node M1 t") },
        M2: { interp: a.mix.nodes.M2.interp, t: num(a.mix.nodes.M2.t, 0, 1, "mix node M2 t") },
        MX: { interp: a.mix.nodes.MX.interp, t: num(a.mix.nodes.MX.t, 0, 1, "mix node MX t") },
      },
      quad_weights: a.mix.quad_weights,
    },
    master: {
      latch_on: a.master.latch_on === true, head: a.master.head,
      gain: num(a.master.gain, 0, 120, "master.gain"), norm_on: a.master.norm_on === true,
    },
    decode_lanes: a.decodeLanes === true,
  };
}
