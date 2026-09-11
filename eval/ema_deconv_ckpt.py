#!/usr/bin/env python3
"""ema_deconv_ckpt.py — recover ONLINE weights from a pair of EMA checkpoints.

WHY (CONTINUITY 2026-09-10). sa3_control/train.py initialises its EMA shadow from the params
AT CONSTRUCTION -- for a fresh adapter, the ZERO-INIT state -- and copy_to()s the shadow into
the modules before saving. So ck["state"] and ck["lora_state"] ARE the EMA, and at beta 0.999
per optimizer step the saved adapter is 77.9% zero-init at 250 steps and still 22.3% at 1500.
Worse than the dilution: it DECREASES MONOTONICALLY with step, so it is perfectly confounded
with training progress -- a trajectory A/B run on raw EMA checkpoints measures the EMA horizon
and reports it as learning.

ck["model_train"] holds the online ADAPTER but NOT the 684 dora tensors, so for a dora arm
there is no undiluted copy to fall back on. This recovers one arithmetically instead.

THE IDENTITY. Over a gap of D optimizer steps between two saves,
    s_t = b^D * s_{t-D} + (1-b) * sum_{k<D} b^k * theta_{t-k}
so  (s_t - b^D * s_{t-D}) / (1 - b^D)  is a normalised weighted average of the ONLINE weights
across that window, with the zero-init contribution removed EXACTLY.

WHAT IT IS NOT: the endpoint. It is a windowed average over the D steps between saves, and the
window is the residual error. VALIDATED where ground truth exists -- the adapter, which has both
sets -- at rel err 0.588 (raw EMA) -> 0.196 (deconvolved) on D17 step8000->10000.

CONDITIONING: the divisor is 1 - b^D. D17 (save 2000 micro, accum 8, D=250) gives 0.221, well
conditioned. D18 (save 500, D=62) gives 0.061, a ~16x amplification -- fine on exactly-stored
weights, but check --report before trusting a tighter gap or a longer beta.

  eval/ema_deconv_ckpt.py --ckpt <run>/riffer_step10000.pt --prev <run>/riffer_step8000.pt \
      --out <run>/deconv/riffer_step10000.pt
"""
import argparse, os, sys, math, torch

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True, help="the LATER checkpoint (s_t)")
    ap.add_argument("--prev", required=True, help="the EARLIER checkpoint (s_{t-D})")
    ap.add_argument("--out", required=True)
    ap.add_argument("--beta", type=float, default=None, help="default: read from the ckpt's args.ema")
    ap.add_argument("--report", action="store_true",
                    help="also print the validation against model_train (adapter only), which is "
                         "the one place ground truth exists")
    a = ap.parse_args()

    t = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    p = torch.load(a.prev, map_location="cpu", weights_only=False)
    args_t = t.get("args") or {}
    beta = a.beta if a.beta is not None else float(args_t.get("ema", 0.999))
    ga = int(args_t.get("grad_accum", 1) or 1)
    D = (int(t["step"]) - int(p["step"])) // ga          # gap in OPTIMIZER steps
    if D <= 0:
        sys.exit(f"--ckpt step {t['step']} must be AFTER --prev step {p['step']}")
    w = beta ** D
    if 1 - w < 1e-3:
        print(f"[warn] 1-b^D = {1-w:.2e}: the division amplifies by {1/(1-w):.0f}x. "
              f"Use a wider checkpoint gap.", flush=True)
    print(f"[deconv] beta {beta} accum {ga}  gap {D} optimizer steps  b^D {w:.4f}  "
          f"divisor {1-w:.4f}", flush=True)

    def deconv(dt, dp):
        out = {}
        for k, v in dt.items():
            if k in dp and torch.is_tensor(v) and v.is_floating_point():
                out[k] = ((v.double() - w * dp[k].double()) / (1 - w)).to(v.dtype)
            else:
                out[k] = v                                # non-float / unmatched: pass through
        return out

    new = dict(t)
    new["state"] = deconv(t["state"], p["state"])
    if t.get("lora_state") and p.get("lora_state"):
        new["lora_state"] = deconv(t["lora_state"], p["lora_state"])
    new["ema_deconvolved"] = {"beta": beta, "gap_optimizer_steps": D, "b_pow_D": w,
                              "from": os.path.basename(a.ckpt), "prev": os.path.basename(a.prev),
                              "note": "windowed average of the ONLINE weights; NOT the endpoint"}

    if a.report and t.get("model_train"):
        tt = t["model_train"]
        def rel(d):
            n = q = 0.0
            for k in tt:
                if k in d:
                    n += ((d[k].double() - tt[k].double()) ** 2).sum().item()
                    q += (tt[k].double() ** 2).sum().item()
            return math.sqrt(n / q) if q else float("nan")
        print(f"[validate] vs true online adapter -- raw EMA {rel(t['state']):.4f}  "
              f"deconvolved {rel(new['state']):.4f}", flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    torch.save(new, a.out)
    print(f"[deconv] wrote {a.out}", flush=True)

if __name__ == "__main__":
    sys.exit(main())
