// Converts a v1 project (the pre-rename app, sa3-studio/src/lib/store.svelte.ts
// `toJSON()`) into ProjectV2 (spec §9.2). The real v1 shape was read directly
// from that file and from sa3-studio/src/lib/types.ts / musictime.ts -- NOT
// guessed from the spec's one paragraph (867-869), which names only the lane
// rename and the RenderSettings default-fill.
//
// Two things v1 has that ProjectV2's frozen ForgeClip cannot represent, and are
// therefore dropped rather than forced: the per-clip RenderOp and its
// op-specific fields (mixBPath, promptRegion, the longform arc-grammar
// `schedule` STRING, windowSec/overlapSec/xfadeSec, bendOps) -- ForgeClip has no
// `op` field at all (verified against M1 T3 and M4/M5's own plans); and a v1
// clip whose source is "empty" or "audio-file" AND which has no `serverPath`,
// which has no representable AudioRef (v1 itself never durably saved it -- its
// own toJSON() drops previewUrl for audio-file clips and loadJSON() already
// flags them for manual relink). With a serverPath it becomes a `path` ref.
//
// Never throws: this is the ONLY project-load path for an old save, so a
// garbage or partial input degrades to defaults rather than blocking the load.

import {
  BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT, MIX_DEFAULT,
} from "./defaults";
import type { AudioRef, ForgeClip, ForgeLane, ProjectV2, RenderSettings } from "./types";

const V1_LANE_IDS = ["drums", "bass", "other", "vocals"] as const;

/** v1's own SnapMode (musictime.ts:52) is bar|beat|1/8|1/16|1/32|edge|off -- already
 *  spelled 1/n, not bare digits, contrary to what M5's own Normative table and this
 *  milestone's brief both claim (see this task's WHY). Handled defensively both ways. */
const SNAP_V1_TO_V2: Record<string, string> = {
  off: "free",
  "8": "1/8", "16": "1/16", "32": "1/32",
  "1/8": "1/8", "1/16": "1/16", "1/32": "1/32",
  bar: "bar", beat: "beat", edge: "edge",
};

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function convertSnap(raw: unknown): ProjectV2["snap"] {
  if (typeof raw === "string" && raw in SNAP_V1_TO_V2) return SNAP_V1_TO_V2[raw];
  return "lane";   // ArrangementStore's own default (M5 T1)
}

function convertAudio(source: unknown): AudioRef | null {
  if (!isObj(source)) return null;
  switch (source.kind) {
    case "crop":
      return typeof source.cropId === "string" ? { kind: "crop", crop_id: source.cropId } : null;
    case "render":
      return typeof source.jobId === "string" && typeof source.filename === "string"
        ? { kind: "render", job_id: source.jobId, file: source.filename }
        : null;
    // "empty" and "audio-file" have no v2 AudioRef of their own -- see this task's WHY and
    // serverPathRef below.
    default:
      return null;
  }
}

/** v1's `serverPath` (types.ts:150-158): an absolute path ON THE SERVER, from a job's returned
 *  files or typed in by hand -- exactly v2's `{kind: "path"}` ref. */
function serverPathRef(clip: Record<string, unknown>): AudioRef | null {
  return typeof clip.serverPath === "string" && clip.serverPath !== ""
    ? { kind: "path", path: clip.serverPath }
    : null;
}

function convertRender(v1render: unknown, fallbackDurationSec: number): RenderSettings {
  const out = cloneRenderSettings(BASE_DEFAULTS);
  if (!isObj(v1render)) {
    out.duration_sec = fallbackDurationSec;
    return out;
  }
  if (typeof v1render.prompt === "string") out.prompt = v1render.prompt;
  if (typeof v1render.negativePrompt === "string") out.negative_prompt = v1render.negativePrompt;
  if (typeof v1render.steps === "number") out.steps = v1render.steps;
  if (typeof v1render.cfgScale === "number") out.cfg_scale = v1render.cfgScale;
  if (typeof v1render.seed === "number") out.seed = v1render.seed;
  if (typeof v1render.apgScale === "number") out.apg_scale = v1render.apgScale;
  if (typeof v1render.samplerType === "string") out.sampler_type = v1render.samplerType;
  // schedule (ScheduleSpec) and cfg_interval_progress have no v1 analogue --
  // v1's `schedule` field, when present, is a longform arc-grammar STRING, an
  // entirely different thing, and is not read here.
  out.duration_sec = fallbackDurationSec;
  return out;
}

function convertLanes(raw: unknown): ForgeLane[] {
  const lanes = asArray(raw);
  return [0, 1, 2, 3].map((index) => {
    const id = V1_LANE_IDS[index];
    const src = lanes.find((l) => isObj(l) && l.id === id);
    return {
      index: index as 0 | 1 | 2 | 3,
      name: `LANE ${index + 1}`,
      muted: isObj(src) && typeof src.muted === "boolean" ? src.muted : false,
      solo: isObj(src) && typeof src.solo === "boolean" ? src.solo : false,
      gain: isObj(src) && typeof src.gain === "number" ? src.gain : 1,
      chain: structuredClone(CHAIN_DEFAULTS),
    };
  });
}

function convertClips(raw: unknown): ForgeClip[] {
  const out: ForgeClip[] = [];
  for (const c of asArray(raw)) {
    if (!isObj(c)) continue;
    const audio = convertAudio(c.source) ?? serverPathRef(c);
    if (!audio) continue;   // "empty" / "audio-file" with no serverPath, or malformed -- dropped, see WHY
    const laneIndex = V1_LANE_IDS.indexOf((c.laneId as (typeof V1_LANE_IDS)[number]) ?? "drums");
    const durSec = typeof c.durationSec === "number" ? c.durationSec : 0;
    out.push({
      id: typeof c.id === "string" ? c.id : `clip_${out.length}`,
      lane: (laneIndex >= 0 ? laneIndex : 0) as 0 | 1 | 2 | 3,
      start_sec: typeof c.startSec === "number" ? c.startSec : 0,
      offset_sec: typeof c.offsetSec === "number" ? c.offsetSec : 0,
      dur_sec: durSec,
      loop: false,   // v1 has no loop concept
      audio,
      native_bpm: typeof c.bpm === "number" ? c.bpm : null,
      detune_cents: 0,   // v1 has no per-clip detune
      downbeats_sec: typeof c.downbeatSec === "number" ? [c.downbeatSec] : [],
      render: convertRender(c.render, durSec),
      a2a: null,   // v1 has no per-clip A2A state
      latentState: c.latentState === "valid" || c.latentState === "stale" ? c.latentState : "none",
      history: [],
      // previewUrl is intentionally never read (spec §9.2: previewAudio is
      // in-memory only, and the converter neither reads nor writes it). The
      // field itself is required on ForgeClip (M5 T10), so it is always null.
      previewAudio: null,
    });
  }
  return out;
}

export function convertProjectV1(raw: unknown): ProjectV2 {
  const data = isObj(raw) ? raw : {};
  const meter = isObj(data.meter) ? data.meter : {};
  return {
    version: 2,
    name: "",
    meter: {
      bpm: typeof meter.bpm === "number" ? meter.bpm : 120,
      beatsPerBar: typeof meter.beatsPerBar === "number" ? meter.beatsPerBar : 4,
    },
    snap: convertSnap(data.snap),
    view: { pxPerSec: typeof data.pxPerSec === "number" ? data.pxPerSec : 80, scrollSec: 0 },
    lanes: convertLanes(data.lanes),
    clips: convertClips(data.clips),
    overlaps: {},
    mix: structuredClone(MIX_DEFAULT),
    master: structuredClone(MASTER_DEFAULT),
    defaults: cloneRenderSettings(BASE_DEFAULTS),
    // v1 records no backbone (and no ckpt). This value only fills the required field -- it is NOT
    // a stage request: Task 9's loader applies converted v1 input with `restoreModel: false`, so
    // the current stage and ckpt stay, no model rebuild runs, and a later SAVE records whatever
    // backbone is actually loaded (critic pass 2 #7 -- emitting a fixed value here used to flip a
    // POST session to BASE and rebuild the server model on every v1 import).
    backbone: "medium-base",
    ckpt_path: null,
    renders: [],
    mixdown: null,
    preview: null,
    ui: { bottomTab: "prompt", modules: ["files", "lane-chain"], sideOpen: true, terminal: "pane" },
  };
}
