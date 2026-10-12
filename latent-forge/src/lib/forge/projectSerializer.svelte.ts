// Turns the live stores into ProjectV2 (spec §9.2) and back, and the narrower
// master-preset slice (spec §9.3). Reads/writes the real singletons directly,
// the same pattern every other store-adjacent module in this codebase uses.
//
// `.svelte.ts` because of $state.snapshot: structuredClone throws DataCloneError
// on a $state proxy (Global Constraint #7), and every arrangement/settings field
// read here IS one. $state.snapshot reads through the proxies, which is also why
// App's autosave $effect, which calls serializeProject, depends on every field.
import {
  arrangement, MAX_PX_PER_SEC, MIN_PX_PER_SEC,
} from "../stores/arrangement.svelte";
import { settings, STAGE_BACKBONE, STAGE_FIELDS, type ModelStage } from "../stores/settings.svelte";
import { view } from "../stores/view.svelte";
import { history } from "../render/history.svelte";
import { CLIP_OPS } from "./types";
import type { RenderHistoryEntry } from "./types";
import { durableChain } from "../chains/modulePresets";
import { SNAP_MODES } from "../math/snap";
import { BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT, POST_DEFAULTS } from "./defaults";
import { isAudioRef, isEnvelope } from "./guards";
import type {
  ForgeClip, ForgeLane, LaneChain, MasterChain, MixSpec, OverlapParams, ProjectV2, RenderSettings,
} from "./types";

/** `backbone` overrides settings.backboneId: SessionController's pin (Task 9 WHY, step 8) keeps a
 *  loaded session's own backbone in what is saved while a failed rebuild has the client reverted. */
export function serializeProject(opts: { name: string; backbone?: string }): ProjectV2 {
  const overlaps: Record<string, OverlapParams> = {};
  // peek, not overlapParams: this runs inside App's autosave $effect, and must not write.
  for (const o of arrangement.overlaps) {
    overlaps[o.key] = $state.snapshot(arrangement.peekOverlapParams(o.key)) as OverlapParams;
  }

  return {
    version: 2,
    name: opts.name,
    meter: { bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar },
    snap: arrangement.snap,
    view: { pxPerSec: arrangement.pxPerSec, scrollSec: arrangement.scrollSec },
    // durableChain: lora.slot is a transient /slots resolution, never saved (contract table).
    lanes: ($state.snapshot(arrangement.lanes) as ForgeLane[]).map((l) => ({ ...l, chain: durableChain(l.chain) })),
    // previewAudio is in-memory only (spec §9.2 "Not serialised", M1 Normative row): the field is
    // required on ForgeClip, so it is written as null -- the live ref never reaches the JSON.
    clips: ($state.snapshot(arrangement.clips) as ForgeClip[]).map((c) => ({ ...c, previewAudio: null })),
    overlaps,
    mix: $state.snapshot(arrangement.mix) as MixSpec,
    master: $state.snapshot(arrangement.master) as MasterChain,
    defaults: $state.snapshot(settings.defaults) as RenderSettings,
    backbone: opts.backbone ?? settings.backboneId,
    ckpt_path: settings.ckptPath,
    // M9 T3 owns these. $state.snapshot, like every other store read here (Global Constraint #7:
    // `$state.snapshot` only in a .svelte.ts file -- which is why this module is one).
    renders: $state.snapshot(history.renders) as RenderHistoryEntry[],
    mixdown: history.mixdown,
    preview: history.preview,
    ui: $state.snapshot(view.snapshotUi()) as ProjectV2["ui"],
  };
}

/** STAGE_BACKBONE inverted: "medium" -> POST, "medium-base" -> BASE, anything else -> null. */
function stageForBackbone(backbone: string): ModelStage | null {
  const hit = (Object.keys(STAGE_BACKBONE) as ModelStage[]).find((s) => STAGE_BACKBONE[s] === backbone);
  return hit ?? null;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

const RENDER_KINDS = ["gen", "a2a", "inpaint", "mix"];

/** Every field the preview container, the MIXDOWN slot and refOf dereference. */
function isRenderEntry(v: unknown): boolean {
  return isObj(v) && typeof v.job_id === "string" && typeof v.forge_job_id === "string"
    && typeof v.file === "string" && typeof v.label === "string"
    && RENDER_KINDS.includes(v.kind as string) && isNum(v.dur_sec)
    && isStrOrNull(v.source_clip_id) && isNum(v.created);
}

/** null, or an integer that addresses a row of `renders`. A float or an out-of-range index would
 *  leave the MIXDOWN slot pointing at nothing. */
function isRenderIndex(v: unknown, renders: unknown[]): boolean {
  return v === null || (typeof v === "number" && Number.isInteger(v) && v >= 0 && v < renders.length);
}

function isNum(v: unknown): boolean {
  return typeof v === "number" && Number.isFinite(v);
}

const isBool = (v: unknown): boolean => typeof v === "boolean";
const isStrOrNull = (v: unknown): boolean => v === null || typeof v === "string";
const isLaneIndex = (v: unknown): boolean => [0, 1, 2, 3].includes(v as number);

// Shape checks for validateProjectV2 / validateMasterPreset, one per M1 type (M1 plan lines
// 428-624): every saved field of LaneChain, ForgeLane, ForgeClip (not the in-memory previewAudio),
// OverlapParams, MixSpec and MasterChain.

/** RenderSettings, as far as cloneRenderSettings dereferences it (the nested objects it copies). */
function isRender(r: unknown): boolean {
  return isObj(r) && isObj(r.schedule) && Array.isArray(r.cfg_interval_progress);
}

function isLaneChain(c: unknown): boolean {
  if (!isObj(c) || !isLatchBlock(c) || !isObj(c.film) || !isObj(c.lora)) return false;
  const film = c.film;
  const lora = c.lora;
  return isBool(c.film_on) && isBool(c.lora_on) && isBool(c.bungee_on) && isNum(c.semitones)
    && isStrOrNull(film.ckpt) && isNum(film.gain) && isNum(film.value)
    && isStrOrNull(lora.ckpt_path) && (lora.slot === null || isNum(lora.slot)) && isNum(lora.strength);
}

function isA2A(a: unknown): boolean {
  return a === null || (isObj(a) && isBool(a.on) && isNum(a.noise) && isEnvelope(a.envelope));
}

/** The clip-layout fields a master preset carries (and every clip has). */
function isClipLayout(c: Record<string, unknown>): boolean {
  return typeof c.id === "string" && isLaneIndex(c.lane) && isNum(c.start_sec) && isNum(c.offset_sec)
    && isNum(c.dur_sec) && isBool(c.loop) && (c.native_bpm === null || isNum(c.native_bpm))
    && isNum(c.detune_cents) && isA2A(c.a2a);
}

/** A v2 file written before M9 has no `op`; refusing it would stop M9 opening its own earlier sessions. */
function isClipOp(v: unknown): boolean {
  return v === undefined || v === null || (typeof v === "string" && (CLIP_OPS as readonly string[]).includes(v));
}

function isClip(c: unknown): boolean {
  return isObj(c) && isClipLayout(c) && isAudioRef(c.audio) && isRender(c.render) && isClipOp(c.op)
    && Array.isArray(c.downbeats_sec) && c.downbeats_sec.every(isNum)
    && ["none", "valid", "stale"].includes(c.latentState as string)
    && Array.isArray(c.history) && c.history.every(isAudioRef);
}

function isOverlapParams(o: unknown): boolean {
  return isObj(o) && isEnvelope(o.curve) && isBool(o.chroma_xfade) && isBool(o.override)
    && isNum(o.steps) && isNum(o.cfg) && isRender(o.render);
}

function isMix(m: unknown): boolean {
  if (!isObj(m) || !isObj(m.nodes) || !Array.isArray(m.quad_weights)) return false;
  const nodes = m.nodes;
  return ["tree", "cascade", "quad"].includes(m.order as string)
    && (["M1", "M2", "MX"] as const).every((k) => {
      const n = nodes[k];
      return isObj(n) && (n.interp === "lerp" || n.interp === "slerp") && isNum(n.t);
    })
    && m.quad_weights.length === 4 && m.quad_weights.every(isNum);
}

/** The LatCH part a lane's chain and the master's chain share. */
function isLatchBlock(b: Record<string, unknown>): boolean {
  const h = b.hparams;
  return isBool(b.latch_on) && Array.isArray(b.slots) && b.slots.length === 2
    && b.slots.every((s: unknown) => isObj(s) && typeof s.head === "string" && typeof s.kind === "string"
      && isNum(s.value) && isNum(s.weight) && isNum(s.start_pct) && isNum(s.end_pct))
    && isObj(h) && isNum(h.rho) && isNum(h.mu) && isNum(h.gamma) && isNum(h.n_iter) && isBool(h.log_norms);
}

/** A master saved before 2026-10-09: one head and one gain, no slots. Still a valid file. */
function isLegacyMaster(m: Record<string, unknown>): boolean {
  return isBool(m.latch_on) && typeof m.head === "string" && isNum(m.gain) && isBool(m.norm_on) && m.slots === undefined;
}

function isMaster(m: unknown): boolean {
  if (!isObj(m)) return false;
  if (isLegacyMaster(m)) return true;
  return isLatchBlock(m) && isBool(m.norm_on) && isNum(m.noise);
}

/**
 * The master chain as the app holds it. A legacy master (one head, one gain) has nothing to carry into
 * the lane-style slots -- a gradient step has no target or window -- so it comes back as the defaults
 * with its LatCH switched off and its normalise toggle kept; the LatCH it had would otherwise have
 * silently changed meaning into a guided pass.
 */
export function normalizeMaster(raw: MasterChain | Record<string, unknown>): MasterChain {
  if (isLegacyMaster(raw as Record<string, unknown>)) {
    return { ...structuredClone(MASTER_DEFAULT), norm_on: (raw as { norm_on: boolean }).norm_on };
  }
  return structuredClone(raw as MasterChain);
}

/**
 * A `version: 2` object from the server or a file, checked as a WHOLE before applyProject touches
 * any store (critic pass 2 #1). Every field applyProject -- or a reader it hands data to
 * (cloneRenderSettings, view.restoreUi, the lane-chain, clip, overlap, mix and master components)
 * -- dereferences is checked, down to each lane, clip, overlap entry, mix node and master field
 * (critic pass 3 #8: `ui: {modules: "files"}` used to pass and then throw in restoreUi, the LAST
 * line of the apply, after every store was written). So an object that passes cannot throw
 * half-way through the apply. Throws naming the first bad field; returns the same object, typed.
 */
export function validateProjectV2(raw: unknown): ProjectV2 {
  const bad = (field: string) => new Error(`not a v2 project: ${field} is missing or the wrong type`);
  if (!isObj(raw) || raw.version !== 2) throw bad("version");
  const p = raw;
  if (!isObj(p.meter) || !isNum(p.meter.bpm) || !isNum(p.meter.beatsPerBar)) throw bad("meter");
  if (!SNAP_MODES.some((m) => m.value === p.snap)) throw bad("snap");
  if (!isObj(p.view) || !isNum(p.view.pxPerSec) || !isNum(p.view.scrollSec)) throw bad("view");
  if (!Array.isArray(p.lanes) || p.lanes.length !== 4) throw bad("lanes");
  p.lanes.forEach((l: unknown, i: number) => {
    if (!isObj(l) || !isLaneIndex(l.index) || typeof l.name !== "string" || !isNum(l.gain)
      || !isBool(l.muted) || !isBool(l.solo)) {
      throw bad(`lanes[${i}]`);
    }
    if (!isLaneChain(l.chain)) throw bad(`lanes[${i}].chain`);
  });
  if (!Array.isArray(p.clips)) throw bad("clips");
  p.clips.forEach((c: unknown, i: number) => {
    if (!isClip(c)) throw bad(`clips[${i}]`);
  });
  if (!isObj(p.overlaps)) throw bad("overlaps");
  for (const [key, o] of Object.entries(p.overlaps)) {
    if (!isOverlapParams(o)) throw bad(`overlaps.${key}`);
  }
  if (!isMix(p.mix)) throw bad("mix");
  if (!isMaster(p.master)) throw bad("master");
  if (!isRender(p.defaults)) throw bad("defaults");
  if (typeof p.backbone !== "string") throw bad("backbone");
  if (!isStrOrNull(p.ckpt_path)) throw bad("ckpt_path");
  // M1's restoreUi calls `.filter` on modules; the other three it reads through includes()/Boolean().
  if (!Array.isArray(p.renders)) throw bad("renders");
  p.renders.forEach((r: unknown, i: number) => {
    if (!isRenderEntry(r)) throw bad(`renders[${i}]`);
  });
  if (!isRenderIndex(p.mixdown, p.renders)) throw bad("mixdown");
  if (!isRenderIndex(p.preview, p.renders)) throw bad("preview");
  if (!isObj(p.ui) || !Array.isArray(p.ui.modules)) throw bad("ui");
  return raw as unknown as ProjectV2;
}

/** M4's own field copy (settings.svelte.ts `assign`), for STAGE_FIELDS: a typed assignment per key. */
function copyField<K extends keyof RenderSettings>(into: RenderSettings, from: RenderSettings, k: K): void {
  into[k] = from[k];
}

/** `project` is plain data (a server response, a parsed file, or serializeProject's output) that
 *  has already passed validateProjectV2 or come out of convertProjectV1. `restoreModel: false`
 *  (converted v1 input) keeps the current stage and ckpt: v1 records neither (critic pass 2 #7) --
 *  and so keeps that stage's STAGE_FIELDS too (critic pass 3 #7). */
export function applyProject(project: ProjectV2, opts: { restoreModel?: boolean } = {}): void {
  // Nothing selected survives a load: the old selection's clip/overlap key may not exist here, and a
  // stale overlap key would keep OVERLAP-INPAINT mounted (critic pass 2 #5).
  view.clearSelection();
  // Overlap params are replaced wholesale, not merged: a key this project does not set must not
  // inherit the previous project's edits (a v1 import keeps its clip ids, so keys can repeat).
  arrangement.clearOverlapParams();
  arrangement.setBpm(project.meter.bpm);
  arrangement.beatsPerBar = project.meter.beatsPerBar;
  arrangement.setSnap(project.snap as Parameters<typeof arrangement.setSnap>[0]);
  // arrangement has no setPxPerSec (M5 T1): assign directly, clamped exactly as zoomBy clamps.
  arrangement.pxPerSec = Math.max(MIN_PX_PER_SEC, Math.min(MAX_PX_PER_SEC, project.view.pxPerSec));
  arrangement.setScrollSec(project.view.scrollSec);
  arrangement.lanes.splice(0, arrangement.lanes.length, ...structuredClone(project.lanes));
  arrangement.clips.splice(
    0, arrangement.clips.length,
    ...structuredClone(project.clips).map((c) => ({ ...c, op: c.op ?? null, previewAudio: null })),
  );
  arrangement.mix = structuredClone(project.mix);
  arrangement.master = normalizeMaster(project.master);
  for (const [key, params] of Object.entries(project.overlaps)) {
    arrangement.setOverlapParams(key, structuredClone(params));
  }
  // backboneId is a getter over settings.stage (M4 plan line 427), so restoring `backbone` means
  // restoring the stage. Assigned directly, NOT via setStage(): setStage overwrites defaults'
  // steps/sampler/schedule with the stage defaults, and the saved defaults (next line) must win.
  // The caller (SessionController, step 8) rebuilds the server model if this changed it.
  if (opts.restoreModel ?? true) {
    const stage = stageForBackbone(project.backbone);
    if (stage) settings.stage = stage;
    settings.ckptPath = project.ckpt_path;
  }
  settings.defaults = cloneRenderSettings(project.defaults);
  if (!(opts.restoreModel ?? true)) {
    // The stage stayed, so its steps/sampler/schedule stay matched to it, exactly as M4's setStage
    // keeps them: the converter fills `defaults` from BASE_DEFAULTS, which under POST would put 24
    // Euler steps on the model schedule into a distilled session.
    const stageDefaults = cloneRenderSettings(settings.stage === "POST" ? POST_DEFAULTS : BASE_DEFAULTS);
    for (const k of STAGE_FIELDS) copyField(settings.defaults, stageDefaults, k);
  }
  // Wholesale, like overlaps: a previous session's renders must not survive into this one, and
  // `restore` drops an index the loaded list cannot address.
  history.restore(project.renders, project.mixdown, project.preview);
  view.restoreUi(project.ui);
}

// ---------------------------------------------------------- master preset (§9.3)

export interface MasterPresetPayload {
  lanes: { chain: LaneChain }[];
  clips: {
    id: string; lane: 0 | 1 | 2 | 3; start_sec: number; offset_sec: number; dur_sec: number;
    loop: boolean; native_bpm: number | null; detune_cents: number; a2a: ForgeClip["a2a"];
  }[];
  mix: MixSpec;
  master: MasterChain;
  defaults: { schedule: RenderSettings["schedule"]; prompt: string };
}

/**
 * Spec §9.3's own enumeration, taken literally rather than as "ProjectV2 minus
 * two fields" (the two readings do not fully reconcile -- see this task's WHY).
 * No `audio`, no `render.steps`/`cfg_scale`/etc: those belong to the separate
 * `render`-level preset (M4), and re-including them here would make the two
 * levels redundant.
 */
export function buildMasterPresetPayload(): MasterPresetPayload {
  return {
    lanes: arrangement.lanes.map((l) => ({ chain: durableChain($state.snapshot(l.chain) as LaneChain) })),
    clips: arrangement.clips.map((c) => ({
      id: c.id, lane: c.lane, start_sec: c.start_sec, offset_sec: c.offset_sec,
      dur_sec: c.dur_sec, loop: c.loop, native_bpm: c.native_bpm, detune_cents: c.detune_cents,
      a2a: $state.snapshot(c.a2a) as ForgeClip["a2a"],
    })),
    mix: $state.snapshot(arrangement.mix) as MixSpec,
    master: $state.snapshot(arrangement.master) as MasterChain,
    defaults: {
      schedule: $state.snapshot(settings.defaults.schedule) as RenderSettings["schedule"],
      prompt: settings.defaults.prompt,
    },
  };
}

/**
 * A master preset from the server, checked as a WHOLE before applyMasterPreset writes anything
 * (critic pass 3 #12): a payload missing `defaults` used to throw on the last two lines, after the
 * lanes, clips, mix and master were already recalled -- and an armed session then autosaved that
 * half recall. Every field applyMasterPreset writes is checked. Throws naming the first bad field.
 */
export function validateMasterPreset(raw: unknown): MasterPresetPayload {
  const bad = (field: string) => new Error(`not a master preset: ${field} is missing or the wrong type`);
  if (!isObj(raw)) throw bad("payload");
  if (!Array.isArray(raw.lanes) || raw.lanes.length !== 4) throw bad("lanes");
  raw.lanes.forEach((l: unknown, i: number) => {
    if (!isObj(l) || !isLaneChain(l.chain)) throw bad(`lanes[${i}].chain`);
  });
  if (!Array.isArray(raw.clips)) throw bad("clips");
  raw.clips.forEach((c: unknown, i: number) => {
    if (!isObj(c) || !isClipLayout(c)) throw bad(`clips[${i}]`);
  });
  if (!isMix(raw.mix)) throw bad("mix");
  if (!isMaster(raw.master)) throw bad("master");
  if (!isObj(raw.defaults) || !isObj(raw.defaults.schedule) || typeof raw.defaults.prompt !== "string") {
    throw bad("defaults");
  }
  return raw as unknown as MasterPresetPayload;
}

/** Recall replaces the whole slice (spec §9.3): matched by clip id within the
 *  CURRENT session's arrangement, since a master preset is a snapshot of one
 *  session's layout, not a transplant of clips into a different one. A clip id
 *  the preset names that no longer exists is skipped, not an error.
 *  `payload` is plain data that passed validateMasterPreset (a server response),
 *  or buildMasterPresetPayload's output. */
export function applyMasterPreset(payload: MasterPresetPayload): void {
  payload.lanes.forEach((l, i) => {
    if (arrangement.lanes[i]) arrangement.lanes[i].chain = structuredClone(l.chain ?? CHAIN_DEFAULTS);
  });
  for (const saved of payload.clips) {
    const clip = arrangement.clips.find((c) => c.id === saved.id);
    if (!clip) continue;
    clip.lane = saved.lane;
    clip.start_sec = saved.start_sec;
    clip.offset_sec = saved.offset_sec;
    clip.dur_sec = saved.dur_sec;
    clip.loop = saved.loop;
    clip.native_bpm = saved.native_bpm;
    clip.detune_cents = saved.detune_cents;
    clip.a2a = structuredClone(saved.a2a);
  }
  arrangement.mix = structuredClone(payload.mix);
  arrangement.master = normalizeMaster(payload.master);
  settings.defaults.schedule = structuredClone(payload.defaults.schedule);
  settings.defaults.prompt = payload.defaults.prompt;
}

/**
 * What counts as work for step 3's "replace unsaved work?" (critic pass 3 #3): everything saved
 * except the name, the viewport, the ui slice and the model -- scrolling, opening a module or a
 * STAGE revert is not work anyone would lose.
 *
 * M9 T3 adds `renders`/`mixdown`/`preview` to that list. They are OUTPUT, not edits: the audio a
 * history entry points at is a file the server already wrote: its job record (payload included) is
 * archived under OUT_DIR/_forge_jobs and served by /forge/jobs/{id} across restarts, and the audio by
 * /forge/audio with a `render` ref. (The FILES `renders` root lists only out_*.wav, so a commit's
 * mix.wav is NOT browsable there -- corrected in review 2026-10-01.) Counting them would make the
 * prompt fire after every single render -- including the render the user is about to drag onto a
 * lane. They are still serialised and restored; only this question ignores them. (M9 open question A5.)
 */
export function unsavedWorkKey(p: ProjectV2): string {
  return JSON.stringify({
    ...p, name: "", view: null, ui: null, backbone: "", ckpt_path: null,
    renders: null, mixdown: null, preview: null,
  });
}
