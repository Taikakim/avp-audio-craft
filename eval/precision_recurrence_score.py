#!/usr/bin/env python
"""precision_recurrence_score.py -- fp32cmp vs bf16cmp whitened-chroma recurrence re-score
(CONTINUITY DM 2026-08-04, precision thread: does the anisotropy rounding at bf16 measurably
degrade melodic/harmonic recurrence vs fp32, on clips we already rendered -- zero new compute).

Same chroma_recurrence() methodology as melody_wall_analysis.py (whitened per-pitch-class chroma_cqt
self-similarity, off-diagonal >~2s band, HIGHER = more repeated pitch-class content = more hook-like).
Paired at matched (label_stem, ep, cfg, w, prompt, seed) cells -- label_stem strips the fp32cmp_/bf16cmp_
prefix so e.g. fp32cmp_avp_t512_bs8_lr1e4__ep3__cfg7__w100__rb_common_0__s786795416 pairs against the
bf16cmp twin of the same cell.

Clips live on Mantu (already-rendered matrix_cells corpus, NOT the LUMI-pull drive CONTINUITY's DM
pointed at -- those dirs on 9a410a1d only hold checkpoints for this arm, the actual wavs are the
model_matrix ingest on Mantu). Covers both MASTER variants CONTINUITY asked about (avp + goa,
t512_bs8_lr1e4) plus _ptm/_repr/_repr_ptm where both fp32/bf16 sides exist, so nothing is dropped
silently -- reported per variant-group.

Run (mir venv has librosa): /home/kim/Projects/mir/mir/bin/python eval/precision_recurrence_score.py
"""
import os, sys, glob, json, re, time
import numpy as np

RENDERS = "/run/media/kim/Mantu/sa3_lora_runs/model_matrix"
OUTDIR = "/home/kim/Projects/SAO/eval/precision_recurrence"
SR = 44100

PAIRS = [
    ("fp32cmp_avp_t512_bs8_lr1e4", "bf16cmp_avp_t512_bs8_lr1e4"),
    ("fp32cmp_avp_t512_bs8_lr1e4_ptm", "bf16cmp_avp_t512_bs8_lr1e4_ptm"),
    ("fp32cmp_avp_t512_bs8_lr1e4_repr", "bf16cmp_avp_t512_bs8_lr1e4_repr"),
    ("fp32cmp_avp_t512_bs8_lr1e4_repr_ptm", "bf16cmp_avp_t512_bs8_lr1e4_repr_ptm"),
    ("fp32cmp_goa_t512_bs8_lr1e4", "bf16cmp_goa_t512_bs8_lr1e4"),
    ("fp32cmp_goa_t512_bs8_lr1e4_ptm", "bf16cmp_goa_t512_bs8_lr1e4_ptm"),
]

CELL_RE = re.compile(r"^(?P<label>.+?)__ep(?P<ep>\d+)__cfg(?P<cfg>\d+)__w(?P<w>\d+)__(?P<prompt>.+?)__s(?P<seed>\d+)\.wav$")


def chroma_recurrence(y, sr):
    import librosa
    hop = 2048
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    if C.shape[1] < 8:
        return {"recurrence_mean": float("nan"), "recurrence_rate": float("nan")}
    mu = C.mean(axis=1, keepdims=True); sd = C.std(axis=1, keepdims=True) + 1e-6
    Cw = (C - mu) / sd
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
    if y.size < SR:
        return None
    r = chroma_recurrence(y, SR)
    r.update(dsp(y, SR))
    return r


def key_of(m):
    return (m["ep"], m["cfg"], m["w"], m["prompt"], m["seed"])


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

    all_labels = sorted({lbl for pair in PAIRS for lbl in pair})
    files = []
    for lbl in all_labels:
        files += sorted(glob.glob(os.path.join(RENDERS, f"{lbl}__*.wav")))
    files = [f for f in files if os.path.basename(f) not in done]
    print(f"[prec] {len(files)} clips to score ({len(done)} already done); labels={all_labels}", flush=True)

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
                print(f"[prec] FAIL {os.path.basename(f)}: {e!r}", flush=True)
            if sc is None:
                continue
            rec = {"file": os.path.basename(f), **m.groupdict(), **sc}
            jf.write(json.dumps(rec) + "\n"); jf.flush()
            if (i + 1) % 200 == 0:
                el = time.time() - t0
                print(f"[prec] {i+1}/{len(files)}  {el/(i+1):.2f}s/clip  ~{el/(i+1)*(len(files)-i-1)/60:.0f}min left", flush=True)

    rows = [json.loads(l) for l in open(jsonl)]
    by_label = {}
    for r in rows:
        by_label.setdefault(r["label"], {})[key_of(r)] = r

    METRICS = ["recurrence_rate", "recurrence_mean", "flatness", "hf", "zcr", "onsets_per_s"]
    summary = {}
    per_cell_deltas = []
    for fp32_lbl, bf16_lbl in PAIRS:
        fp32_cells = by_label.get(fp32_lbl, {})
        bf16_cells = by_label.get(bf16_lbl, {})
        common = sorted(set(fp32_cells) & set(bf16_cells))
        pair_key = f"{fp32_lbl} vs {bf16_lbl}"
        if not common:
            summary[pair_key] = {"n_matched": 0}
            continue
        deltas = {mt: [] for mt in METRICS}
        fp32v = {mt: [] for mt in METRICS}
        bf16v = {mt: [] for mt in METRICS}
        for k in common:
            a, b = fp32_cells[k], bf16_cells[k]
            row = {"pair": pair_key, "ep": k[0], "cfg": k[1], "w": k[2], "prompt": k[3], "seed": k[4]}
            for mt in METRICS:
                av, bv = a.get(mt), b.get(mt)
                if av is not None and bv is not None and np.isfinite(av) and np.isfinite(bv):
                    deltas[mt].append(av - bv)  # fp32 - bf16 (positive = fp32 has more recurrence)
                    fp32v[mt].append(av)
                    bf16v[mt].append(bv)
                    row[f"{mt}_fp32"] = av
                    row[f"{mt}_bf16"] = bv
                    row[f"{mt}_delta"] = av - bv
            per_cell_deltas.append(row)
        summary[pair_key] = {"n_matched": len(common)}
        for mt in METRICS:
            if deltas[mt]:
                summary[pair_key][f"{mt}_fp32_mean"] = round(float(np.mean(fp32v[mt])), 5)
                summary[pair_key][f"{mt}_bf16_mean"] = round(float(np.mean(bf16v[mt])), 5)
                summary[pair_key][f"{mt}_delta_fp32_minus_bf16"] = round(float(np.mean(deltas[mt])), 5)
                summary[pair_key][f"{mt}_delta_frac_fp32_higher"] = round(float(np.mean([d > 0 for d in deltas[mt]])), 3)

    with open(os.path.join(OUTDIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(OUTDIR, "per_cell_deltas.jsonl"), "w") as f:
        for row in per_cell_deltas:
            f.write(json.dumps(row) + "\n")

    lines = ["# fp32cmp vs bf16cmp precision re-score (whitened-chroma recurrence)",
             "Paired at matched (ep,cfg,w,prompt,seed) cells. delta = fp32 - bf16; positive = fp32 MORE recurrent.",
             "Same whitening caveat as the melody-wall readout (raw chroma cosine saturates).", ""]
    for fp32_lbl, bf16_lbl in PAIRS:
        pair_key = f"{fp32_lbl} vs {bf16_lbl}"
        s = summary.get(pair_key, {})
        if not s.get("n_matched"):
            lines.append(f"- **{pair_key}**: no matched cells"); continue
        rec_d = s.get("recurrence_rate_delta_fp32_minus_bf16")
        rec_p = s.get("recurrence_rate_delta_frac_fp32_higher")
        recm_d = s.get("recurrence_mean_delta_fp32_minus_bf16")
        fl_d = s.get("flatness_delta_fp32_minus_bf16")
        hf_d = s.get("hf_delta_fp32_minus_bf16")
        verdict = ("fp32 MORE recurrent" if (rec_d and rec_d > 0 and rec_p and rec_p > 0.55)
                   else ("~flat" if rec_d is not None and abs(rec_d) < 0.003 else "bf16 MORE recurrent"))
        lines.append(f"- **{pair_key}** (n={s['n_matched']}): "
                     f"Δrecurrence_rate={rec_d:+.4f} ({rec_p:.0%} cells fp32-higher) "
                     f"Δrecurrence_mean={recm_d:+.4f} Δflatness={fl_d:+.4f} Δhf={hf_d:+.4f} -> **{verdict}**")
    with open(os.path.join(OUTDIR, "VERDICT.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines), flush=True)
    print(f"[prec] wrote {OUTDIR}/summary.json + VERDICT.md", flush=True)


if __name__ == "__main__":
    main()
