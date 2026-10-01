import { LENGTH_CAP_SEC } from "../forge/defaults";
import type { JobOp, RenderHistoryEntry, Target } from "../forge/types";
import { applyRenderPreset } from "../presets/renderPresets";
import { RANGES } from "../sampling/scheduleRules";
import { settings } from "../stores/settings.svelte";

export const NO_PREVIEW_HINT = "load a render from HISTORY first";
export const RENDER_RUNNING_HINT = "a render is running";
export const NO_SETTINGS_HINT = "that render carries no settings";
export const NOT_THIS_CLIP_HINT = "select the clip this render was made from";

export interface PayloadSettings {
  /** Exactly the keys applyRenderPreset may look at, or null when the op has none. */
  body: Record<string, unknown> | null;
  /** Seconds, already validated as finite and in range — or null when the op has no length. */
  durationSec: number | null;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** A length is only a length if it is a finite number inside RANGES.length_sec. An old job record
 *  from a server that has since changed its mind is data, not a promise. */
function durationOf(v: unknown): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  if (v < RANGES.length_sec.min || v > LENGTH_CAP_SEC) return null;
  return v;
}

function pick(src: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of keys) if (k in src) out[k] = src[k];
  return out;
}

/** Reduce a JobRecord.payload to the settings USE SETTINGS may copy. Writer A T1 builds each of
 *  these shapes; this is their one inverse, and it is total — `payload` is `unknown`. */
export function payloadSettings(op: JobOp, payload: unknown): PayloadSettings {
  if (!isObj(payload)) return { body: null, durationSec: null };

  switch (op) {
    case "generate": {
      // generatePayload: { ...renderWire(s, cfg), duration }. `duration` is not a RenderSettings key
      // and applyRenderPreset would ignore it silently, so it is removed rather than left to be.
      const { duration, ...rest } = payload;
      return { body: rest, durationSec: durationOf(duration) };
    }
    case "a2a_clip":
    case "inpaint": {
      // Both carry a nested `render` (M8 parse_render's key set) and take their length from the
      // clip or the region, never from settings.
      const render = payload.render;
      return { body: isObj(render) ? render : null, durationSec: null };
    }
    case "commit":
      // Lanes, clips and overlaps each carry their own render block; there is no session-wide one.
      return { body: null, durationSec: durationOf(payload.duration_sec) };
    case "longform": {
      // The ARC string is `prompt_arc` (formerly `schedule`); neither is a ScheduleSpec, and neither
      // is picked below, so no arc string can reach applyRenderPreset.
      const body = pick(payload, ["steps", "cfg_scale", "seed"]);
      return {
        body: Object.keys(body).length > 0 ? body : null,
        durationSec: durationOf(payload.duration),
      };
    }
    case "bend": {
      const body = pick(payload, ["seed"]);
      return { body: Object.keys(body).length > 0 ? body : null, durationSec: null };
    }
    default:
      // decode, and the a2a_track / a2a_mix ops M9's UI never submits.
      return { body: null, durationSec: null };
  }
}

export interface ApplyOutcome {
  applied: string[];
  rejected: string[];
  /** The length actually written, after the clamp — or null when nothing was written. */
  lengthSec: number | null;
}

export function applyPayloadSettings(target: Target, ps: PayloadSettings): ApplyOutcome {
  const out: ApplyOutcome = { applied: [], rejected: [], lengthSec: null };

  if (ps.body !== null) {
    // editable(), not current(): M4's Normative row says current() reads and editable() returns the
    // object a write must mutate. applyRenderPreset mutates in place.
    const result = applyRenderPreset(settings.editable(target), ps.body);
    out.applied = result.applied;
    out.rejected = result.rejected;
  }

  if (ps.durationSec !== null) {
    // M4 T10's clamp, verbatim in effect: the single owner of duration_sec writes it through patch().
    const sec = Math.min(LENGTH_CAP_SEC, Math.max(RANGES.length_sec.min, ps.durationSec));
    settings.patch(target, { duration_sec: sec });
    out.lengthSec = sec;
  }

  return out;
}

export function useSettingsBlock(entry: RenderHistoryEntry | null, busy: boolean): string | null {
  if (entry === null) return NO_PREVIEW_HINT;
  if (busy) return RENDER_RUNNING_HINT;
  // Whether the op carries settings is only knowable after jobRecord() resolves, so it is not a
  // block reason — it is what the button reports afterwards.
  return null;
}

export function replaceClipBlock(
  entry: RenderHistoryEntry | null, target: Target, busy: boolean,
): string | null {
  if (entry === null) return NO_PREVIEW_HINT;
  if (busy) return RENDER_RUNNING_HINT;
  if (target.kind !== "clip") return NOT_THIS_CLIP_HINT;
  if (entry.source_clip_id === null || entry.source_clip_id !== target.id) return NOT_THIS_CLIP_HINT;
  return null;
}
