#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-28)
"""grad_noise_by_t_report.py -- read train_latch's grad_noise_by_t.jsonl (--log-grad-noise-t) for one or more runs.

Per run, per third of training (early / mid / late, by step), per flow-time bin (t = 0 clean ... 1 pure noise):
  cos      mean cosine of the two half-batch gradients (share of signal at half the batch; 1 = no noise)
  B_simple median of McCandlish's noise scale in samples (above the batch actually used = noise-dominated steps)
for the whole model and per kind of part, pooling every block: attn, mlp, adaLN_mod, norms, input projection, time embedder,
output projection. Single readings at a half of 2-8 items are noisy; the means here pool ~20-60 readings per cell.
RUN: python3 eval/grad_noise_by_t_report.py <run_dir> [<run_dir> ...]   (stdlib only; writes <run_dir>/grad_noise_by_t_summary.json)
"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path


def kind(part):
    if part.startswith("blocks."):
        return part.split(".")[2]
    return {"latent_proj": "input", "t_embedder": "t_embed", "out_proj": "output", "norm_final": "norm_final"}.get(part.split(".")[0], part)


def summarise(run):
    recs = [json.loads(l) for l in (run / "grad_noise_by_t.jsonl").read_text().splitlines() if l.strip()]
    if not recs:
        return None
    steps = [r["step"] for r in recs]
    lo, hi = min(steps), max(steps)
    third = lambda s: min(2, int(3 * (s - lo) / max(1, hi - lo + 1)))  # noqa: E731
    cos, bs = defaultdict(list), defaultdict(list)
    for r in recs:
        ph = ("early", "mid", "late")[third(r["step"])]
        for b in r["bins"]:
            tb = f"{b['t_lo']:.1f}-{b['t_hi']:.1f}"
            cos[(ph, tb, "ALL")].append(b["all"]["cos"])
            if b["all"]["b_simple"] is not None:
                bs[(ph, tb, "ALL")].append(b["all"]["b_simple"])
            per_kind = defaultdict(list)
            for p, v in b["parts"].items():
                per_kind[kind(p)].append(v["cos"])
            for k, v in per_kind.items():
                cos[(ph, tb, k)].append(st.mean(v))
    out = {"run": run.name, "readings": len(recs), "steps": [lo, hi], "b_half": recs[0]["b_half"],
           "cos": {"|".join(k): round(st.mean(v), 3) for k, v in cos.items()},
           "b_simple_median": {"|".join(k): round(st.median(v), 2) for k, v in bs.items()}}
    (run / "grad_noise_by_t_summary.json").write_text(json.dumps(out, indent=1))
    return out


def main():
    for d in sys.argv[1:]:
        s = summarise(Path(d))
        if not s:
            print(f"{d}: no readings")
            continue
        tbins = sorted({k.split("|")[1] for k in s["cos"]})
        kinds = sorted({k.split("|")[2] for k in s["cos"]}, key=lambda k: (k != "ALL", k))
        print(f"\n{s['run']}: {s['readings']} readings, steps {s['steps'][0]}-{s['steps'][1]}, half-batch {s['b_half']}")
        print("half-batch gradient cosine by flow time (t=0 clean, 1 noise); rows: part kind x training third")
        print(f"{'kind':12s} {'third':6s} " + " ".join(f"{t:>8s}" for t in tbins))
        for k in kinds:
            for ph in ("early", "mid", "late"):
                row = [s["cos"].get(f"{ph}|{t}|{k}") for t in tbins]
                if any(v is not None for v in row):
                    print(f"{k:12s} {ph:6s} " + " ".join(f"{v:8.3f}" if v is not None else f"{'-':>8s}" for v in row))
        print("B_simple (median, samples), whole model:")
        for ph in ("early", "mid", "late"):
            print(f"{'ALL':12s} {ph:6s} " + " ".join(f"{s['b_simple_median'].get(f'{ph}|{t}|ALL', float('nan')):8.1f}" for t in tbins))


if __name__ == "__main__":
    main()
