// Runtime validators for the contract unions. Used by the project loader, the
// mock server and anything that accepts a ref from a drag payload -- places
// where a TypeScript type alone proves nothing.

import type { AudioRef, Envelope, LatentRef, Progress, Target } from "./types";

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isStr(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** A `file` ref's `rel` must not escape its root (spec §6.1). */
function isSafeRel(v: unknown): v is string {
  return isStr(v) && !v.split(/[\\/]/).includes("..");
}

export function isAudioRef(v: unknown): v is AudioRef {
  if (!isObj(v)) return false;
  switch (v.kind) {
    case "upload": return isStr(v.sha256);
    case "render": return isStr(v.job_id) && isStr(v.file);
    case "crop": return isStr(v.crop_id);
    case "file": return isStr(v.root) && isSafeRel(v.rel);
    case "path": return isStr(v.path);
    default: return false;
  }
}

export function isLatentRef(v: unknown): v is LatentRef {
  if (!isObj(v)) return false;
  switch (v.kind) {
    case "crop": return isStr(v.crop_id);
    case "path": return isStr(v.path);
    case "audio": return isAudioRef(v.audio);
    default: return false;
  }
}

export function isEnvelope(v: unknown): v is Envelope {
  if (!isObj(v)) return false;
  const { points, curves } = v;
  if (!Array.isArray(points) || points.length !== 4) return false;
  if (!Array.isArray(curves) || curves.length !== 3) return false;
  return (
    points.every((p) => isNum(p) && p >= 0 && p <= 1) &&
    curves.every((c) => isNum(c) && c >= -1 && c <= 1)
  );
}

export function isProgress(v: unknown): v is Progress {
  if (!isObj(v)) return false;
  return (
    isStr(v.job_id) && isStr(v.op) && typeof v.stage === "string" &&
    isNum(v.stage_index) && isNum(v.stage_count) &&
    isNum(v.step) && isNum(v.steps) &&
    isNum(v.steps_left_total) && isNum(v.steps_total)
  );
}

/** Stable key for a target; also the key of the per-target settings map. */
export function targetKey(t: Target): string {
  switch (t.kind) {
    case "none": return "session";
    case "clip": return `clip:${t.id}`;
    case "overlap": return `overlap:${t.key}`;
  }
}
