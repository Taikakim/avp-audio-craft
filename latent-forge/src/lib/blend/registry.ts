// Owner: KUANG (created 2026-10-15), from WINTERMUTE's phase-1 plan (docs/superpowers/plans/2026-10-15-adapter-mixer-phase1.md)
// Blend ideas for the adapter mixer (spec docs/superpowers/specs/2026-10-15-adapter-mixer-design.md §3, §4.3).
// A new idea = one entry here (plus its own controls, Phase 2+). Each turns the UI's curve into the
// fields the server's `dora` request takes (GHOST-NOTE's _apply_block_profile, SAO 5522423).
import type { BlendMode, LaneChain } from "../forge/types";
import type { ChainRequest } from "../chains/latch";

export interface BlendWire { block_strengths: number[]; blend?: "interp" }
export interface BlendIdea { id: BlendMode; label: string; help: string; toWire(curve: number[]): BlendWire }

export const BLEND_IDEAS: readonly BlendIdea[] = [
  {
    id: "amount",
    label: "amount (blend with base)",
    help: "Per block, how much of the adapter's weight change is applied: 0 = base model, 1 = full adapter. " +
      "Exact for LoRA and DoRA (rows / cols); other adapter types fall back to direction and the render reports it.",
    toWire: (curve) => ({ block_strengths: [...curve], blend: "interp" }),
  },
  {
    id: "direction",
    label: "direction (stock strength)",
    help: "Per block, the adapter's usual strength knob: scales the low-rank direction, the trained magnitude stays. " +
      "For DoRA only an exact 0 turns a block off: 0.05 still applies nearly the full adapter there.",
    toWire: (curve) => ({ block_strengths: [...curve] }),
  },
];

export function blendIdea(id: BlendMode): BlendIdea {
  const idea = BLEND_IDEAS.find((b) => b.id === id);
  if (!idea) throw new Error(`unknown blend mode ${id}`);
  return idea;
}

/** The chain's lora object as the server takes it. No blend (or blend off) = exactly the pre-mixer shape. */
export function loraWire(lora: LaneChain["lora"]): ChainRequest["lora"] {
  const base = { ckpt_path: lora.ckpt_path, slot: null, strength: lora.strength } as ChainRequest["lora"];
  if (!lora.blend?.on) return base;
  return { ...base, strength: 1, ...blendIdea(lora.blend.mode).toWire(lora.blend.curve) };
}
