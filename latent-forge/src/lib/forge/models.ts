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
