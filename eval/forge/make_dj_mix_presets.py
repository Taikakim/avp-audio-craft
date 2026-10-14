#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-13)
"""One Latent Forge MASTER preset per DJ-mix clip: the recipe that generated it, model included.

Each mixtape clip id is a model_matrix cell name (<arm>[_ptm]__<ckpt-tag>__cfg<c>__w<pct>__<prompt>
__s<seed>[__st<steps>]). The recipe is backtracked from:
  * the model_matrix manifest (prompt text, seed, cfg, steps, duration, EMA/online weights),
    preferring the 48 s (`__d48`) re-render the v6/v7 mixes were built from;
  * the checkpoint: the renderer's own bracket manifest (eval/model_matrix_gen.build_jobs), else
    the model census (eval/model_db) by run dir + epoch. `_repr` arms are the same run pulled to a
    second place (since consolidated), so they fall back to the plain arm;
  * the backbone: a `_ptm` arm was rendered on the post-trained `medium`, everything else on
    `medium-base` (model_matrix_gen --pt-medium).

The preset carries only `model`, `render` and `source`; it has no lanes/clips/mix/master, so a
recall leaves the arrangement alone and sets the session defaults + (after asking) the model.

  python3 eval/forge/make_dj_mix_presets.py                 # v7 32-clip mix, writes the presets
  python3 eval/forge/make_dj_mix_presets.py --dry-run       # print what it would write
"""
import argparse
import json
import re
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
SAO_EVAL = Path("/home/kim/Projects/SAO/eval")
MIXES = Path("/run/media/kim/Mantu2/sa3_lora_runs")
MANIFEST = Path.home() / "evals_aac/model_matrix/manifest.jsonl"
OUT = Path("/home/kim/Projects/sa3_render_out/_forge/presets/master")
NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
DEAD_MANTU = "/run/media/kim/Mantu/"


def parse_id(cid: str) -> dict:
    parts = cid.split("__")
    out = {"label": parts[0], "tag": parts[1]}
    for p in parts[2:]:
        if p.startswith("cfg"):
            out["cfg"] = float(p[3:])
        elif p.startswith("w") and p[1:].isdigit():
            out["strength"] = int(p[1:]) / 100
        elif p.startswith("st") and p[2:].isdigit():
            out["steps"] = int(p[2:])
        elif re.fullmatch(r"s\d+", p):
            out["seed"] = int(p[1:])
        elif p in ("ema", "online"):
            out["weights"] = p
        else:
            out.setdefault("prompt_id", p)
    return out


def manifest_entry(cid: str, rows: dict):
    """The d48 re-render the mixes used, else the base cell."""
    return rows.get(cid + "__d48") or rows.get(cid)


def ckpt_index() -> dict:
    sys.path.insert(0, str(SAO_EVAL))
    import model_matrix_gen as mm  # noqa: E402  (stdlib-only at import)
    import model_db  # noqa: E402
    mm.RUNS = MIXES                 # the bracket's Mantu root is a dead mount; Mantu2 is live
    idx = {}
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):   # build_jobs prints a skip line per missing pick
        for label, path, tag in mm.build_jobs():
            idx[(label, tag)] = str(path)
    census = {}
    for m in model_db.load_or_build()["models"]:
        if m.get("epoch") is None or not m.get("loadable", True):
            continue
        run = Path(m["path"]).parent.name
        key = (run, f"ep{m['epoch']}")
        # Prefer a slim .weights.ckpt over a fat one: same weights, a fraction of the read.
        if key not in census or m["path"].endswith(".weights.ckpt"):
            census[key] = (m["path"], m.get("family"))
    return idx, census


def resolve_ckpt(label: str, tag: str, idx: dict, census: dict):
    for cand in (label, label.removesuffix("_repr")):
        p = idx.get((cand, tag))
        if p and Path(p).exists():
            return p, census.get((Path(p).parent.name, tag), (None, None))[1]
        if p and p.startswith(DEAD_MANTU) and Path(p.replace(DEAD_MANTU, "/run/media/kim/Mantu2/")).exists():
            return p.replace(DEAD_MANTU, "/run/media/kim/Mantu2/"), None
        hit = census.get((cand, tag))
        if hit:
            return hit
    return None, None


def preset_for(i: int, cid: str, mix: str, rows: dict, idx: dict, census: dict):
    c = parse_id(cid)
    ptm = c["label"].endswith("_ptm")
    arm = c["label"].removesuffix("_ptm")
    e = manifest_entry(cid, rows)
    if e is None:
        return None, f"{cid}: not in the model_matrix manifest"
    if arm == "base":
        ckpt, family = None, None
    else:
        ckpt, family = resolve_ckpt(arm, c["tag"], idx, census)
        if ckpt is None:
            return None, f"{cid}: no checkpoint for {arm} {c['tag']}"
    name = NAME_RE.sub("-", f"dj-{mix}-{i:02d}-{arm}-{c['tag']}")[:80]
    return {
        "model": {"backbone": "medium" if ptm else "medium-base", "ckpt_path": ckpt,
                  "family": family, "strength": float(e.get("strength", c.get("strength", 1.0))),
                  "weights": e.get("weights")},
        "render": {"prompt": e["prompt_text"], "seed": int(e["seed"]), "cfg_scale": float(e["cfg"]),
                   "steps": int(e.get("steps") or c.get("steps") or 24),
                   "duration_sec": float(e["duration"])},
        "source": {"mix": mix, "position": i, "clip_id": cid, "file": e["file"],
                   "prompt_id": e["prompt_id"],
                   "note": "backtracked by eval/forge/make_dj_mix_presets.py from the model_matrix "
                           "manifest; the mix itself also bungee-stretched, clamp-decoded and "
                           "crossfaded this clip, none of which a preset recalls."},
    }, name


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--order", type=Path, default=MIXES / "mixtape_v7_phase0/order_used.json")
    ap.add_argument("--mix", default="v7", help="short mix tag used in the preset names")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    rows = {}
    for ln in MANIFEST.open():
        e = json.loads(ln)
        rows[Path(e["file"]).stem] = e
    idx, census = ckpt_index()
    order = json.loads(a.order.read_text())
    written, problems = 0, []
    for i, clip in enumerate(order, 1):
        preset, name_or_err = preset_for(i, clip["id"], a.mix, rows, idx, census)
        if preset is None:
            problems.append(name_or_err)
            continue
        if a.dry_run:
            m = preset["model"]
            print(f"{name_or_err}: {m['backbone']} {Path(m['ckpt_path'] or 'base').name} "
                  f"{preset['render']['steps']}st cfg{preset['render']['cfg_scale']}")
        else:
            a.out.mkdir(parents=True, exist_ok=True)
            (a.out / f"{name_or_err}.json").write_text(json.dumps(preset, indent=1))
        written += 1
    print(f"{written}/{len(order)} presets {'(dry run)' if a.dry_run else '-> ' + str(a.out)}")
    for p in problems:
        print("  SKIPPED", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
