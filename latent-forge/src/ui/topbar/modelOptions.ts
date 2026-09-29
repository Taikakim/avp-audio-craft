// Spec §4.2: the MODEL select lists the four backbones, then the adapters from
// /models?family=adapter&loadable=1. Choosing a backbone posts to /forge/backbone
// (M7); choosing an adapter sets the session-default ckpt_path, which is why each
// option carries the path it would write.

export const BACKBONE_IDS = [
  "medium",
  "medium-base",
  "small-music",
  "small-music-base",
] as const;

export type BackboneId = (typeof BACKBONE_IDS)[number];

/** One row of the existing server's /models response (a CkptEntry). The real model_db rows
 *  carry `label` (the run's arm) and no `name` (eval/model_db.py), so `name` is optional and a
 *  display reads `label || name || path` (critic follow-up to the reconcile pass, #6). */
export interface AdapterEntry {
  path: string;
  name?: string;
  label?: string;
  family?: string;
}

export interface ModelOption {
  value: string;
  label: string;
  group: "backbone" | "adapter";
  /** null for a backbone; the checkpoint path for an adapter. */
  ckptPath: string | null;
}

export function buildModelOptions(adapters: AdapterEntry[]): ModelOption[] {
  const options: ModelOption[] = BACKBONE_IDS.map((id) => ({
    value: id,
    label: id,
    group: "backbone" as const,
    ckptPath: null,
  }));
  const seen = new Set<string>();
  for (const a of adapters) {
    if (!a.path || seen.has(a.path)) continue;
    seen.add(a.path);
    options.push({
      value: a.path,
      label: a.label || a.name || a.path,
      group: "adapter",
      ckptPath: a.path,
    });
  }
  return options;
}
