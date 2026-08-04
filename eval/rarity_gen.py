#!/usr/bin/env python
"""rarity_gen.py — rarity-set generator + LUMI extension (reconstructed 2026-07-10).

The original scratchpad loop was lost; rebuilt from rarity_gen_set/clip_index.json (150
shared prompt/band/seed specs) + lumi/first-job-rarity-extension.md. LUMI-ready:
embarrassingly-parallel over the 15 model-variant grid with per-GCD sharding and
skip-if-exists resume — this is the FIRST real LUMI job (inference-only, zero-risk).

Grid = 15 model-variants x 150 specs = 2250 clips:
  base       x cfg{1,6,16}                 (3)   — no adapter, weight n/a
  evr1x      x weight{1.0,1.33} x cfg{...}  (6)
  newstack   x weight{1.0,1.33} x cfg{...}  (6)
Clip name: <source>_w<NNN>_cfg<C>__<band>__<promptid>__s<seed>.wav (G's board parses on __).

Run one GCD's shard:
  ... rarity_gen.py --out-dir <dir> --shard $i --shards 8 [--source .. --weight .. --cfg ..]
Pure grid/shard/naming logic is unit-tested (test_rarity_gen.py); the generate loop needs GPU.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import argparse, hashlib, json, sys
from pathlib import Path

MODELS = {          # source -> adapter ckpt (None = base, no adapter)
    "base": None,
    "evr1x": "dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt",
    "newstack": "dora16_goa_newstack_8ep/epoch=7-step=10800.ckpt",
}
CFGS = [1.0, 6.0, 16.0]
WEIGHTS = [1.0, 1.33]     # adapter DoRA strengths (base uses 1.0 sentinel)


def build_variants():
    """The 15 (source, weight, cfg) model-variants."""
    out = []
    for src in MODELS:
        weights = [1.0] if src == "base" else WEIGHTS
        for w in weights:
            for c in CFGS:
                out.append({"source": src, "weight": w, "cfg": c})
    return out


def promptid(prompt):
    return hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8]


def load_specs(clip_index_path):
    """The 150 shared (prompt, band, seed) specs (the 'base' rows of the gen set)."""
    d = json.load(open(clip_index_path))
    return [{"prompt": v["prompt"], "band": v["band"], "seed": int(v["seed"])}
            for v in d.values() if v.get("source") == "base"]


def build_grid(variants, specs):
    grid = []
    for var in variants:
        for sp in specs:
            grid.append({**var, "prompt": sp["prompt"], "band": sp["band"],
                         "seed": sp["seed"], "promptid": promptid(sp["prompt"])})
    return grid


def clip_name(g):
    return (f"{g['source']}_w{int(round(g['weight'] * 100)):03d}_cfg{int(g['cfg'])}"
            f"__{g['band']}__{g['promptid']}__s{g['seed']}.wav")


def select(grid, shard=0, shards=1, source=None, weight=None, cfg=None):
    """Optional variant filters, then round-robin shard slice (GCD assignment)."""
    g = grid
    if source:
        g = [x for x in g if x["source"] == source]
    if weight is not None:
        g = [x for x in g if abs(x["weight"] - weight) < 1e-6]
    if cfg is not None:
        g = [x for x in g if abs(x["cfg"] - cfg) < 1e-6]
    return [x for i, x in enumerate(g) if i % shards == shard]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--runs-root", default="/run/media/kim/Mantu/sa3_lora_runs",
                    help="prefix for adapter ckpts (LUMI: point at /project staging)")
    ap.add_argument("--clip-index", default=None,
                    help="clip_index.json with the 150 base specs (default: <runs-root>/rarity_gen_set/clip_index.json)")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--source", default=None)      # optional variant filters
    ap.add_argument("--weight", type=float, default=None)
    ap.add_argument("--cfg", type=float, default=None)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--seed-fallback", type=int, default=0)
    ap.add_argument("--no-skip", action="store_true", help="re-render even if the wav exists")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    ci = args.clip_index or f"{args.runs_root}/rarity_gen_set/clip_index.json"
    grid = build_grid(build_variants(), load_specs(ci))
    mine = select(grid, args.shard, args.shards, args.source, args.weight, args.cfg)
    todo = [g for g in mine if args.no_skip or not (args.out_dir / clip_name(g)).exists()]
    print(f"[rarity_gen] shard {args.shard}/{args.shards}: {len(mine)} assigned, "
          f"{len(todo)} to render ({len(mine) - len(todo)} already exist)", flush=True)
    (args.out_dir / f"run_meta.shard{args.shard}.json").write_text(json.dumps(
        {"purpose": "rarity-set extension (LUMI first job): 15 model-variants x 150 specs; "
                    "DoRA weight 1.0/1.33 x cfg 1/6/16, rarity-lite scored downstream.",
         "shard": args.shard, "shards": args.shards, "filters": {"source": args.source,
         "weight": args.weight, "cfg": args.cfg}, "steps": args.steps, "duration": args.duration,
         "assigned": len(mine), "variants": build_variants()}, indent=2))
    if not todo:
        print("[rarity_gen] nothing to do", flush=True)
        return

    import torch  # noqa: E402
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
    from sa3_control.audio_io import save_audio          # noqa: E402
    from stable_audio_3 import StableAudioModel           # noqa: E402

    # group by (source, weight) so each adapter loads once
    def key(g):
        return (g["source"], g["weight"])
    todo.sort(key=key)
    model = None
    cur = None
    for g in todo:
        if key(g) != cur:
            del model
            if model is not None:
                torch.cuda.empty_cache()
            model = StableAudioModel.from_pretrained("medium-base", device="cuda")
            ck = MODELS[g["source"]]
            if ck:
                model.load_lora([f"{args.runs_root}/{ck}"])
                try: model.set_lora_strength(float(g["weight"]))
                except Exception: pass
            cur = key(g)
            print(f"[load] {g['source']} w={g['weight']}", flush=True)
        out = model.generate(prompt=g["prompt"], duration=args.duration, steps=args.steps,
                             cfg_scale=float(g["cfg"]), seed=int(g["seed"]), batch_size=1)
        save_audio(args.out_dir / clip_name(g), out[0].float().cpu(),
                   model.model.sample_rate, normalize=True)
    print("[rarity_gen] done", flush=True)


if __name__ == "__main__":
    main()
