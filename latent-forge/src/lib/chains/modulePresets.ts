// Spec §9.3's module level: "`latch`, `film`, `lora`, `bungee`: that module's settings object …
// module recall applies to the active lane." Each level's slice is the set of LaneChain fields its
// module owns, INCLUDING its own on/off flag, so every level has the same shape rule: a recalled
// preset restores whether the module is on, not just its values.
import type { LaneChain } from "../forge/types";

export type ModuleLevel = "latch" | "film" | "lora" | "bungee";

export const MODULE_PRESET_FIELDS: Record<ModuleLevel, readonly (keyof LaneChain)[]> = {
  latch: ["latch_on", "slots", "hparams"],
  film: ["film_on", "film"],
  lora: ["lora_on", "lora"],
  bungee: ["bungee_on", "semitones"],
};

/** A plain deep copy of the level's fields. JSON, not structuredClone: `chain` is normally a
 *  $state proxy, and structuredClone throws DataCloneError on one (Global Constraint #7).
 *  `lora.slot` is written null: a /slots index names whatever is resident NOW, so only
 *  `lora.ckpt_path` is durable (contract table, critic pass 2 #14). */
export function modulePresetPayload(chain: LaneChain, level: ModuleLevel): Partial<LaneChain> {
  const out: Record<string, unknown> = {};
  for (const k of MODULE_PRESET_FIELDS[level]) out[k] = JSON.parse(JSON.stringify(chain[k]));
  if (level === "lora") (out.lora as LaneChain["lora"]).slot = null;
  return out as Partial<LaneChain>;
}

/** The whole chain as it may be SAVED (session, master preset): a plain copy with the transient
 *  `lora.slot` cleared. The live chain is never modified. */
export function durableChain(chain: LaneChain): LaneChain {
  const copy = JSON.parse(JSON.stringify(chain)) as LaneChain;
  copy.lora.slot = null;
  return copy;
}

/** Writes ONLY the level's own fields into `chain`, in place (the $state proxy rule). Anything else
 *  in the payload -- another level's field, or junk from a hand-edited preset file -- is ignored. */
export function applyModulePreset(chain: LaneChain, level: ModuleLevel, payload: Record<string, unknown>): void {
  const target = chain as unknown as Record<string, unknown>;
  for (const k of MODULE_PRESET_FIELDS[level]) {
    if (k in payload && payload[k] !== undefined) target[k] = JSON.parse(JSON.stringify(payload[k]));
  }
}
