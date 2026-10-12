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
  /** Present only on a row a finished commit reported (spec §6.9 meta.stages). */
  seconds?: number;
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

/** From a commit job's `meta.stages` (spec §6.9: "meta.stages (label, on, note, seconds)"). */
export interface CommitStage {
  label: string;
  on: boolean;
  note: string;
  seconds: number;
}

/** The last commit's ground truth, plus the arrangement it described. */
export interface CommitStages {
  key: string;
  stages: CommitStage[];
}

/**
 * The estimate is a pure function of SignalPathInput, so the input IS the identity of what a
 * commit's stages describe. Field order is fixed by construction here rather than by
 * JSON.stringify's insertion order, which differs between a live $state proxy and a structuredClone.
 */
export function signalKeyOf(input: SignalPathInput): string {
  return JSON.stringify([
    input.lanes.map((l) => [l.index, chainActive(l.chain), l.chain.bungee_on]),
    input.clips.map((c) => [c.lane, c.isCropAudio, c.needsStretch, c.a2aOn]),
    input.overlapCount,
    input.mix.order,
    [input.master.latch_on, input.master.norm_on],
  ]);
}

/**
 * M7 open question 7, decided in M9 T4: RECONCILE, not replace. The estimate is always computed;
 * a finished commit's stages override it only while `commit.key` still equals the current input's
 * key. The moment the arrangement changes, the commit describes something else and is dropped --
 * a confidently wrong lit row is worse than an honest estimate (signalPath.ts's own header).
 * Rows are matched by LABEL, so a server that adds or reorders stages degrades to the estimate for
 * the rows the client does not recognise instead of producing a short or renumbered list.
 */
export function mergeSignalPath(
  estimate: SignalPathStage[],
  commit: CommitStages | null,
  currentKey: string,
): SignalPathStage[] {
  if (commit === null || commit.key !== currentKey) return estimate;
  // Labels repeat: S1 and S9 are both "DECODE latent → audio". A Map keyed by label kept only S9 and
  // lit row 1 with S9's state (review 2026-10-01), so the k-th row with a label takes the k-th
  // commit stage with that label -- order within a label, label across the list.
  const byLabel = new Map<string, CommitStage[]>();
  for (const s of commit.stages) {
    const q = byLabel.get(s.label);
    if (q) q.push(s); else byLabel.set(s.label, [s]);
  }
  return estimate.map((row) => {
    const real = byLabel.get(row.label)?.shift();
    return real === undefined
      ? row
      : { ...row, lit: real.on, note: real.note || row.note, seconds: real.seconds };
  });
}
