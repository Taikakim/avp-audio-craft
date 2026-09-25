#!/usr/bin/env python3
"""Print a readable summary of flight-recorder incidents (stdlib only, any python).

    python3 eval/inspect_flight_incident.py <run_dir>                 # every incident in the run
    python3 eval/inspect_flight_incident.py <run_dir>/incidents/step_0001268

Incidents are written by stable-audio-3/stable_audio_3/training/flight_recorder.py
(train_lora_modular.py --flight-recorder). What to look for, in order:
  1. trigger: nonfinite_grad = the step was already broken; raw_norm_z = an outsized gradient.
  2. previous_steps: a lone spike (calm before) vs a ramp (norm rising for several steps --
     that is drift, not a bad batch, and points at the model rather than the data).
  3. batch t: a cluster at one end of [0,1] points at the timestep sampler.
  4. top_params: whether one module family dominates (e.g. to_global_embed, a single block).
  5. prompts / files: repeated across incidents = a bad item; re-listen to it.
"""
import json
import os
import sys


def show(d):
    rep = json.load(open(os.path.join(d, "incident.json")))
    m = rep.get("metrics", {})
    print("=" * 78)
    z = rep.get("z")
    print(f"step {rep['step']}  trigger={rep['trigger']}  z={z if z is None else round(z, 2)}"
          f"  (threshold {rep.get('z_thresh')})")
    med = rep.get("rolling_median_norm")
    tot = m.get("grad/raw_norm_total")
    if med and tot:
        print(f"raw grad norm {tot:.4g}  vs rolling median {med:.4g}  ({tot / med:.1f}x)")
    for k in ("lora_A", "lora_B", "magnitude", "other"):
        v = m.get(f"grad/raw_norm_{k}")
        if v is not None:
            print(f"   {k:10s} {v:.4g}")
    if rep.get("n_nonfinite_params"):
        print(f"NON-FINITE grads in {rep['n_nonfinite_params']} tensors, e.g. {rep['nonfinite_params'][:3]}")
    prev = rep.get("previous_steps", [])
    if prev:
        print("previous steps (step: norm / loss):  " + "  ".join(
            f"{p['step']}: {p['raw_norm_total']:.3g}/{p['loss'] if p['loss'] is None else round(p['loss'], 4)}"
            for p in prev))
    b = rep.get("batch", {})
    t = b.get("t") or []
    if t:
        lo = sum(1 for x in t if x < 0.05)
        hi = sum(1 for x in t if x > 0.95)
        print(f"batch: n={len(t)}  loss={b.get('loss')}  t min/mean/max = {min(t):.3f}/{sum(t)/len(t):.3f}/{max(t):.3f}"
              f"  (t<0.05: {lo}, t>0.95: {hi})")
    print("top params by grad norm (share of squared total):")
    for tp in rep.get("top_params", [])[:8]:
        sh = tp.get("share_of_sq")
        print(f"   {tp['grad_norm']:10.4g}  {'  n/a ' if sh is None else f'{100*sh:5.1f}%'}  {tp['param']}")
    for i, (p, f) in enumerate(zip(b.get("prompts") or [], b.get("files") or [])):
        print(f"   [{i}] t={t[i]:.3f}  {os.path.basename(str(f))}  |  {str(p)[:90]}" if i < len(t) else f"   [{i}] {p}")
    if b.get("note"):
        print(f"note: {b['note']}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    arg = sys.argv[1].rstrip("/")
    if os.path.isfile(os.path.join(arg, "incident.json")):
        dirs = [arg]
    else:
        root = os.path.join(arg, "incidents") if os.path.isdir(os.path.join(arg, "incidents")) else arg
        dirs = sorted(os.path.join(root, x) for x in os.listdir(root)
                      if os.path.isfile(os.path.join(root, x, "incident.json")))
    if not dirs:
        sys.exit(f"no incidents under {arg}")
    for d in dirs:
        show(d)
    print("=" * 78)
    print(f"{len(dirs)} incident(s)")


if __name__ == "__main__":
    main()
