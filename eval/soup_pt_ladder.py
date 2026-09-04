#!/usr/bin/env python3
"""Blend post-trained `medium` toward `medium-base` — a dial on "how much post-training".

WHY (Kim 2026-09-04): the PT model "gets some things right, like a coherent, punchy sound",
but "always sounds more or less the same with the kick, bass and percussions". This rewinds
post-training partially instead of choosing between the two models.

WHY LINEAR INTERPOLATION IS LEGITIMATE HERE, when our earlier soups were "nuanced, not a
clean win" (C1/C2): those souped INDEPENDENTLY TRAINED models. PT was produced BY
fine-tuning base, so the two lie on one trajectory — the linear-mode-connectivity regime
where weight interpolation is well behaved. MEASURED before building this (2026-09-04):
997 tensors, identical names and shapes, median relative delta ||PT-base||/||base|| =
0.0013, median cosine 1.0000, only 6 of 899 tensors below cos 0.9. Post-training barely
moved the weights, so the "ping-pong denoiser" worry (PT is a few-step rf_denoiser) does
NOT put it in a different basin.

THE DELTA IS CONCENTRATED, which is what makes --targeted worth having: the six
most-changed tensors are all `to_local_embed.0.bias` in layers 16-19 (relative delta
0.56-0.71) — the LOCAL CONDITIONING embedding of the upper-middle blocks. Post-training
reads as a targeted edit to how local conditioning enters those layers, which is a
plausible mechanism for "punchy but the rhythm layer always sounds the same". --targeted
holds those tensors at a different alpha from the rest, to test whether punch and sameness
are separable at all.

    W(a) = W_base + a * (W_PT - W_base)          a=0 -> base, a=1 -> PT

  eval/soup_pt_ladder.py --alpha 0.5 --out /run/media/kim/Mantu/soups/ptm_a050
  eval/soup_pt_ladder.py --alpha 1.0 --targeted-alpha 0.0 --out .../ptm_a100_local000

⚠ 8.6 GB per blend. Build one, render it, delete it — do not materialise the whole ladder.
⚠ PT is a few-step ping-pong denoiser (render with --steps 8) while base is a normal
   multi-step sampler. An intermediate alpha belongs to NEITHER sampler by default: render
   each blend under BOTH settings rather than assuming one carries over.
"""
import argparse, json, os, re, shutil, sys
from pathlib import Path

HUB = Path.home() / ".cache/huggingface/hub"
PT = HUB / "models--stabilityai--stable-audio-3-medium/snapshots"
BASE = HUB / "models--stabilityai--stable-audio-3-medium-base/snapshots"
DEFAULT_TARGET = r"to_local_embed.*bias"


def snap(p: Path) -> Path:
    d = [x for x in p.iterdir() if x.is_dir()]
    if len(d) != 1:
        sys.exit(f"expected one snapshot dir under {p}, found {len(d)}")
    return d[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alpha", type=float, required=True,
                    help="0 = medium-base, 1 = post-trained medium")
    ap.add_argument("--targeted-alpha", type=float, default=None,
                    help="separate alpha for tensors matching --targeted-regex "
                         "(default regex = the local-conditioning biases post-training moved most)")
    ap.add_argument("--targeted-regex", default=DEFAULT_TARGET)
    ap.add_argument("--out", type=Path, default=None,
                    help="output model dir; not needed with --dry-run")
    ap.add_argument("--dry-run", action="store_true", help="report the blend, write nothing")
    a = ap.parse_args()

    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file

    ps, bs = snap(PT), snap(BASE)
    rx = re.compile(a.targeted_regex)
    blended, n_t = {}, 0
    with safe_open(ps / "model.safetensors", "pt") as fp, \
         safe_open(bs / "model.safetensors", "pt") as fb:
        keys = list(fp.keys())
        if set(keys) != set(fb.keys()):
            sys.exit("PT and base key sets differ — refusing to blend")
        for k in keys:
            tp, tb = fp.get_tensor(k), fb.get_tensor(k)
            if tp.shape != tb.shape:
                sys.exit(f"shape mismatch on {k}")
            al = a.alpha
            if a.targeted_alpha is not None and rx.search(k):
                al = a.targeted_alpha
                n_t += 1
            if al == 1.0:
                blended[k] = tp.clone()
            elif al == 0.0:
                blended[k] = tb.clone()
            else:
                blended[k] = (tb.float() + al * (tp.float() - tb.float())).to(tp.dtype)
    print(f"  tensors {len(blended)}   alpha {a.alpha}"
          + (f"   targeted alpha {a.targeted_alpha} on {n_t} tensors "
             f"(/{a.targeted_regex}/)" if a.targeted_alpha is not None else ""))

    # IDENTITY CHECK — a blend at a pure endpoint must reproduce that endpoint EXACTLY.
    # Cheap, and it is the only thing that catches a dtype/aliasing mistake before 8.6 GB
    # of wrong weights get rendered and listened to.
    if a.targeted_alpha is None and a.alpha in (0.0, 1.0):
        src = ps if a.alpha == 1.0 else bs
        with safe_open(src / "model.safetensors", "pt") as f:
            bad = [k for k in list(blended)[:64] if not torch.equal(blended[k], f.get_tensor(k))]
        if bad:
            sys.exit(f"identity check FAILED at alpha={a.alpha}: {bad[:3]}")
        print(f"  identity check OK (alpha={a.alpha} reproduces the endpoint exactly)")

    if a.dry_run:
        print("  --dry-run: nothing written")
        return
    if a.out is None:
        sys.exit("--out is required unless --dry-run")
    a.out.mkdir(parents=True, exist_ok=True)
    save_file(blended, str(a.out / "model.safetensors"))
    shutil.copy2(ps / "model_config.json", a.out / "model_config.json")
    # symlink the text encoder rather than copying ~1.2 GB per blend
    t5 = ps / "t5gemma-b-b-ul2"
    if t5.exists() and not (a.out / t5.name).exists():
        os.symlink(t5, a.out / t5.name)
    (a.out / "BLEND.json").write_text(json.dumps(
        {"alpha": a.alpha, "targeted_alpha": a.targeted_alpha,
         "targeted_regex": a.targeted_regex, "n_targeted": n_t,
         "pt": str(ps), "base": str(bs),
         "note": "W = base + alpha*(PT-base). PT is a few-step ping-pong denoiser; render "
                 "intermediate alphas under BOTH sampler settings."}, indent=1) + "\n")
    gb = (a.out / "model.safetensors").stat().st_size / 2**30
    print(f"  wrote {a.out}  ({gb:.2f} GB)")


if __name__ == "__main__":
    main()
