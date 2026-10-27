#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-10-27)
"""ema_deconv_clamp_magnitudes.py -- repair the DoRA magnitude vectors of a deconvolved checkpoint.

WHY. eval/ema_deconv_ckpt.py recovers an online-weight average from two EMA checkpoints. Its --report validates only the
adapter (the one place ground truth exists); the DoRA tensors have no ground truth, and they were NOT validated. On the
morph run (2026-10-27) the deconvolved magnitude vectors came out with entries <= 0 (0 at step 4000, 218 at 6000, 419 at
8000, 991 at 10000, 1598 at 12000, of 870,144) although every EMA original is strictly positive (min 0.008-0.056). The
division by (1 - b^D) amplifies the error about 4.5x and the small magnitudes flip sign. A negative magnitude flips a whole
row of the DoRA weight; the step-12000 render was all non-finite/clipped (peak exactly 1.0, even with null conditioning).

WHAT. For every tensor whose key path contains 'magnitude', entries below --floor in the deconvolved checkpoint are replaced
by the EMA checkpoint's value at the same position (positive by construction). Everything else is copied unchanged.
USAGE.  .venv/bin/python eval/ema_deconv_clamp_magnitudes.py --deconv R/deconv/riffer_step12000.pt \
            --ema R/riffer_step12000.pt --out R/deconv_clamped/riffer_step12000.pt
"""
import argparse, os, torch

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deconv", required=True)
    ap.add_argument("--ema", required=True, help="the EMA checkpoint of the SAME step (positive magnitudes)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--floor", type=float, default=1e-3, help="deconvolved magnitudes below this are replaced")
    a = ap.parse_args()
    d = torch.load(a.deconv, map_location="cpu", weights_only=False)
    e = torch.load(a.ema, map_location="cpu", weights_only=False)
    stats = {"tensors": 0, "replaced": 0, "total": 0}

    def walk(do, eo, path=""):
        if torch.is_tensor(do) and do.is_floating_point() and "magnitude" in path.lower():
            ev = eo
            if torch.is_tensor(ev) and ev.shape == do.shape:
                m = do < a.floor
                stats["tensors"] += 1; stats["total"] += do.numel(); stats["replaced"] += int(m.sum())
                return torch.where(m, ev.to(do.dtype), do)
            return do
        if isinstance(do, dict):
            return {k: walk(v, eo.get(k) if isinstance(eo, dict) else None, path + "/" + str(k)) for k, v in do.items()}
        return do

    out = walk(d, e)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    torch.save(out, a.out)
    print(f"[clamp] {os.path.basename(a.out)}: {stats['replaced']} of {stats['total']} magnitude entries "
          f"(< {a.floor}) replaced by the EMA value, in {stats['tensors']} tensors", flush=True)

if __name__ == "__main__":
    main()
