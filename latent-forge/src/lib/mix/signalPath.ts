// Spec §8.1's nine stages, rendered live in the MIX + SIGNAL PATH tab. This is a CLIENT-SIDE
// PREVIEW, not the ground truth -- the real per-stage on/off comes back from a commit job's
// meta.stages (spec §6.9), which does not exist until M9 wires the button. Until then this
// estimates from what is currently on the timeline, same spirit as M1's litModules() estimating
// module dots before their stores existed.

import { chainIsIdle } from "../chains/latch";
import type { LaneChain, MasterChain, MixSpec } from "../forge/types";

export interface SignalPathClip {
  lane: 0 | 1 | 2 | 3;
  isCropAudio: boolean;   // this clip's AudioRef.kind === "crop" -> S1 decodes it
  needsStretch: boolean;  // native_bpm differs from the project tempo, or detune_cents !== 0
  a2aOn: boolean;         // clip.a2a?.on
}

export interface SignalPathInput {
  lanes: Array<{ index: 0 | 1 | 2 | 3; chain: LaneChain }>;
  clips: SignalPathClip[];
  overlapCount: number;
  mix: MixSpec;
  master: MasterChain;
}

export interface SignalPathStage {
  n: number;
  label: string;
  lit: boolean;
  note: string;
}

const MIX_ORDER_NOTE: Record<MixSpec["order"], string> = {
  tree: "(1+2) + (3+4)",
  cascade: "((1+2)+3)+4",
  quad: "weighted 4-way (lerp only)",
};

function chainActive(chain: LaneChain): boolean {
  return chain.latch_on || chain.film_on || chain.lora_on || chain.bungee_on;
}

export function buildSignalPath(input: SignalPathInput): SignalPathStage[] {
  const anyCrop = input.clips.some((c) => c.isCropAudio);
  const anyStretch = input.clips.some((c) => c.needsStretch) || input.lanes.some((l) => l.chain.bungee_on);
  const anyChainOn = input.lanes.some((l) => chainActive(l.chain));
  const anyA2A = input.clips.some((c) => c.a2aOn);

  // S4's idle note: any lane whose chain is active but whose OWN clips have no A2A on.
  const idleLane = input.lanes.find((l) => {
    if (!chainActive(l.chain)) return false;
    const hasA2AInLane = input.clips.some((c) => c.lane === l.index && c.a2aOn);
    return chainIsIdle(l.chain, hasA2AInLane);
  });

  return [
    { n: 1, label: "DECODE latent → audio", lit: anyCrop, note: "" },
    { n: 2, label: "BUNGEE stretch / pitch", lit: anyStretch, note: "" },
    { n: 3, label: "ENCODE audio → latent", lit: input.clips.length > 0, note: "" },
    { n: 4, label: "LANE CHAINS", lit: anyChainOn, note: idleLane ? "chain idle — no A2A clip in lane" : "" },
    { n: 5, label: "A2A RE-NOISE", lit: anyA2A, note: "" },
    { n: 6, label: "INPAINT OVERLAPS", lit: input.overlapCount > 0, note: "" },
    { n: 7, label: "MIX", lit: input.clips.length > 0, note: MIX_ORDER_NOTE[input.mix.order] },
    { n: 8, label: "MASTER CHAIN", lit: input.master.latch_on || input.master.norm_on, note: "" },
    { n: 9, label: "DECODE latent → audio", lit: input.clips.length > 0, note: "" },
  ];
}
