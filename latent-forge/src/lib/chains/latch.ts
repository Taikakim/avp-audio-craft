// The lane chain as the server takes it (WINTERMUTE 2026-09-25; M8 parse_chain -> chain_to_request)
// and the SIGNAL PATH idle note (spec §8.1 S4). The §5.5 gain mapping is the SERVER's: nothing
// here multiplies a head gain. Pure except fetchLatchHeads (network).

import { forgeApi } from "../forge/api";
import { isRamp } from "./latchScale";
import type { LaneChain, LatchBlock, LatchSlot } from "../forge/types";

/**
 * The subset of /info.latch_heads' element shape LANE CHAIN actually reads (M1's own /info typing
 * is `Record<string, unknown>` -- there is no existing LatchHeadInfo anywhere in M1). Restated from
 * spec §5.5/§6.4 and cross-checked field-for-field against
 * docs/latent-forge/contract/fixtures/handmade-info.json's two real entries (Task 10's contract
 * test re-checks them against the RECORDED info.json). The real payload carries more fields (path,
 * out_channels, loss_type, target_kind_default, standardized, schema) -- they exist on the wire but
 * nothing in this milestone reads them, so they are not declared here.
 */
export interface LatchHeadInfo {
  name: string;
  family: string;
  default_gain: number;
  health: string;
  supports_kinds: string[];
  slider_min: number;
  slider_max: number;
  value_default: number;
  /** The fields below arrive with eval/head_meta.py's schema-1 additions; an older server omits them. */
  units?: string;
  std_mean?: number | null;
  std_std?: number | null;
  /** Highest guidance gain that stayed clean on every test prompt (eval/latch_bracket_quality.json). */
  usable_max_gain?: number | null;
  usable_max_weight?: number | null;
}

/**
 * Exactly M8's CHAIN_DEFAULTS keys (parse_chain's _merge 400s on any other), exactly two slots
 * (parse_chain 400s on any other length), rho/mu as the 0..30 multipliers, lora.slot always null.
 */
export interface ChainRequest {
  latch_on: boolean;
  slots: [LatchSlot, LatchSlot];
  hparams: { rho: number; mu: number; gamma: number; n_iter: number; log_norms: boolean };
  film_on: boolean;
  film: { ckpt: string | null; gain: number; value: number };
  lora_on: boolean;
  lora: { ckpt_path: string | null; slot: null; strength: number };
  bungee_on: boolean;
  semitones: number;
}

/**
 * One slot, key by key. "none" and weight 0 pass through untouched -- chain_to_request drops them
 * (M8 plan line 375). A head the registry does not list becomes "none": chain_to_request 400s on it
 * with weight > 0 (M8 plan lines 377-379). Callers must therefore pass the fetched heads, not `{}`,
 * or every slot is sent as "none". end_pct is clamped up to start_pct: parse_chain 400s on
 * start_pct > end_pct for EVERY slot, before it looks at latch_on or the head (M8 parse_chain), so
 * an idle slot with crossed START%/END% sliders would 400 every render. The start handle is the one
 * the user dragged, so it is kept (WINTERMUTE 2026-09-25; critic follow-up #5).
 */
function wireSlot(slot: LatchSlot, heads: Record<string, LatchHeadInfo>): LatchSlot {
  const known = slot.head === "none" || Object.prototype.hasOwnProperty.call(heads, slot.head);
  const out: LatchSlot = {
    head: known ? slot.head : "none",
    kind: slot.kind,
    value: slot.value,
    weight: slot.weight,
    start_pct: slot.start_pct,
    end_pct: Math.max(slot.start_pct, slot.end_pct),
  };
  // Only a ramp with an explicit start sends value_from: parse_chain 400s on a key it does not know,
  // so every other slot stays byte-for-byte what a server without the field accepts.
  if (isRamp(slot.kind) && typeof slot.value_from === "number") out.value_from = slot.value_from;
  return out;
}

/** The wire shape of the LatCH part of a chain; a lane's chain and the master's both send it. */
export type LatchBlockRequest = Pick<ChainRequest, "latch_on" | "slots" | "hparams">;

export function latchBlockRequest(block: LatchBlock, heads: Record<string, LatchHeadInfo>): LatchBlockRequest {
  const hp = block.hparams;
  return {
    latch_on: block.latch_on,
    slots: [wireSlot(block.slots[0], heads), wireSlot(block.slots[1], heads)],
    hparams: { rho: hp.rho, mu: hp.mu, gamma: hp.gamma, n_iter: hp.n_iter, log_norms: hp.log_norms },
  };
}

/** The chain object for a job payload's `chain` key (M8 plan lines 1422, 1980). Always a plain copy. */
export function chainRequest(chain: LaneChain, heads: Record<string, LatchHeadInfo>): ChainRequest {
  return {
    ...latchBlockRequest(chain, heads),
    film_on: chain.film_on,
    film: { ckpt: chain.film.ckpt, gain: chain.film.gain, value: chain.film.value },
    lora_on: chain.lora_on,
    // ckpt_path is the durable identity; a /slots index is transient (Open questions 25).
    lora: { ckpt_path: chain.lora.ckpt_path, slot: null, strength: chain.lora.strength },
    bungee_on: chain.bungee_on,
    semitones: chain.semitones,
  };
}

/**
 * Spec §8.1 S4: "a lane with an active chain but no A2A clip shows chain idle -- no A2A clip in
 * lane". Active means ANY of the four features is on, not just LatCH -- FiLM, LoRA and Bungee all
 * run during the same A2A pass and are equally idle without one.
 */
export function chainIsIdle(chain: LaneChain, hasA2AClip: boolean): boolean {
  const active = chain.latch_on || chain.film_on || chain.lora_on || chain.bungee_on;
  return active && !hasA2AClip;
}

/** Keys /info.latch_heads by name, for the head selects in Task 2 and Task 4. */
export async function fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>> {
  const info = await forgeApi.info();
  const raw = (info as { latch_heads?: unknown }).latch_heads;
  const list = Array.isArray(raw) ? (raw as LatchHeadInfo[]) : [];
  const out: Record<string, LatchHeadInfo> = {};
  for (const h of list) out[h.name] = h;
  return out;
}
