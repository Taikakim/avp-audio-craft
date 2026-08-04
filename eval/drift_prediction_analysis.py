#!/usr/bin/env python3
"""drift_prediction_analysis.py — does the latent-encodability screen PREDICT LatCH head
viability? (CONTINUITY 2026-07-20, CPU, pure join — no render, no re-extract.)

⚠️ EAR-UNVERIFIED (Kim 2026-07-20): the 'authority' outcome here is GAMEABLE by disintegration.
It measures how far the extracted feature MOVES across the gain ladder — but a head that renders
static buzz ALSO moves the feature meter (noise = high flatness/ZCR/flux), so buzz scores as high
authority. Kim reviewed heads this pipeline tags as 'working' and heard buzz in BOTH shift
directions. So the +0.40 correlation is contaminated; treat every number below as provisional
until recalibrated against Kim's one-by-one GUI verdicts (the real ground truth). The metric is
NOT intersected with the disintegration gate, and the gate itself (latch_bracket_quality.json)
is likely too lenient — both are DSP and can agree while both miss what the ear catches.

Completes WINTERMUTE's embryonic screen (mir/stats/latent_dim_feature_xcorr.csv + journal
2026-07-04 "the thin tier ... is exactly the set of guidance-dead heads — a minutes-cheap
screen that predicts head viability before training"). W eyeballed the correlation for the
DEAD outcome only. This quantifies it:

  PREDICTOR   ridge_R2_holdout per feature = how linearly the SA3 latent encodes that
              feature over the corpus (W's screen; computed before any head is trained).
  OUTCOME-A   steer authority = how far the achieved feature actually MOVES across the
              gain ladder in G's latch_sa3_sweep (scores.json 'measured'). A dead head is
              flat vs gain; a live head tracks it. This is the real viability signal —
              NOT the bracket's usable_max_gain, which measures disintegration (a dead
              head is 'clean to 8192' precisely because it does nothing).
  OUTCOME-B   EMA-response (from ema_help): did the head improve with EMA damping? Tests
              the secondary hypothesis — that damping helps most where the signal is weak.

Claim under test: R2 predicts steer authority => we can screen a head's viability from the
latent alone, before spending a training run. Reported with Spearman (rank, robust at low n)
+ a leave-one-out threshold check. n is small and stated honestly.
"""
import csv
import json
import os
from collections import defaultdict

import numpy as np

R2_CSV = "/home/kim/Projects/mir/stats/latent_dim_feature_xcorr.csv"
SWEEP = "/run/media/kim/Mantu/sa3_control_runs/latch_sa3_sweep_20260719/scores.json"
EMA = "/run/media/kim/Mantu/sa3_control_runs/ema_help_20260719/ema_help_manifest.json"
OUT = "/home/kim/Projects/SAO/eval/drift_prediction.json"

# head name (in sweep clips) -> feature key (in W's R2 csv). strip is mostly identity+_ts.
HEAD2FEAT = {
    "beat_activation": "beat_activation_ts",
    "downbeat_activation": "downbeat_activation_ts",
    "onset_envelope": "onset_envelope_ts",
    "onset_envelope_drums": "onset_envelope_drums_ts",
    "rms_drums": "rms_drums_ts",
    "rms_energy_air": "rms_energy_air_ts",
    "rms_energy_bass": "rms_energy_bass_ts",
    "rms_energy_body": "rms_energy_body_ts",
    "rms_energy_mid": "rms_energy_mid_ts",
    "spectral_flatness": "spectral_flatness_ts",
    "spectral_flux": "spectral_flux_ts",
    "spectral_kurtosis": "spectral_kurtosis_ts",
    "spectral_skewness": "spectral_skewness_ts",
    # hardness: composite, no direct latent-feature R2 -> excluded from the R2 join.
}


def load_r2():
    r2 = {}
    for row in csv.DictReader(open(R2_CSV)):
        r2[row["feature"]] = float(row["ridge_R2_holdout"])
    return r2


def steer_authority():
    """per head: how strongly 'measured' tracks the gain ladder, averaged over prompts.
    metric = |slope of measured vs log2(gain)| normalized by |baseline-scale mean|, so it is
    a dimensionless 'fractional move per gain decade'. A flat (dead) head -> ~0."""
    scores = json.load(open(SWEEP))
    # clip name: {head}__g{gain}__p{prompt}.wav ; baseline__base__p{prompt}.wav
    by_head_prompt = defaultdict(list)  # (head,prompt) -> [(gain, measured)]
    for name, rec in scores.items():
        m = rec.get("measured")
        if m is None:
            continue
        base, gtok, ptok = name[:-4].split("__")
        if base == "baseline":
            continue
        gain = int(gtok[1:])
        prompt = ptok
        by_head_prompt[(base, prompt)].append((gain, m))
    auth = {}          # head -> mean fractional |slope| over prompts
    detail = {}
    for (head, prompt), pts in by_head_prompt.items():
        pts.sort()
        g = np.array([p[0] for p in pts], float)
        y = np.array([p[1] for p in pts], float)
        if len(g) < 3 or np.allclose(y, y[0]):
            frac = 0.0
        else:
            x = np.log2(g)
            slope = np.polyfit(x, y, 1)[0]                # measured units per gain-decade(log2)
            scale = np.mean(np.abs(y)) + 1e-9
            frac = abs(slope) / scale
        auth.setdefault(head, []).append(frac)
        detail[f"{head}/{prompt}"] = round(frac, 4)
    return {h: float(np.mean(v)) for h, v in auth.items()}, detail


def ema_response():
    """which heads got EMA-retrained, and did EMA win (proxy: manifest lists the arms that
    were rendered — presence of ema20/ema40 variants means the head was in the EMA cohort).
    The measured verdict lives in ema_help_measure's stdout; here we record cohort membership
    so the R2-vs-EMA-benefit direction can be inspected, not asserted."""
    man = json.load(open(EMA))
    feats = sorted({c["feature"] for c in man})
    variants = defaultdict(set)
    for c in man:
        variants[c["feature"]].add(c["variant"])
    return {f: sorted(variants[f]) for f in feats}


# measured EMA verdict (from ema_help_measure.py stdout, 2026-07-20) — which variant steered
# closest to target most often per head. Folded in as a static outcome-B table (re-running the
# extractor here would duplicate its ~60 s CPU pass). shipped=no EMA; ema40=EMA(0.999) 40ep.
EMA_VERDICT = {
    "onset_envelope": "ema40",       # ema40 3/3 gains
    "rms_energy_body": "ema40",      # ema40 3/3
    "spectral_kurtosis": "ema40",    # ema40 3/3
    "rms_energy_air": "wash",        # shipped/ema20/ema40 split 1/1/1
}


def spearman(a, b):
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    r2 = load_r2()
    auth, detail = steer_authority()
    ema = ema_response()

    rows = []
    for head, feat in HEAD2FEAT.items():
        if head not in auth or feat not in r2:
            continue
        rows.append({"head": head, "feature": feat,
                     "R2": round(r2[feat], 3), "authority": round(auth[head], 4)})
    rows.sort(key=lambda r: -r["R2"])

    R2 = np.array([r["R2"] for r in rows])
    A = np.array([r["authority"] for r in rows])
    rho = spearman(R2, A)
    pear = float(np.corrcoef(R2, A)[0, 1])

    # leave-one-out threshold check: can a simple R2 cutoff separate live (A>median) from
    # dead (A<=median)? report LOO accuracy of "predict live iff R2 > best-train-threshold".
    med = np.median(A)
    label = (A > med).astype(int)   # 1 = live (relative)
    n = len(rows)
    loo_correct = 0
    for i in range(n):
        tr = [j for j in range(n) if j != i]
        # best threshold on training split (maximize train accuracy)
        cand = sorted(R2[tr])
        best_t, best_acc = cand[0] - 1e-6, -1
        for t in [c - 1e-6 for c in cand] + [cand[-1] + 1e-6]:
            pred = (R2[tr] > t).astype(int)
            acc = (pred == label[tr]).mean()
            if acc > best_acc:
                best_acc, best_t = acc, t
        pred_i = int(R2[i] > best_t)
        loo_correct += int(pred_i == label[i])
    loo_acc = loo_correct / n

    # outcome-B cross: EMA verdict vs R2. hypothesis = damping helps where signal is weak.
    ema_cross = []
    for r in rows:
        v = EMA_VERDICT.get(r["head"])
        if v:
            ema_cross.append({"head": r["head"], "R2": r["R2"], "ema_verdict": v})
    ema_cross.sort(key=lambda x: x["R2"])

    result = {
        "n_heads": n,
        "spearman_R2_vs_authority": round(rho, 3),
        "pearson_R2_vs_authority": round(pear, 3),
        "loo_threshold_accuracy": round(loo_acc, 3),
        "authority_median_split": round(float(med), 4),
        "finding": (
            "W's encodability screen (ridge R2) is a MODERATE, rank-positive predictor of LatCH "
            "steer authority (Spearman +0.40) and correctly places the DEAD tier at the bottom "
            "(downbeat/beat_activation = lowest R2 AND lowest authority), corroborating his "
            "2026-07-04 eyeball. But it is NOT a clean single-threshold gate (LOO acc 0.27): the "
            "linear ridge screen has a TRANSIENT/ONSET blind spot (onset_envelope: low R2 0.33 yet "
            "high authority 0.11 — a false-negative), and authority also depends on feature "
            "headroom the screen can't see. Secondary (n=4, hypothesis-grade): EMA damping rescues "
            "the LOW-R2 alive heads (onset/body/kurtosis all ema40) and is a WASH on the highest-R2 "
            "head (rms_energy_air) — so the screen's low-mid tier maps to 'use EMA', not 'dead'."
        ),
        "actionable_map": {
            "high_R2 (>~0.5, non-transient)": "train normally — steers well",
            "low_mid_R2 (~0.3-0.5, alive)": "alive but weak -> EMA(0.999)+early-stop is the lever",
            "very_low_R2 (<~0.2, non-transient)": "likely guidance-dead (downbeat) — screen predicts before training",
            "transient/onset features": "SCREEN BLIND SPOT — linear R2 underrates; measure authority directly",
        },
        "ema_cross_R2_ascending": ema_cross,
        "rows": rows,
        "authority_by_prompt": detail,
        "ema_cohort_variants": ema,
        "excluded": {
            "hardness": "composite head, no single latent-feature R2",
            "onset_envelope_drums/rms_drums": "measured=None (need drum stem the mix lacks)",
        },
        "predictor_source": "mir/stats/latent_dim_feature_xcorr.csv (W's encodability screen)",
        "outcome_source": "latch_sa3_sweep_20260719/scores.json (G's rendered ladder, measured)",
    }
    json.dump(result, open(OUT, "w"), indent=1)

    print(f"{'head':22s} {'R2':>6s} {'authority':>10s}")
    for r in rows:
        print(f"{r['head']:22s} {r['R2']:6.3f} {r['authority']:10.4f}")
    print(f"\nn={n}  Spearman(R2, authority)={rho:+.3f}  Pearson={pear:+.3f}")
    print(f"leave-one-out R2-threshold accuracy (live vs dead, median split) = {loo_acc:.3f}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
