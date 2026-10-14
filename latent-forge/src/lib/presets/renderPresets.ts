// Last edited: WINTERMUTE 2026-10-13 — render presets recall duration_sec; test-prompt group; preset comments
import { LENGTH_CAP_SEC } from "../forge/defaults";
import { RANGES, SCHEDULE_SHAPES } from "../sampling/scheduleRules";
import type { RenderSettings, ScheduleSpec } from "../forge/types";

export type PresetLevel = "prompt" | "render";

/**
 * A preset is a file at OUT_DIR/_forge/presets/<level>/<name>.json (6.3), so the
 * name is a filename. 6.3 states this regex for session names and gives presets
 * the same storage shape; applying it here is the inference, and it is the
 * conservative direction -- a name this rejects is one the server would have to
 * reject too for the path to be safe.
 */
export const PRESET_NAME_RE = /^[A-Za-z0-9._-]{1,80}$/;

export const RENDER_GROUP_LABEL = "render";
export const PROMPT_GROUP_LABEL = "prompt only";
/** Render presets written by eval/forge/make_test_prompt_presets.py: one per model-matrix test prompt. */
export const TEST_PREFIX = "test-";
export const TEST_GROUP_LABEL = "test prompts";

export interface PresetOption {
  level: PresetLevel;
  name: string;
  group: string;
}

export interface PresetApplyResult {
  applied: string[];
  rejected: string[];
}

export function isValidPresetName(name: string): boolean {
  return PRESET_NAME_RE.test(name) && !name.includes("..");
}

/** 4.5: render presets, then prompt presets under a `prompt only` group. The model-matrix test
 *  prompts are render presets too, listed last under their own group. */
export function presetOptions(renderNames: string[], promptNames: string[]): PresetOption[] {
  const isTest = (n: string) => n.startsWith(TEST_PREFIX);
  return [
    ...renderNames.filter((n) => !isTest(n)).map((name) => ({ level: "render" as const, name, group: RENDER_GROUP_LABEL })),
    ...promptNames.map((name) => ({ level: "prompt" as const, name, group: PROMPT_GROUP_LABEL })),
    ...renderNames.filter(isTest).map((name) => ({ level: "render" as const, name, group: TEST_GROUP_LABEL })),
  ];
}

/** A preset's comment: its `notes` string, "" when it has none. Shown beside the select after a
 *  recall. It is NOT copied into the target's own notes (RenderSettings.notes), which a recall
 *  must never overwrite. */
export function presetComment(body: unknown): string {
  return isPlainObject(body) && typeof body.notes === "string" ? body.notes : "";
}

export function renderPresetBody(s: RenderSettings): RenderSettings {
  return {
    ...s,
    schedule: { ...s.schedule },
    cfg_interval_progress: [s.cfg_interval_progress[0], s.cfg_interval_progress[1]],
  };
}

export function promptPresetBody(s: RenderSettings): { prompt: string; negative_prompt: string } {
  return { prompt: s.prompt, negative_prompt: s.negative_prompt };
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * `sentinel` is an exact value admitted alongside the range, and exactly one field uses
 * it: SEED. M1's own BASE_DEFAULTS/POST_DEFAULTS ship `seed: -1`, the "let the server pick
 * one" sentinel, which sits outside RANGES.seed's `{min: 0}`. Without the exemption a
 * preset saved from the app's untouched defaults -- the commonest preset there is -- comes
 * back reading as malformed, and a round trip of the defaults rejects its own seed.
 * -1 is admitted; -5 is still rejected, because the sentinel is one value, not a floor.
 */
function numberOk(
  v: unknown,
  r: { min: number; max: number; int?: boolean },
  sentinel?: number,
): v is number {
  if (typeof v !== "number" || !Number.isFinite(v)) return false;
  if (sentinel !== undefined && v === sentinel) return true;
  if (r.int && !Number.isInteger(v)) return false;
  return v >= r.min && v <= r.max;
}

export function applyPromptPreset(into: RenderSettings, body: unknown): PresetApplyResult {
  if (!isPlainObject(body)) return { applied: [], rejected: ["<body>"] };
  const applied: string[] = [];
  const rejected: string[] = [];
  for (const k of ["prompt", "negative_prompt"] as const) {
    if (!(k in body)) continue;
    if (typeof body[k] === "string") {
      into[k] = body[k] as string;
      applied.push(k);
    } else {
      rejected.push(k);
    }
  }
  return { applied, rejected };
}

/** SEED's `-1` is M1's server-resolve sentinel; see `numberOk`. */
export const SEED_SENTINEL = -1;

const NUMERIC_TOP: {
  key: keyof RenderSettings;
  range: keyof typeof RANGES;
  sentinel?: number;
}[] = [
  { key: "steps", range: "steps" },
  { key: "cfg_scale", range: "cfg_scale" },
  { key: "seed", range: "seed", sentinel: SEED_SENTINEL },
  { key: "scale_phi", range: "scale_phi" },
];

const NUMERIC_SCHEDULE: { key: keyof ScheduleSpec; range: keyof typeof RANGES }[] = [
  { key: "rho", range: "rho" },
  { key: "sigma_min", range: "sigma_min" },
  { key: "lam_min", range: "lam_min" },
  { key: "lam_max", range: "lam_max" },
  { key: "plateaus", range: "plateaus" },
  { key: "tilt", range: "tilt" },
];

/**
 * A preset file is hand-editable JSON on a disk this client does not own, so it
 * is DATA and every field is checked before it lands. A bad field is named in
 * `rejected` and the existing value stays; the rest of the preset still applies,
 * because half a recall a person can see is more useful than a silent refusal.
 *
 * Unknown keys are ignored rather than rejected -- a preset written by a later
 * milestone must not read as corrupt here. The allow-list also means `__proto__`
 * and friends are never assigned.
 */
export function applyRenderPreset(into: RenderSettings, body: unknown): PresetApplyResult {
  if (!isPlainObject(body)) return { applied: [], rejected: ["<body>"] };
  const applied: string[] = [];
  const rejected: string[] = [];

  const text = applyPromptPreset(into, body);
  applied.push(...text.applied);
  rejected.push(...text.rejected);

  for (const { key, range, sentinel } of NUMERIC_TOP) {
    if (!(key in body)) continue;
    const v = body[key];
    if (numberOk(v, RANGES[range], sentinel)) {
      (into[key] as number) = v;
      applied.push(key);
    } else {
      rejected.push(key);
    }
  }

  // duration_sec: 9.3 says a render preset recalls every txt2audio parameter, and LENGTH is one.
  // It was missing here, so a master preset's render length never landed (found 2026-10-13).
  if ("duration_sec" in body) {
    const d = body.duration_sec;
    if (typeof d === "number" && Number.isFinite(d) && d > 0 && d <= LENGTH_CAP_SEC) {
      into.duration_sec = d;
      applied.push("duration_sec");
    } else {
      rejected.push("duration_sec");
    }
  }

  if ("apg_scale" in body) {
    if (typeof body.apg_scale === "number" && Number.isFinite(body.apg_scale)) {
      into.apg_scale = body.apg_scale;
      applied.push("apg_scale");
    } else {
      rejected.push("apg_scale");
    }
  }

  if ("sampler_type" in body) {
    const v = body.sampler_type;
    if (v === null || typeof v === "string") {
      into.sampler_type = v;
      applied.push("sampler_type");
    } else {
      rejected.push("sampler_type");
    }
  }

  if ("cfg_interval_progress" in body) {
    const v = body.cfg_interval_progress;
    const r = RANGES.cfg_interval;
    if (
      Array.isArray(v) && v.length === 2 &&
      numberOk(v[0], r) && numberOk(v[1], r) && v[0] <= v[1]
    ) {
      into.cfg_interval_progress = [v[0], v[1]];
      applied.push("cfg_interval_progress");
    } else {
      rejected.push("cfg_interval_progress");
    }
  }

  if ("schedule" in body) {
    const sch = body.schedule;
    if (!isPlainObject(sch)) {
      rejected.push("schedule");
    } else {
      if ("shape" in sch) {
        if (typeof sch.shape === "string" && (SCHEDULE_SHAPES as readonly string[]).includes(sch.shape)) {
          into.schedule.shape = sch.shape as ScheduleSpec["shape"];
          applied.push("schedule.shape");
        } else {
          rejected.push("schedule.shape");
        }
      }
      if ("stepped" in sch) {
        if (typeof sch.stepped === "boolean") {
          into.schedule.stepped = sch.stepped;
          applied.push("schedule.stepped");
        } else {
          rejected.push("schedule.stepped");
        }
      }
      for (const { key, range } of NUMERIC_SCHEDULE) {
        if (!(key in sch)) continue;
        const v = sch[key];
        if (numberOk(v, RANGES[range])) {
          (into.schedule[key] as number) = v;
          applied.push(`schedule.${key}`);
        } else {
          rejected.push(`schedule.${key}`);
        }
      }
    }
  }

  return { applied, rejected };
}

/**
 * Presets from the render server's own store (GET /presets, eval/presets/*.json), e.g. the
 * v7 transition recipes. They carry a /generate payload, not RenderSettings: `duration`
 * instead of `duration_sec`, and the adapter as `dora: {ckpt_path, strength}`.
 */
export const SERVER_GROUP_LABEL = "server recipes";

export interface ServerPresetApplyResult extends PresetApplyResult {
  /** The adapter the recipe was rendered with; undefined when the recipe names none. */
  ckptPath?: string;
}

export function applyServerPreset(into: RenderSettings, body: unknown): ServerPresetApplyResult {
  if (!isPlainObject(body) || !isPlainObject(body.payload)) return { applied: [], rejected: ["<body>"] };
  const payload = body.payload;
  const r: ServerPresetApplyResult = applyRenderPreset(into, payload);
  if ("duration" in payload) {
    const d = payload.duration;
    if (typeof d === "number" && Number.isFinite(d) && d > 0 && d <= LENGTH_CAP_SEC) {
      into.duration_sec = d;
      r.applied.push("duration");
    } else {
      r.rejected.push("duration");
    }
  }
  const dora = payload.dora;
  if (isPlainObject(dora) && typeof dora.ckpt_path === "string" && dora.ckpt_path !== "") {
    r.ckptPath = dora.ckpt_path;
    r.applied.push("dora.ckpt_path");
  }
  return r;
}
