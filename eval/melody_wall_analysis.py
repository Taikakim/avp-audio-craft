#!/usr/bin/env python
"""melody_wall_analysis.py — audio readout for the melody-wall campaign (#59 subspace-loss + E1a
x0-equiv), CONTINUITY 2026-08-04 (autonomous, Kim asleep). Answers the #59 hypothesis: does
upweighting the melody subspace (subloss K2/5/12) or removing the isotropic floor (x0-equiv) produce
MORE within-clip melodic REPETITION (the "hook" axis) at comparable texture quality, vs the
lreq_goa_lr1e4 baseline?

Per clip (matched cell = label__ep__cfg__w__prompt__seed):
  - chroma_recurrence : within-clip melodic/harmonic self-similarity (the hook proxy). librosa
      chroma_cqt -> beat-agnostic frame self-similarity (cosine) -> mean recurrence at lag>=~2s
      (excludes the trivial near-diagonal). HIGHER = more repeated pitch-class content = more hook-like.
  - flatness / hf / zcr / onsets : texture + health (disintegration screen), so a recurrence gain
      isn't just droning/whitening.
Aggregates per (arm, ep) over the cells common to that arm AND the baseline; reports paired deltas.
Streams per-clip to a JSONL (crash-safe) then writes the summary JSON + a short markdown verdict.

Run (mir venv has librosa):  /home/kim/Projects/mir/mir/bin/python eval/melody_wall_analysis.py
"""
import os, sys, glob, json, re, time
import numpy as np

RENDERS = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/matrix_cells"
OUTDIR = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/analysis/melody_wall"
BASELINE = "lreq_goa_lr1e4"
ARMS = ["x0eq_goa", "x0eq_sub5_goa", "subloss_goa_k2", "subloss_goa_k5", "subloss_goa_k12"]
SR = 44100

CELL_RE = re.compile(r"^(?P<label>.+?)__ep(?P<ep>\d+)__cfg(?P<cfg>\d+)__w(?P<w>\d+)__(?P<prompt>.+?)__s(?P<seed>\d+)\.wav$")


def chroma_recurrence(y, sr):
    import librosa
    # Whitened-chroma self-similarity recurrence. RAW chroma cosine saturates (~0.95 for everything
    # — the static harmonic bed dominates), so WHITEN per pitch-class over time (z-score) to score the
    # MOVING melodic/harmonic content's recurrence, not the constant bed (W's whitened-patch lesson).
    # recurrence_rate = fraction of off-band frame-pairs with strong similarity (>0.5) = returning
    # motifs (the "hook" axis). recurrence_mean = overall. Off-diagonal band (~2s) excludes local
    # continuity. NB harmonic/melodic proxy (chroma), not lead-isolated.
    hop = 2048
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)  # [12, T]
    if C.shape[1] < 8:
        return {"recurrence_mean": float("nan"), "recurrence_rate": float("nan")}
    mu = C.mean(axis=1, keepdims=True); sd = C.std(axis=1, keepdims=True) + 1e-6
    Cw = (C - mu) / sd                                          # whiten per pitch-class
    Cn = Cw / (np.linalg.norm(Cw, axis=0, keepdims=True) + 1e-8)
    S = Cn.T @ Cn
    T = S.shape[0]
    band = max(1, int(round(2.0 * sr / hop)))
    mask = np.abs(np.subtract.outer(np.arange(T), np.arange(T))) > band
    vals = S[mask]
    if vals.size == 0:
        return {"recurrence_mean": float("nan"), "recurrence_rate": float("nan")}
    return {"recurrence_mean": float(np.mean(vals)), "recurrence_rate": float(np.mean(vals > 0.5))}


def dsp(y, sr):
    import librosa
    Sx = np.abs(librosa.stft(y, n_fft=2048))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    hf = float(Sx[freqs >= 6000].sum() / (Sx.sum() + 1e-8))
    flat = float(np.mean(librosa.feature.spectral_flatness(S=Sx)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    dur = len(y) / sr
    ops = float(len(onsets) / dur) if dur > 0 else 0.0
    return {"flatness": flat, "hf": hf, "zcr": zcr, "onsets_per_s": ops}


def score_clip(path):
    import librosa
    y, _ = librosa.load(path, sr=SR, mono=True)
    if y.size < SR:  # <1s = broken
        return None
    r = chroma_recurrence(y, SR)
    r.update(dsp(y, SR))
    return r


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    jsonl = os.path.join(OUTDIR, "per_clip.jsonl")
    done = set()
    if os.path.exists(jsonl):
        for ln in open(jsonl):
            try:
                done.add(json.loads(ln)["file"])
            except Exception:
                pass
    labels = [BASELINE] + ARMS
    files = []
    for lbl in labels:
        files += sorted(glob.glob(os.path.join(RENDERS, f"{lbl}__*.wav")))
    files = [f for f in files if os.path.basename(f) not in done]
    print(f"[mw] {len(files)} clips to score ({len(done)} already done); labels={labels}", flush=True)

    t0 = time.time()
    with open(jsonl, "a") as jf:
        for i, f in enumerate(files):
            m = CELL_RE.match(os.path.basename(f))
            if not m:
                continue
            try:
                sc = score_clip(f)
            except Exception as e:
                sc = None
                print(f"[mw] FAIL {os.path.basename(f)}: {e!r}", flush=True)
            if sc is None:
                continue
            rec = {"file": os.path.basename(f), **m.groupdict(), **sc}
            jf.write(json.dumps(rec) + "\n"); jf.flush()
            if (i + 1) % 200 == 0:
                el = time.time() - t0
                print(f"[mw] {i+1}/{len(files)}  {el/ (i+1):.2f}s/clip  ~{el/(i+1)*(len(files)-i-1)/60:.0f}min left", flush=True)

    # ---- aggregate: per (label, ep, cfg, w) mean, then paired arm-vs-baseline deltas at common cells
    rows = [json.loads(l) for l in open(jsonl)]
    def key(r):  # matched-cell key EXCLUDING label
        return (r["ep"], r["cfg"], r["w"], r["prompt"], r["seed"])
    by_label = {}
    for r in rows:
        by_label.setdefault(r["label"], {})[key(r)] = r
    base = by_label.get(BASELINE, {})
    METRICS = ["recurrence_rate", "recurrence_mean", "flatness", "hf", "zcr", "onsets_per_s"]
    summary = {}
    for arm in ARMS:
        cells = by_label.get(arm, {})
        common = [k for k in cells if k in base]
        if not common:
            summary[arm] = {"n_matched": 0}
            continue
        deltas = {mt: [] for mt in METRICS}
        absv = {mt: [] for mt in METRICS}
        for k in common:
            for mt in METRICS:
                a, b = cells[k].get(mt), base[k].get(mt)
                if a is not None and b is not None and np.isfinite(a) and np.isfinite(b):
                    deltas[mt].append(a - b)
                    absv[mt].append(a)
        summary[arm] = {"n_matched": len(common)}
        for mt in METRICS:
            if deltas[mt]:
                summary[arm][f"{mt}_arm_mean"] = round(float(np.mean(absv[mt])), 5)
                summary[arm][f"{mt}_delta_vs_base"] = round(float(np.mean(deltas[mt])), 5)
                summary[arm][f"{mt}_delta_frac_pos"] = round(float(np.mean([d > 0 for d in deltas[mt]])), 3)
    summary["_baseline"] = {"label": BASELINE,
                            **{f"{mt}_mean": round(float(np.mean([v.get(mt) for v in base.values()
                                if v.get(mt) is not None and np.isfinite(v.get(mt))])), 5) for mt in METRICS}}
    with open(os.path.join(OUTDIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # ---- markdown verdict
    lines = ["# Melody-wall audio readout (#59 subspace-loss + E1a x0-equiv)",
             f"baseline = {BASELINE}; each arm vs baseline at matched (ep,cfg,w,prompt,seed) cells.",
             "**Hook hypothesis: chroma_recurrence UP at comparable flatness/hf = melody upweighting worked.**", ""]
    b = summary["_baseline"]
    lines.append(f"baseline means: recurrence_rate={b['recurrence_rate_mean']}  recurrence_mean={b['recurrence_mean_mean']}  "
                 f"flatness={b['flatness_mean']}  hf={b['hf_mean']}")
    lines.append("")
    for arm in ARMS:
        s = summary[arm]
        if not s.get("n_matched"):
            lines.append(f"- **{arm}**: no matched cells"); continue
        rec_d = s.get("recurrence_rate_delta_vs_base"); rec_p = s.get("recurrence_rate_delta_frac_pos")
        fl_d = s.get("flatness_delta_vs_base"); hf_d = s.get("hf_delta_vs_base")
        verdict = "HOOK↑" if (rec_d and rec_d > 0 and rec_p and rec_p > 0.55) else ("~flat" if rec_d is not None and abs(rec_d) < 0.003 else "HOOK↓")
        lines.append(f"- **{arm}** (n={s['n_matched']}): Δrecurrence_rate={rec_d:+.4f} ({rec_p:.0%} cells up) "
                     f"| Δflatness={fl_d:+.4f} Δhf={hf_d:+.4f} -> **{verdict}**")
    with open(os.path.join(OUTDIR, "VERDICT.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines), flush=True)
    print(f"[mw] wrote {OUTDIR}/summary.json + VERDICT.md", flush=True)


if __name__ == "__main__":
    main()
