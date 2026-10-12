// Which right-pane modules hold non-default settings (spec §4.6, the "lit dot").
//
// Pure: it takes a snapshot of whatever settings currently exist and compares
// them with the defaults of defaults.ts. M1 passes nulls -- there is no chain or
// per-target settings store yet -- so every dot is dark. M4 fills `sampling`
// from lib/stores/render.svelte.ts and M7 fills `overlap`, `chain` and `master`
// from lib/stores/chains.svelte.ts; nothing in this file changes when they do.

import { BASE_DEFAULTS, CHAIN_DEFAULTS, MASTER_DEFAULT, OVERLAP_DEFAULT } from "./defaults";
import type { LaneChain, MasterChain, OverlapParams, RenderSettings } from "./types";
// ModuleId is declared ONCE, by the view store (it is also the vocabulary
// persisted into the project JSON's ui.modules). The two legacy ids T15
// re-homes are not spec modules, so they never appear in MODULE_ORDER and
// never get a lit dot.
import type { ModuleId } from "../stores/view.svelte";

export type SpecModuleId = Exclude<ModuleId, "legacy-inspector" | "legacy-server">;

/** Spec §4.6, top to bottom. */
export const MODULE_ORDER: SpecModuleId[] = [
  "overlap", "files", "lane-chain", "advanced-sampling", "master-chain",
];

/** The header text. LANE n CHAIN follows the active lane (spec §4.6.3). */
export function moduleTitle(id: SpecModuleId, activeLane: 0 | 1 | 2 | 3): string {
  switch (id) {
    case "overlap": return "OVERLAP — INPAINT";
    case "files": return "FILES";
    case "lane-chain": return `LANE ${activeLane + 1} CHAIN`;
    case "advanced-sampling": return "ADVANCED SAMPLING";
    case "master-chain": return "MASTER CHAIN";
  }
}

/** Structural equality. Settings are plain JSON, so this is enough and is cheap. */
export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return false;
  if (typeof a !== "object") return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((v, i) => deepEqual(v, b[i]));
  }
  const ao = a as Record<string, unknown>;
  const bo = b as Record<string, unknown>;
  const ak = Object.keys(ao);
  const bk = Object.keys(bo);
  if (ak.length !== bk.length) return false;
  return ak.every((k) => Object.prototype.hasOwnProperty.call(bo, k) && deepEqual(ao[k], bo[k]));
}

/**
 * What exists right now. `null` means "this milestone has no store for it yet",
 * which reads as default (dark dot) rather than as a difference.
 */
export interface ModuleStateSnapshot {
  overlap: OverlapParams | null;
  chain: LaneChain | null;
  sampling: RenderSettings | null;
  master: MasterChain | null;
}

/**
 * ADVANCED SAMPLING owns the sampling apparatus, not the prompt: the prompt and
 * the negative prompt live in the PROMPT + SIGMA pane (spec §4.5), so typing a
 * prompt must not light this module's dot.
 */
function samplingIsDefault(s: RenderSettings): boolean {
  return (
    s.steps === BASE_DEFAULTS.steps &&
    s.cfg_scale === BASE_DEFAULTS.cfg_scale &&
    s.apg_scale === BASE_DEFAULTS.apg_scale &&
    s.scale_phi === BASE_DEFAULTS.scale_phi &&
    s.sampler_type === BASE_DEFAULTS.sampler_type &&
    deepEqual(s.cfg_interval_progress, BASE_DEFAULTS.cfg_interval_progress) &&
    deepEqual(s.schedule, BASE_DEFAULTS.schedule)
  );
}

export function litModules(s: ModuleStateSnapshot): Record<SpecModuleId, boolean> {
  return {
    "overlap": s.overlap !== null && !deepEqual(s.overlap, OVERLAP_DEFAULT),
    // A root and a filter string are navigation, not settings: FILES never lights.
    files: false,
    "lane-chain": s.chain !== null && !deepEqual(s.chain, CHAIN_DEFAULTS),
    "advanced-sampling": s.sampling !== null && !samplingIsDefault(s.sampling),
    "master-chain": s.master !== null && !deepEqual(s.master, MASTER_DEFAULT),
  };
}
