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
  /** model_db's own fields: every checkpoint of one run shares `label` and sits in the run's folder. */
  epoch?: number | null;
  step?: number | null;
}

export interface ModelOption {
  value: string;
  label: string;
  group: "backbone" | "adapter";
  /** null for a backbone; the checkpoint path for an adapter. */
  ckptPath: string | null;
  /** adapters only, and only when the server recorded them. */
  epoch?: number;
  step?: number;
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
      ...(typeof a.epoch === "number" ? { epoch: a.epoch } : {}),
      ...(typeof a.step === "number" ? { step: a.step } : {}),
    });
  }
  return options;
}

/** The folder a checkpoint sits in, separator-agnostic: the server's paths are POSIX, a saved one may not be. */
function folderOf(path: string): string {
  return path.replace(/[/\\][^/\\]*$/, "");
}

function fileOf(path: string): string {
  return path.slice(path.search(/[^/\\]*$/));
}

/**
 * The checkpoints of one run: same folder, and an epoch recorded. Checkpoints with no epoch are not
 * grouped -- nothing says two of them belong together -- so each stays its own entry.
 */
function runKey(o: ModelOption): string {
  return o.epoch !== undefined ? folderOf(o.value) : o.value;
}

/** "ep 67 · 45900" -- the file name when the server recorded no epoch. */
export function epochLabel(o: ModelOption): string {
  if (o.epoch === undefined) return fileOf(o.value);
  return o.step !== undefined ? `ep ${o.epoch} · ${o.step}` : `ep ${o.epoch}`;
}

export interface ModelMenu {
  /** The four backbones, then ONE entry per adapter run. The entry for the run holding `selected`
   *  carries `selected`'s path; any other run carries its newest epoch. */
  primary: ModelOption[];
  /** The selected run's checkpoints, newest epoch first; [] unless `selected` is an adapter with an epoch. */
  epochs: ModelOption[];
}

/**
 * The MODEL select used to list every checkpoint of every run under the run's own name -- 660 rows
 * that differed only by an epoch the label did not show. The run is the primary choice and the epoch
 * a second select beside it. The value stays the checkpoint PATH throughout (sessions and
 * settings.ckptPath store that), so picking from either select is one `onmodel(path)`.
 */
export function modelMenu(options: ModelOption[], selected: string): ModelMenu {
  const primary: ModelOption[] = [];
  const runs = new Map<string, ModelOption[]>();
  for (const o of options) {
    if (o.group === "backbone") {
      primary.push(o);
      continue;
    }
    const key = runKey(o);
    const list = runs.get(key);
    if (list) list.push(o);
    else {
      runs.set(key, [o]);
      primary.push(o); // placeholder, replaced below so the run keeps its place in the list
    }
  }
  const newestFirst = (a: ModelOption, b: ModelOption) =>
    (b.epoch ?? -1) - (a.epoch ?? -1) || (b.step ?? -1) - (a.step ?? -1);
  let epochs: ModelOption[] = [];
  const out = primary.map((o) => {
    if (o.group === "backbone") return o;
    const members = runs.get(runKey(o)) as ModelOption[];
    members.sort(newestFirst);
    const holdsSelection = members.some((m) => m.value === selected);
    const rep = members.find((m) => m.value === selected) ?? members[0];
    if (holdsSelection && rep.epoch !== undefined) epochs = members;
    return members.length > 1 ? { ...rep, label: `${rep.label} (${members.length} ep)` } : rep;
  });
  return { primary: out, epochs };
}
