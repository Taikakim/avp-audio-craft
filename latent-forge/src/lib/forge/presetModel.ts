// Owner: WINTERMUTE (created 2026-10-13)
// The model a preset was made with, and the check before recalling it: a preset made on another
// backbone or adapter sounds different on the loaded one, so the UI asks before switching (and
// switching can take a minute and a lot of VRAM, so it never happens unasked).

export interface PresetModel {
  /** "medium" (post-trained) or "medium-base" ...; null = whatever is loaded. */
  backbone: string | null;
  /** Adapter or full-finetune checkpoint; null = the bare backbone. */
  ckpt_path: string | null;
  family?: string | null;
  strength?: number;
  weights?: "online" | "ema" | null;
}

export interface LoadedModel {
  backbone: string | null;
  ckpt_path: string | null;
}

export function isPresetModel(v: unknown): v is PresetModel {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
  const m = v as Record<string, unknown>;
  const strOrNull = (x: unknown) => x === null || x === undefined || typeof x === "string";
  return strOrNull(m.backbone) && strOrNull(m.ckpt_path);
}

/** What would change on recall: an empty list means the loaded model already matches. */
export function modelChanges(want: PresetModel, have: LoadedModel): ("backbone" | "checkpoint")[] {
  const out: ("backbone" | "checkpoint")[] = [];
  if (want.backbone && want.backbone !== have.backbone) out.push("backbone");
  if ((want.ckpt_path ?? null) !== (have.ckpt_path ?? null)) out.push("checkpoint");
  return out;
}

/** "medium-base + fp32cmp_avp_t512_bs8_lr1e4 / epoch=7-step=2392.ckpt" -- run dir and file only. */
export function describeModel(m: { backbone: string | null; ckpt_path: string | null }): string {
  const bb = m.backbone ?? "(loaded backbone)";
  if (!m.ckpt_path) return `${bb}, no adapter`;
  const parts = m.ckpt_path.split("/");
  return `${bb} + ${parts.slice(-2).join(" / ")}`;
}

export function confirmText(want: PresetModel, have: LoadedModel, presetName: string): string {
  return `${presetName} was made with\n  ${describeModel(want)}\n\nLoaded now:\n  ${describeModel(have)}\n\n`
    + "Load the preset's model? (Cancel keeps the current model and applies the settings only.)";
}

// One place that knows how to ask + switch: App registers it (it owns switchBackbone and the
// top-bar selects), preset menus anywhere call requestPresetModel.
type Requester = (model: PresetModel, presetName: string) => Promise<void>;
let requester: Requester | null = null;

export function setPresetModelRequester(fn: Requester | null): void {
  requester = fn;
}

export async function requestPresetModel(model: PresetModel, presetName: string): Promise<void> {
  if (requester) await requester(model, presetName);
}
