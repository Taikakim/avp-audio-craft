// Spec §4.5 MIX ORDER, §8.1 S7 MIX. Which pairs feed which node is fixed by `order`; each node's
// own {interp, t} lives on MixSpec.nodes and is read directly by the component -- this file only
// describes the WIRING between lanes and nodes, and the quad-weight normalisation used for the
// client-side preview (the server does the real mix, spec §8.1 S7).

import type { MixSpec } from "../forge/types";

export interface MixTreeNode {
  id: "M1" | "M2" | "MX";
  a: string; // "L1".."L4" or another node's id
  b: string;
}

export function mixTree(order: MixSpec["order"]): MixTreeNode[] | null {
  if (order === "quad") return null;
  if (order === "tree") {
    return [
      { id: "M1", a: "L1", b: "L2" },
      { id: "M2", a: "L3", b: "L4" },
      { id: "MX", a: "M1", b: "M2" },
    ];
  }
  return [ // cascade
    { id: "M1", a: "L1", b: "L2" },
    { id: "M2", a: "M1", b: "L3" },
    { id: "MX", a: "M2", b: "L4" },
  ];
}

export function isQuad(order: MixSpec["order"]): boolean {
  return order === "quad";
}

export function normalizedQuadWeights(weights: readonly [number, number, number, number]): [number, number, number, number] {
  const sum = weights.reduce((s, w) => s + w, 0);
  if (sum <= 0) return [0.25, 0.25, 0.25, 0.25];
  return weights.map((w) => w / sum) as [number, number, number, number];
}
