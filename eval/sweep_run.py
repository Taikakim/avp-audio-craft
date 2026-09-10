"""Batch/sweep CLI. A THIN CLIENT of the render server at :8056 -- it POSTs the
same payload the GUI posts and stores what came back.

It does NOT import the model, build a guidance config, or compute a weight. That
is deliberate: resolve_latch() in explorer_render_server.py NORMALISES gains
(rho = mu = slot-1 gain, per-slot weight = slot_gain / g0), so any second
implementation would silently be on a different scale and its numbers would not
mean what the GUI's mean. eval/head_lab.py was deleted for exactly that mistake.

Resumable by construction: one append-only JSON line per finished cell, fsynced,
keyed on sweep_spec.cell_id. Rerun the same command to continue. Errors are NOT
treated as done -- a rerun retries them, which is what you want after fixing a
bad path.

    python eval/sweep_run.py --spec S.json --out DIR [--dry-run] [--limit N]
                             [--base-url U] [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import presets           # noqa: E402
import sweep_spec        # noqa: E402

SCHEMA_VERSION = 1
DEFAULT_BASE = "http://localhost:8056"
RENDER_TIMEOUT = 3600.0
MODELS_TIMEOUT = 30.0


def _fetch_models(base_url=DEFAULT_BASE):
    """GET /models (the multi-root model database). Falls back to the local DB so
    the sweep can still be PLANNED with the server down."""
    try:
        import requests
        r = requests.get(f"{base_url.rstrip('/')}/models", timeout=MODELS_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        import model_db
        return model_db.load_or_build()


def resolve_models(spec, *, fetch=None, base_url=DEFAULT_BASE) -> list[dict]:
    """Spec entries (model-db id, label, or absolute path) -> model records.

    Fails LOUDLY on an unresolved entry, before any render: a typo that silently
    renders 40 cells on the base model is exactly the failure this exists to stop.
    """
    want = spec.get("models") or []
    if not want:
        return []
    db = (fetch or (lambda: _fetch_models(base_url)))()
    recs = db.get("models", db if isinstance(db, list) else [])
    by = {}
    for m in recs:
        for k in ("id", "label", "path"):
            if m.get(k):
                by.setdefault(str(m[k]), m)
    out = []
    for w in want:
        m = by.get(str(w))
        if m is None:
            raise ValueError(
                f"unknown model {w!r} — not an id, label or path in the model DB. "
                f"List them with: curl -s {base_url}/models | head")
        if not m.get("loadable", True):
            raise ValueError(
                f"model {w!r} has family {m.get('family')!r}, which cannot be loaded "
                f"through /generate today. Control/contour families are the subject of "
                f"docs/superpowers/plans/"
                f"2026-08-23-inference-ui-global-conditioner-inpaint.md")
        out.append({"id": m.get("id"), "label": m.get("label") or Path(m["path"]).stem,
                    "path": m["path"], "family": m.get("family")})
    return out


def manifest_path_for(out_dir) -> Path:
    return Path(out_dir) / "manifest.jsonl"


def done_ids(manifest_path) -> set:
    out = set()
    p = Path(manifest_path)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue                      # a torn last line from a kill -- ignore
        if rec.get("status") == "ok" and rec.get("cell_id"):
            out.add(rec["cell_id"])
    return out


def append_line(manifest_path, record) -> None:
    with open(manifest_path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())              # survive a kill mid-sweep


def _http_post(url, payload, timeout=RENDER_TIMEOUT):
    import requests
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _payload_for(spec) -> dict:
    if spec.get("payload"):
        return dict(spec["payload"])
    return dict(presets.load(spec["preset"])["payload"])


def run(spec, out_dir, *, base_url=DEFAULT_BASE, post=None, dry_run=False,
        limit=None, force=False, fetch=None) -> dict:
    problems = sweep_spec.validate_spec(spec)
    if problems:
        raise ValueError("bad sweep spec: " + "; ".join(problems))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mpath = manifest_path_for(out_dir)
    post = post or _http_post
    url = f"{base_url.rstrip('/')}/generate"

    payload = _payload_for(spec)
    models = resolve_models(spec, fetch=fetch, base_url=base_url)
    axes = dict(spec.get("axes") or {})
    label_by_path = {}
    if models:
        axes["model"] = [m["path"] for m in models]   # AXIS_KINDS maps it to ckpt_path
        label_by_path = {m["path"]: m["label"] for m in models}
    cells = sweep_spec.expand(payload, axes, seeds=spec.get("seeds"))
    for c in cells:
        # AFTER expand, so cell_id is keyed on the LABEL: a drive that remounts under
        # another name changes every path, and keying on the path would silently
        # re-render a finished sweep.
        if "model" in c["coords"]:
            c["coords"]["model"] = label_by_path[c["coords"]["model"]]
            c["cell_id"] = sweep_spec.cell_id(c["coords"])
    already = set() if force else done_ids(mpath)
    todo = [c for c in cells if c["cell_id"] not in already]
    if limit is not None:
        todo = todo[:limit]

    stats = {"planned": len(cells), "skipped": len(cells) - len(todo),
             "rendered": 0, "errors": 0, "z0_missing": 0,
             "manifest": str(mpath), "out_dir": str(out_dir)}
    if dry_run:
        for c in todo:
            print(f"  {c['cell_id']}  {c['coords']}")
        return stats

    started = time.time()
    sweep_meta = {"name": spec.get("name", out_dir.name),
                  "preset": spec.get("preset"), "started": started}
    try:
        for i, c in enumerate(todo, 1):
            t0 = time.time()
            print(f"[{i}/{len(todo)}] {c['cell_id']}  {c['coords']}", flush=True)
            # payload is stored VERBATIM per cell. Redundant with coords + the
            # preset, and that redundancy is the point: the preset may be edited
            # later, and the manifest must still say what actually ran.
            rec = {"schema": SCHEMA_VERSION, "cell_id": c["cell_id"],
                   "coords": c["coords"], "payload": c["payload"],
                   "sweep": sweep_meta, "t": time.time()}
            try:
                resp = post(url, c["payload"], timeout=RENDER_TIMEOUT)
                lat = resp.get("latents") or []
                rec.update(status="ok", files=resp.get("files", []), latents=lat,
                           z0_missing=not lat, seed=resp.get("seed"),
                           job_id=resp.get("job_id"),
                           server={k: (resp.get("meta") or {}).get(k) for k in
                                   ("dora_loaded", "film_loaded", "model_rebuilt")},
                           elapsed_sec=round(time.time() - t0, 1), error=None)
                stats["rendered"] += 1
                if not lat:
                    stats["z0_missing"] += 1
                    print("  WARNING: response carried no z0 latent "
                          "(standing directive: save z0 next to every render)")
            except Exception as e:
                rec.update(status="error", files=[], latents=[], z0_missing=True,
                           seed=None, job_id=None, server={},
                           elapsed_sec=round(time.time() - t0, 1), error=repr(e))
                stats["errors"] += 1
                print(f"  ERROR {e!r}")
            append_line(mpath, rec)
    except KeyboardInterrupt:
        left = len(todo) - stats["rendered"] - stats["errors"]
        print(f"\ninterrupted: {stats['rendered']} done, {left} remaining — "
              f"rerun the same command to continue")
        stats["interrupted"] = True
        return stats
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Sweep one or more axes over a saved preset, via the render "
                    "server at :8056. Resumable: rerun to continue.")
    ap.add_argument("--spec", required=True, help="sweep spec JSON")
    ap.add_argument("--out", required=True, help="output dir (holds manifest.jsonl)")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--dry-run", action="store_true", help="list cells, render nothing")
    ap.add_argument("--limit", type=int, default=None, help="render at most N cells")
    ap.add_argument("--force", action="store_true", help="ignore the manifest, redo all")
    ap.add_argument("--models", default=None,
                    help="comma-separated model ids/labels/paths; overrides the "
                         "spec's models list")
    a = ap.parse_args(argv)
    spec = sweep_spec.load_spec(a.spec)
    if a.models:
        spec["models"] = [x.strip() for x in a.models.split(",") if x.strip()]
    stats = run(spec, a.out, base_url=a.base_url,
                dry_run=a.dry_run, limit=a.limit, force=a.force)
    print(json.dumps(stats, indent=2))
    return 1 if stats.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
