// Last edited: WINTERMUTE 2026-10-13 — census verdict flags, notes key, generic 'checkpoints' labels
// Last edited: WINTERMUTE 2026-10-14 — the MODEL NOTES 1..5 rating and its colours
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
  /** model_db's curation flags (eval/model_db.py `_join_quality`): the run has a checkpoint on Kim's
   *  cleaned-checkpoints list / THIS checkpoint is on it / the run's status is failed-*. */
  good_run?: boolean;
  good_ckpt?: boolean;
  broken?: boolean;
  /** The census key this run's notes live under (eval/model_db.py `notes_key`): the run folder
   *  when the checkpoint's own folder is a generic `checkpoints/`. */
  notes_key?: string;
  /** The MODEL NOTES 1..5 rating of the run (overrides `forge_rating`), null when unrated. */
  rating?: number | null;
}

/** wandb-style runs save to <run>/<id>/checkpoints/, so their `label` is just "checkpoints". */
const GENERIC_LABELS = new Set(["checkpoints", "runs"]);

/** green = on the cleaned-checkpoints list, red = a failed run, "" = no verdict. */
export type ModelQuality = "good" | "broken" | "";

export interface ModelOption {
  value: string;
  label: string;
  group: "backbone" | "adapter";
  /** null for a backbone; the checkpoint path for an adapter. */
  ckptPath: string | null;
  /** adapters only, and only when the server recorded them. */
  epoch?: number;
  step?: number;
  /** The run's own label, the key MODEL NOTES reads and writes (the backbone id for a backbone). */
  run: string;
  /** The run's verdict (MODEL select) ... */
  quality: ModelQuality;
  /** ... and this checkpoint's (EPOCH select). */
  ckptGood: boolean;
  /** The run's MODEL NOTES rating, 1..5, or null. Overrides `quality` for the run's colour. */
  rating: number | null;
}

/** 1 red, 2 orange, 3 yellow, 4 light green, 5 turquoise (tokens.css --rate1..5). */
export function ratingColor(r: number | null | undefined): string {
  return typeof r === "number" && r >= 1 && r <= 5 ? `var(--rate${Math.round(r)})` : "";
}

/** The MODEL select's colour for a run: its rating when it has one, else the census verdict. */
export function runColor(o: Pick<ModelOption, "rating" | "quality">): string {
  return ratingColor(o.rating) || (o.quality === "good" ? "var(--green-strong)" : o.quality === "broken" ? "var(--red)" : "");
}

/** The EPOCH select's colour: the checkpoint's own verdict (cleaned list / failed run). The rating is
 *  per run, so it does not tell one epoch from another. */
export function ckptColor(o: Pick<ModelOption, "quality" | "ckptGood">): string {
  return o.quality === "broken" ? "var(--red)" : o.ckptGood ? "var(--green-strong)" : "";
}

/** A rating just saved from MODEL NOTES, applied to every option of that run without a refetch. */
export function withRating(options: ModelOption[], run: string, rating: number | null): ModelOption[] {
  return options.map((o) => (o.run === run ? { ...o, rating } : o));
}

function validRating(r: unknown): number | null {
  return typeof r === "number" && Number.isInteger(r) && r >= 1 && r <= 5 ? r : null;
}

export function runQuality(a: { good_run?: boolean; broken?: boolean }): ModelQuality {
  return a.broken ? "broken" : a.good_run ? "good" : "";
}

export function buildModelOptions(
  adapters: AdapterEntry[], goodBackbones: string[] = [], backboneRatings: Record<string, number> = {},
): ModelOption[] {
  const options: ModelOption[] = BACKBONE_IDS.map((id) => ({
    value: id,
    label: id,
    group: "backbone" as const,
    ckptPath: null,
    run: id,
    quality: goodBackbones.includes(id) ? ("good" as const) : ("" as const),
    ckptGood: false,
    rating: validRating(backboneRatings[id]),
  }));
  const seen = new Set<string>();
  for (const a of adapters) {
    if (!a.path || seen.has(a.path)) continue;
    seen.add(a.path);
    const generic = !!a.label && GENERIC_LABELS.has(a.label) && !!a.notes_key;
    const name = generic ? (a.notes_key as string) : a.label || a.name || a.path;
    options.push({
      value: a.path,
      label: name + (a.family === "fullft" ? " (full FT)" : ""),
      group: "adapter",
      ckptPath: a.path,
      run: a.notes_key || a.label || a.name || a.path,
      quality: runQuality(a),
      ckptGood: !!a.good_ckpt && !a.broken,
      rating: validRating(a.rating),
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
