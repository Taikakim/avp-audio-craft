// The adapter list the MODEL select appends (spec §4.2). `/models` is an existing
// server route outside the frozen /forge contract, so it lives beside forgeApi
// rather than inside it; M7 folds it in if the contract ever grows a forge route
// for the checkpoint index.
//
// An unmounted adapter root is a normal state on this box, not an error: the
// server answers `{ok: false, error: ...}` and the select simply shows the four
// backbones.
//
// The real route answers `{ok, count, models, stale_root_ids}` -- the array is
// under `models` (eval/explorer_render_server.py's /models route). An earlier
// draft read `ckpts` and always resolved [] against the real server.

import type { AdapterEntry } from "../../ui/topbar/modelOptions";

export async function fetchAdapters(): Promise<AdapterEntry[]> {
  const res = await fetch("/models?family=adapter&loadable=1");
  const text = await res.text();
  if (!text) return [];
  let body: { ok?: boolean; models?: AdapterEntry[] };
  try {
    body = JSON.parse(text) as { ok?: boolean; models?: AdapterEntry[] };
  } catch {
    return [];
  }
  if (!res.ok || body.ok === false || !Array.isArray(body.models)) return [];
  return body.models;
}

/** A /models row as the control_adapter query returns it: every model_db row carries
 *  `control_mode` (eval/model_db.py), null when the probe found none. */
type ControlAdapterRow = AdapterEntry & { control_mode?: string | null };

/**
 * Sibling of fetchAdapters, same shape, for FiLM's CKPT select (spec §5.5, §10 X9).
 * There is no "film" family (WINTERMUTE 2026-09-25; critic follow-up #1, M7 Open questions 36):
 * FiLM checkpoints are family "control_adapter" with control_mode "scalar". The filter is
 * REQUIRED, not cosmetic -- the server's _install_film builds a ScalarAttributeEncoder, so a
 * melody_contour / metrical_position / fingerprint / dual_scalar / attribute adapter would load
 * the wrong encoder. /info.film_default.ckpt stays the preselected default (the "" option).
 */
export async function fetchFilmCkpts(): Promise<AdapterEntry[]> {
  const res = await fetch("/models?family=control_adapter");
  const text = await res.text();
  if (!text) return [];
  let body: { ok?: boolean; models?: ControlAdapterRow[] };
  try {
    body = JSON.parse(text) as { ok?: boolean; models?: ControlAdapterRow[] };
  } catch {
    return [];
  }
  if (!res.ok || body.ok === false || !Array.isArray(body.models)) return [];
  return body.models.filter((m) => m.control_mode === "scalar");
}

export interface SlotEntry {
  index: number; path: string; label: string; family: string; cost_gb: number; strength: number;
}
export interface SlotsResponse {
  ok: boolean; active: number | null; backbone: string | null;
  slots: SlotEntry[]; max_slots: number; vram_floor_gb: number; free_gb: number;
}

/**
 * Resident adapter slots (eval/adapter_slots.py, eval/explorer_render_server.py:901-905). LORA/DORA
 * lists these first -- switching between them costs milliseconds, a fresh /models load does not.
 */
export async function fetchSlots(): Promise<SlotsResponse> {
  const res = await fetch("/slots");
  const text = await res.text();
  const empty: SlotsResponse = { ok: false, active: null, backbone: null, slots: [], max_slots: 0, vram_floor_gb: 0, free_gb: 0 };
  if (!text) return empty;
  let body: Partial<SlotsResponse>;
  try {
    body = JSON.parse(text) as Partial<SlotsResponse>;
  } catch {
    return empty;
  }
  if (!res.ok || body.ok === false || !Array.isArray(body.slots)) return empty;
  return {
    ok: true, active: body.active ?? null, backbone: body.backbone ?? null,
    slots: body.slots, max_slots: body.max_slots ?? 0,
    vram_floor_gb: body.vram_floor_gb ?? 0, free_gb: body.free_gb ?? 0,
  };
}
