#!/usr/bin/env python3
"""extract_recipes.py — extract REAL training recipes from checkpoint files.

Rebuild (2026-07-30, THE-FINN) of the original /tmp extractor that populated
models_index_overrides.json on 2026-07-12 (the _doc there references it; it was
lost with /tmp). Committed this time so re-extraction is reproducible.

Source of truth for checkpoint LOCATIONS: eval/rarity_bracket_manifest.json
  models[label] = {tier, picks:[ckpt filename...], root?, skip?, reason?, witness?}
  full path = (root or DEFAULT_ROOT)/<label>/<pick>

Per label it loads a representative checkpoint and extracts a STRUCTURED recipe:
  - DoRA/LoRA runs: lora_config (rank/alpha/adapter_type/dropout/include/exclude)
    + target-module count and rank-from-shapes read off the state_dict
    + epoch/global_step; optimizer param_groups (lr/betas/weight_decay/eps) ONLY
    if the pick is a fat `.ckpt` (slim `.weights.ckpt` prunes optimizer_states).
  - control-adapter / LatCH / other shapes: dump whatever config-like top-level
    dicts exist (args / hparams / metadata / config), plus epoch/step/avg_loss.

Run:  python3 Misc/extract_recipes.py            # dry-run -> writes staging file only
      python3 Misc/extract_recipes.py --limit 20 # first N labels (validation)
      python3 Misc/extract_recipes.py --label X   # single label
Output: eval/extracted_recipes.staging.json  (+ printed coverage summary)
Merging into models_index_overrides.json is a SEPARATE, non-clobbering step.
"""
import argparse, json, os, sys, time, traceback
from pathlib import Path

MANIFEST = Path("/home/kim/Projects/SAO/eval/rarity_bracket_manifest.json")
# Standing rule: no drive paths in code. eval/model_roots.json is the config.
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from model_roots import resolve_roots as _resolve_roots  # noqa: E402


def _default_root() -> str:
    for r in _resolve_roots():
        if r.id == "local_dora" and r.available:
            return r.path
    raise SystemExit("no available checkpoint root -- is the eval drive mounted? "
                     "(see eval/model_roots.json)")


DEFAULT_ROOT = None      # resolved lazily in main(); see _default_root()
STAGING = Path("/home/kim/Projects/SAO/eval/extracted_recipes.staging.json")

try:
    import torch
except Exception as e:  # pragma: no cover
    print("FATAL: torch not importable — run under the mir venv "
          "(/home/kim/Projects/mir/.venv/bin/python)", file=sys.stderr)
    raise


def _pick_representative(root, label, picks):
    """Prefer a fat .ckpt (has optimizer_states) over a slim .weights.ckpt;
    among same kind, the latest by (epoch, step) parsed from the filename."""
    def parse(fn):
        e = s = -1
        for tok in fn.replace(".weights", "").replace(".ckpt", "").split("-"):
            if tok.startswith("epoch="):
                try: e = int(tok.split("=")[1])
                except: pass
            if tok.startswith("step="):
                try: s = int(tok.split("=")[1])
                except: pass
        fat = not fn.endswith(".weights.ckpt")  # fat .ckpt sorts first
        return (fat, e, s)
    existing = [p for p in picks if os.path.exists(os.path.join(root, label, p))]
    if not existing:
        return None
    existing.sort(key=parse, reverse=True)
    return existing[0]


def _lora_target_modules(state_dict):
    """Count distinct base modules carrying LoRA params + read rank from a lora_A."""
    mods, rank = set(), None
    for k, v in state_dict.items():
        if "lora_A" in k:
            base = k.split(".parametrizations")[0] if ".parametrizations" in k else k.split(".lora_A")[0]
            mods.add(base)
            if rank is None:
                try: rank = int(v.shape[0])  # lora_A: (rank, in)
                except Exception: pass
    return len(mods), rank


def _safetensors_header(path):
    """Read the JSON header of a .safetensors file WITHOUT loading tensor data.
    Layout: 8-byte little-endian header length, then that many bytes of JSON
    {tensor_name: {dtype, shape, data_offsets}, "__metadata__": {...}}."""
    import struct
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(n))


def extract_safetensors(pick, path, size_mb):
    try:
        hdr = _safetensors_header(path)
    except Exception as e:
        return {"_status": "load_error", "_reason": f"{type(e).__name__}: {e}",
                "_source_ckpt": pick, "_size_mb": size_mb}
    meta = hdr.get("__metadata__") or {}
    tensors = [k for k in hdr if k != "__metadata__"]
    rec = {"_status": "ok", "_source_ckpt": pick, "_size_mb": size_mb,
           "_pruned_slim": False, "kind": "safetensors adapter (svd-extracted)"}
    lc = meta.get("lora_config")
    if isinstance(lc, str):
        try: lc = json.loads(lc)
        except Exception: pass
    la = [k for k in tensors if "lora_A" in k]
    rec["target_modules_count"] = len(la)
    try: rec["rank_from_shapes"] = int(hdr[la[0]]["shape"][0]) if la else None
    except Exception: rec["rank_from_shapes"] = None
    if isinstance(lc, dict):
        rec["lora_config"] = {k: lc.get(k) for k in ("rank", "alpha", "adapter_type", "dropout", "include", "exclude")}
        prov = {k: lc[k] for k in ("extracted_from", "extraction_method") if k in lc}
        if prov: rec["extraction_provenance"] = prov
    elif lc is not None:
        rec["lora_config_raw"] = lc
    rec["optimizer"] = "N/A (SVD-extracted adapter — no training optimizer state)"
    other = {k: v for k, v in meta.items() if k != "lora_config"}
    if other: rec["safetensors_metadata"] = other
    return rec


def _optimizer_from_states(ck):
    """Pull lr/betas/weight_decay/eps from optimizer_states[0].param_groups[0]."""
    try:
        os_ = ck.get("optimizer_states")
        if not os_: return None
        pg = os_[0]["param_groups"][0]
        out = {}
        for f in ("lr", "betas", "weight_decay", "eps"):
            if f in pg: out[f] = pg[f]
        return out or None
    except Exception:
        return None


def extract_one(root, label, picks):
    pick = _pick_representative(root, label, picks)
    if pick is None:
        return {"_status": "unreachable",
                "_reason": "no pick exists on disk (broken symlink / cleaned drive path)",
                "_root": root, "_picks": picks}
    path = os.path.join(root, label, pick)
    size_mb = os.path.getsize(path) // 1024 // 1024
    if pick.endswith(".safetensors"):
        return extract_safetensors(pick, path, size_mb)
    t0 = time.time()
    try:
        ck = torch.load(path, map_location="cpu", weights_only=False)
    except Exception as e:
        return {"_status": "load_error", "_reason": f"{type(e).__name__}: {e}",
                "_source_ckpt": pick, "_size_mb": size_mb}
    load_s = round(time.time() - t0, 1)
    rec = {"_status": "ok", "_source_ckpt": pick, "_size_mb": size_mb,
           "_pruned_slim": pick.endswith(".weights.ckpt")}
    if not isinstance(ck, dict):
        rec["_status"] = "unexpected_shape"; rec["_reason"] = type(ck).__name__
        return rec
    rec["epoch"] = ck.get("epoch")
    rec["global_step"] = ck.get("global_step")
    if "avg_loss" in ck: rec["avg_loss"] = ck["avg_loss"]
    lc = ck.get("lora_config")
    sd = ck.get("state_dict")
    if isinstance(lc, dict):
        n_mods, rank_shapes = (_lora_target_modules(sd) if isinstance(sd, dict) else (None, None))
        rec["kind"] = "dora/lora"
        rec["lora_config"] = {k: lc.get(k) for k in ("rank", "alpha", "adapter_type", "dropout", "include", "exclude")}
        rec["target_modules_count"] = n_mods
        rec["rank_from_shapes"] = rank_shapes
        opt = _optimizer_from_states(ck)
        rec["optimizer"] = opt if opt else ("PRUNED (slim .weights.ckpt — no optimizer_states)"
                                            if rec["_pruned_slim"] else "not present in checkpoint")
    else:
        # control-adapter / LatCH / other: dump config-like top-level dicts
        rec["kind"] = "non-lora (control/latch/other)"
        for cand in ("args", "hparams", "hyper_parameters", "metadata", "config", "adapter_config"):
            if isinstance(ck.get(cand), dict):
                rec[cand] = ck[cand]
        if isinstance(sd, dict):
            rec["state_dict_tensors"] = len(sd)
            rec["state_dict_sample_keys"] = list(sd.keys())[:4]
        rec["_top_level_keys"] = [k for k in ck.keys() if k != "state_dict"]
    rec["_load_s"] = load_s
    # free memory before next checkpoint
    del ck
    if sd is not None: del sd
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only first N labels")
    ap.add_argument("--label", type=str, default=None, help="single label")
    ap.add_argument("--retry-failed", action="store_true",
                    help="reprocess ONLY labels whose staged _status != ok; update staging in place")
    args = ap.parse_args()

    manifest = json.load(open(MANIFEST))
    models = manifest["models"]
    items = list(models.items())
    if args.label:
        items = [(k, v) for k, v in items if k == args.label]
    if args.limit:
        items = items[:args.limit]

    out, t_start = {}, time.time()
    if args.retry_failed and STAGING.exists():
        out = json.load(open(STAGING))
        items = [(k, v) for k, v in items if out.get(k, {}).get("_status") != "ok"]
        print(f"retry-failed: reprocessing {len(items)} non-ok labels (keeping {len(out)-len(items)} ok)")
    counts = {"ok": 0, "unreachable": 0, "load_error": 0, "unexpected_shape": 0}
    for i, (label, v) in enumerate(items, 1):
        root = v.get("root") or _default_root()
        picks = v.get("picks") or []
        try:
            rec = extract_one(root, label, picks)
        except Exception as e:
            rec = {"_status": "exception", "_reason": f"{type(e).__name__}: {e}",
                   "_trace": traceback.format_exc()[-400:]}
        rec["_tier"] = v.get("tier"); rec["_manifest_skip"] = v.get("skip")
        out[label] = rec
        counts[rec.get("_status", "unexpected_shape")] = counts.get(rec.get("_status", "unexpected_shape"), 0) + 1
        st = rec.get("_status")
        extra = ""
        if st == "ok":
            if rec.get("kind", "").startswith("dora"):
                lc = rec.get("lora_config", {})
                extra = f"{rec.get('kind')} r{lc.get('rank')}/a{lc.get('alpha')} {lc.get('adapter_type')} " \
                        f"mods={rec.get('target_modules_count')} opt={'dict' if isinstance(rec.get('optimizer'),dict) else 'pruned'}"
            else:
                extra = rec.get("kind", "")
        print(f"[{i}/{len(items)}] {label:40s} {st:14s} {extra}  ({rec.get('_size_mb','-')}MB, {rec.get('_load_s','-')}s)")

    STAGING.write_text(json.dumps(out, indent=2, default=str, ensure_ascii=False))
    dt = round(time.time() - t_start, 1)
    print("\n=== coverage ===")
    for k, n in counts.items():
        if n: print(f"  {k}: {n}")
    print(f"  total labels processed: {len(items)}   wall: {dt}s")
    print(f"  staging written: {STAGING}")


if __name__ == "__main__":
    main()
