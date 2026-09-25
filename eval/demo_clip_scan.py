#!/usr/bin/env python3
"""demo_clip_scan.py — quick health check of a training run's demo clips (no GPU, no model).

For every <run>/demos/<milestone>/*.wav it prints:
  jumps   samples where the waveform jumps by more than --jump between neighbours. A clean
          clip scores 0-5; audible crackle is typically hundreds. (This is the check agents ran
          by hand on audition_160ep_2026-09-22-b and goa3_avp_r256_2026-09-23.)
  nonfin  NaN/Inf samples in the audio (should always be 0)
  crest   peak / rms (linear, not dB) -- a squashed/over-guided render reads low. Kim's ear closed
          one investigation on this alone: a narrow-window guidance clip he called "just distorted
          rumble" measured crest 2.21 against a clean arm's ~6 (MASTER.md sec5's target_raw
          section, 2026-08-28 audition). Ported here from the one-off
          scripts/render_standard_eval_grid.py (2026-09-21 VADD/discontinuity report), whose own
          compute_dsp_metrics() had this and jumps but nothing else this script didn't already have.
  z0std   std of the saved latent next to the clip (<clip>.z0.npy). Healthy renders sit around
          0.9-1.1; the crackling clips we have seen sat at 1.3-1.4. z0nan = non-finite latent
          values (a fully-NaN latent means the render diverged, e.g. the A x20 run's rb_mid_4_48s).

USAGE (SAO venv, any cwd):
  /home/kim/Projects/SAO/.venv/bin/python /home/kim/Projects/SAO/eval/demo_clip_scan.py <run_dir>
  ... --milestone step2536       # only one milestone folder
Exit code is 0 either way; read the table.
"""
import argparse
import glob
import os

import numpy as np
import soundfile as sf


def scan(path, jump):
    x, _ = sf.read(path)
    peak = float(np.nanmax(np.abs(x))) if x.size else float("nan")
    rms = float(np.sqrt(np.nanmean(np.square(x)))) if x.size else float("nan")
    row = {
        "jumps": int((np.abs(np.diff(x, axis=0)) > jump).sum()),
        "nonfin": int((~np.isfinite(x)).sum()),
        "peak": peak,
        "crest": peak / (rms + 1e-9) if x.size else float("nan"),
    }
    z_path = path[:-4] + ".z0.npy"
    if os.path.exists(z_path):
        z = np.load(z_path)
        row["z0std"] = float(np.nanstd(z))
        row["z0nan"] = int((~np.isfinite(z)).sum())
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("--milestone", default=None, help="e.g. step2536; default: all")
    ap.add_argument("--jump", type=float, default=0.6, help="sample-to-sample jump threshold")
    a = ap.parse_args()
    pattern = os.path.join(a.run_dir, "demos", a.milestone or "*", "*.wav")
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"no clips under {pattern}")
    print(f"{'clip':40s} {'jumps':>6s} {'nonfin':>6s} {'peak':>5s} {'crest':>6s} {'z0std':>6s} {'z0nan':>6s}")
    bad = 0
    for f in files:
        r = scan(f, a.jump)
        flag = r["jumps"] > 50 or r["nonfin"] or r.get("z0nan", 0)
        bad += bool(flag)
        print(f"{os.path.relpath(f, os.path.join(a.run_dir, 'demos')):40s} {r['jumps']:6d} {r['nonfin']:6d} "
              f"{r['peak']:5.2f} {r['crest']:6.2f} {r.get('z0std', float('nan')):6.2f} {r.get('z0nan', -1):6d}"
              f"{'   <-- listen for crackle' if flag else ''}")
    print(f"\n{len(files)} clips, {bad} flagged (jumps > 50 or any NaN).")


if __name__ == "__main__":
    main()
