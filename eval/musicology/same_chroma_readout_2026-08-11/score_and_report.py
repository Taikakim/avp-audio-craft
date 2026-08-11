#!/usr/bin/env python3
"""score_and_report.py -- Stage B of the same_chroma readout/ceiling test.

Reads the head-predicted 384-d chroma (Stage A, predict_head.py, SAO/.venv)
and scores it against three ground truths:
  1. audio-derived SAME chroma (compute_same_chroma on the render)          -- PRIMARY
  2. MIDI-note-derived per-frame pitch-class energy (mido)                  -- secondary
  3. transposition tracking on the chromatic sweeps                        -- register test
plus a timbre-invariance test (gm_timbre_pitch: fixed pattern, 120 GM
programs).

Reuses verbatim: compute_same_chroma / fold_to_12 (mir-same-chroma), the
cos12 time-averaged formula from eval/chroma384_eval.py, GM_NAMES /
family_name from eval/musicology/gm_timbre_pitch/pipeline.py.

Venv: mir (librosa/essentia/mido; soundfile for WAV I/O).
Run:
  /home/kim/Projects/mir/mir/bin/python score_and_report.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import compute_same_chroma, fold_to_12  # noqa: E402

sys.path.insert(0, "/home/kim/Projects/SAO/eval/musicology/gm_timbre_pitch")
from pipeline import GM_NAMES, family_name  # noqa: E402

import mido  # noqa: E402

HERE = Path(__file__).parent
GM_DIR = Path("/home/kim/Projects/SAO/eval/musicology/gm_timbre_pitch")
TM_DIR = Path("/home/kim/Projects/SAO/eval/musicology/test_midis_v2")
PRED_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/same_chroma_readout/predicted")

BAND_NAMES = ["bass", "mid", "air"]
FPS = 10.7666015625
HEAD_CKPT = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt"

TM_TIMBRES = ["sawlead", "squarelead", "piano", "strings", "churchorgan", "epiano",
              "synthbass", "synthbrass", "flute", "vibraphone"]


# ── helpers reused verbatim from eval/chroma384_eval.py's cos12 formula ─────

def cos12_timeavg(a12, b12):
    """a12/b12: (3,12,T). Time-averages each to (3,12) then returns (3,) cosine per band
    (verbatim formula from eval/chroma384_eval.py's cos12, generalized to 3-D input)."""
    a = a12.mean(-1) if a12.ndim == 3 else a12
    b = b12.mean(-1) if b12.ndim == 3 else b12
    num = (a * b).sum(-1)
    den = np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1) + 1e-9
    return num / den


def cos12_perframe_mean(a12, b12):
    """a12/b12: (3,12,T). Returns (3,) mean-over-frames cosine per band."""
    num = (a12 * b12).sum(1)
    den = np.linalg.norm(a12, axis=1) * np.linalg.norm(b12, axis=1) + 1e-9
    c = num / den
    return np.nanmean(c, axis=-1)


def cos12_vec(a, b):
    """a,b: (12,) or (N,12) vs (N,12). Plain cosine, no time axis."""
    num = (a * b).sum(-1)
    den = np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1) + 1e-9
    return num / den


# ── MIDI note extraction (mido) ─────────────────────────────────────────────

_MIDI_CACHE = {}


def notes_from_midi(path):
    path = str(path)
    if path in _MIDI_CACHE:
        return _MIDI_CACHE[path]
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat
    events = []
    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            events.append((tick, msg))
    events.sort(key=lambda e: e[0])
    notes = []
    active = {}
    cur_tick, cur_time, cur_tempo = 0, 0.0, 500000
    for tick, msg in events:
        cur_time += mido.tick2second(tick - cur_tick, tpb, cur_tempo)
        cur_tick = tick
        if msg.type == "set_tempo":
            cur_tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            active.setdefault(msg.note, []).append(cur_time)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            starts = active.get(msg.note)
            if starts:
                notes.append((starts.pop(0), cur_time, msg.note))
    notes.sort(key=lambda n: n[0])
    _MIDI_CACHE[path] = notes
    return notes


def band_of_pitch(pitch):
    return 0 if pitch < 60 else (2 if pitch >= 84 else 1)  # bass / mid / air (C4/C6 split)


def midi_pc_grid(notes, n_frames, fps=FPS):
    """Per-frame binary pitch-class-active grid, overall (12,T) and per-band (3,12,T)."""
    pc = np.zeros((12, n_frames), dtype=np.float32)
    band_pc = np.zeros((3, 12, n_frames), dtype=np.float32)
    for start, end, pitch in notes:
        f0 = max(int(np.floor(start * fps)), 0)
        f1 = min(int(np.ceil(end * fps)), n_frames)
        if f1 <= f0:
            continue
        pci = pitch % 12
        band = band_of_pitch(pitch)
        pc[pci, f0:f1] = 1.0
        band_pc[band, pci, f0:f1] = 1.0
    return pc, band_pc


# ── I/O ──────────────────────────────────────────────────────────────────────

def load_pred(set_name, stem):
    p = PRED_DIR / set_name / f"{stem}.npy"
    if not p.exists():
        return None
    return np.load(p)  # (3,128,T) float32


def gt_chroma_from_wav(path):
    y, sr = sf.read(str(path), always_2d=True)
    return compute_same_chroma(y, sr)  # (3,128,T) float32


def align(a, b):
    T = min(a.shape[-1], b.shape[-1])
    return a[..., :T], b[..., :T], T


# ── pair enumeration ─────────────────────────────────────────────────────────

def gm_pairs():
    """gm_timbre_pitch: pattern in {sweep,pat1,pat2,pat5} x program 0..119.
    MIDI is shared per pattern (only program_change differs -> notes identical)."""
    lat_dir = GM_DIR / "latents"
    ren_dir = GM_DIR / "renders"
    midi_dir = GM_DIR / "midis"
    out = []
    for p in sorted(lat_dir.glob("*.z0.npy")):
        stem = p.stem[:-3]  # strip ".z0"
        pattern, prog_s = stem.split("__p")
        program = int(prog_s)
        out.append({
            "set": "gm_timbre_pitch", "stem": stem, "pattern": pattern,
            "program": program, "program_name": GM_NAMES[program],
            "family": family_name(program),
            "wav": ren_dir / f"{stem}.wav", "midi": midi_dir / f"{pattern}.mid",
        })
    return out


def tm_pairs():
    """test_midis_v2: {midi_stem}__{timbre}. MIDI = <midi_stem>.mid in the set root."""
    lat_dir = TM_DIR / "latents"
    ren_dir = TM_DIR / "renders"
    out = []
    for p in sorted(lat_dir.glob("*.z0.npy")):
        stem = p.stem[:-3]
        midi_stem, timbre = stem.rsplit("__", 1)
        out.append({
            "set": "test_midis_v2", "stem": stem, "pattern": midi_stem,
            "timbre": timbre,
            "wav": ren_dir / f"{stem}.wav", "midi": TM_DIR / f"{midi_stem}.mid",
        })
    return out


# ── metric 1: readout fidelity (head vs audio-GT) ───────────────────────────

def metric1_readout(pairs):
    rows = []
    missing = []
    for pr in pairs:
        pred = load_pred(pr["set"], pr["stem"])
        if pred is None or not pr["wav"].exists():
            missing.append(pr["stem"])
            continue
        gt = gt_chroma_from_wav(pr["wav"])
        pred_a, gt_a, T = align(pred, gt)
        pred12, gt12 = fold_to_12(pred_a), fold_to_12(gt_a)
        ta = cos12_timeavg(pred12, gt12)
        pf = cos12_perframe_mean(pred12, gt12)
        row = dict(pr)
        row.pop("wav"), row.pop("midi")
        for i, b in enumerate(BAND_NAMES):
            row[f"timeavg_{b}"] = float(ta[i])
            row[f"perframe_{b}"] = float(pf[i])
        rows.append(row)
    return rows, missing


def summarize_readout(rows, group_key=None):
    if not rows:
        return {}
    out = {}
    for metric in ("timeavg", "perframe"):
        for b in BAND_NAMES:
            vals = np.array([r[f"{metric}_{b}"] for r in rows])
            out[f"{metric}_{b}_mean"] = float(np.nanmean(vals))
            out[f"{metric}_{b}_median"] = float(np.nanmedian(vals))
            out[f"{metric}_{b}_std"] = float(np.nanstd(vals))
    out["n"] = len(rows)
    if group_key:
        groups = {}
        for r in rows:
            groups.setdefault(r[group_key], []).append(r)
        out["by_" + group_key] = {
            k: summarize_readout(v) for k, v in groups.items()
        }
    return out


# ── metric 2: timbre-invariance (gm_timbre_pitch, fixed pattern across 120 programs) ──

def metric2_timbre_invariance(gm_rows_full, gm_pairs_list):
    """gm_rows_full: dict stem -> pred12 time-avg (3,12) vector (computed fresh here,
    since metric1 didn't keep the full folded array)."""
    by_pattern = {}
    for pr in gm_pairs_list:
        by_pattern.setdefault(pr["pattern"], []).append(pr)

    out = {}
    for pattern, prs in by_pattern.items():
        vecs = []  # (N,3,12)
        progs = []
        for pr in prs:
            pred = load_pred(pr["set"], pr["stem"])
            if pred is None:
                continue
            pred12 = fold_to_12(pred)  # (3,12,T)
            vecs.append(pred12.mean(-1))  # (3,12) time-avg
            progs.append(pr["program"])
        if len(vecs) < 3:
            continue
        vecs = np.stack(vecs, 0)  # (N,3,12)
        band_out = {}
        for bi, b in enumerate(BAND_NAMES):
            v = vecs[:, bi, :]  # (N,12)
            norm = np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9
            u = v / norm
            sim = u @ u.T
            iu = np.triu_indices(len(v), k=1)
            mean_pairwise = float(np.nanmean(sim[iu]))
            per_prog_mean_sim = (sim.sum(1) - 1.0) / (len(v) - 1)  # exclude self
            worst_idx = np.argsort(per_prog_mean_sim)[:10]
            worst = [{"program": progs[i], "name": GM_NAMES[progs[i]],
                      "family": family_name(progs[i]),
                      "mean_sim_to_others": float(per_prog_mean_sim[i])}
                     for i in worst_idx]
            band_out[b] = {"mean_pairwise_cos": mean_pairwise, "n_programs": len(v),
                            "worst10": worst}
        out[pattern] = band_out
    return out


# ── metric 3: pitch/note fidelity (head vs MIDI-derived GT) ─────────────────

def metric3_midi_fidelity(pairs):
    rows = []
    for pr in pairs:
        pred = load_pred(pr["set"], pr["stem"])
        if pred is None or not pr["midi"].exists():
            continue
        notes = notes_from_midi(pr["midi"])
        T = pred.shape[-1]
        _, band_pc = midi_pc_grid(notes, T)  # (3,12,T)
        pred12 = fold_to_12(pred)  # (3,12,T)
        ta = cos12_timeavg(pred12, band_pc)
        pf = cos12_perframe_mean(pred12, band_pc)
        row = {"set": pr["set"], "stem": pr["stem"], "pattern": pr["pattern"]}
        # note whether this pattern ever visits a given band (else cos is degenerate)
        band_has_notes = [bool(band_pc[i].sum() > 0) for i in range(3)]
        for i, b in enumerate(BAND_NAMES):
            row[f"timeavg_{b}"] = float(ta[i]) if band_has_notes[i] else None
            row[f"perframe_{b}"] = float(pf[i]) if band_has_notes[i] else None
        rows.append(row)
    return rows


def summarize_midi_fidelity(rows):
    out = {}
    for metric in ("timeavg", "perframe"):
        for b in BAND_NAMES:
            vals = np.array([r[f"{metric}_{b}"] for r in rows if r[f"{metric}_{b}"] is not None])
            if len(vals) == 0:
                out[f"{metric}_{b}_mean"] = None
                out[f"{metric}_{b}_n"] = 0
                continue
            out[f"{metric}_{b}_mean"] = float(np.nanmean(vals))
            out[f"{metric}_{b}_n"] = int(len(vals))
    out["n_pairs"] = len(rows)
    return out


# ── metric 4: transposition / register (chromatic sweeps) ──────────────────

def metric4_transposition(sweep_pairs, fps=FPS):
    per_pair = []
    for pr in sweep_pairs:
        pred = load_pred(pr["set"], pr["stem"])
        if pred is None or not pr["midi"].exists():
            continue
        notes = notes_from_midi(pr["midi"])
        if not notes:
            continue
        T = pred.shape[-1]
        pred12 = fold_to_12(pred)  # (3,12,T)
        pc_overall = pred12.sum(0)  # (12,T) summed over bands

        correct_overall = 0
        correct_bandmatched = 0
        n_notes = 0
        argmax_seq = []
        true_pc_seq = []
        for start, end, pitch in notes:
            f0 = max(int(np.floor(start * fps)), 0)
            f1 = min(int(np.ceil(end * fps)), T)
            if f1 <= f0:
                continue
            true_pc = pitch % 12
            band = band_of_pitch(pitch)
            seg_overall = pc_overall[:, f0:f1].mean(-1)
            seg_band = pred12[band, :, f0:f1].mean(-1)
            am_overall = int(np.argmax(seg_overall))
            am_band = int(np.argmax(seg_band))
            correct_overall += int(am_overall == true_pc)
            correct_bandmatched += int(am_band == true_pc)
            n_notes += 1
            argmax_seq.append(am_band)
            true_pc_seq.append(true_pc)

        if n_notes == 0:
            continue
        # frame-to-frame circular shift agreement: does the register-matched
        # argmax advance by the same direction/step as the true chromatic run?
        shift_agree = 0
        shift_total = 0
        for i in range(1, len(argmax_seq)):
            true_step = (true_pc_seq[i] - true_pc_seq[i - 1]) % 12
            pred_step = (argmax_seq[i] - argmax_seq[i - 1]) % 12
            shift_total += 1
            shift_agree += int(true_step == pred_step)

        per_pair.append({
            "set": pr["set"], "stem": pr["stem"],
            "timbre": pr.get("timbre", pr.get("program_name")),
            "n_notes": n_notes,
            "argmax_acc_overall": correct_overall / n_notes,
            "argmax_acc_bandmatched": correct_bandmatched / n_notes,
            "shift_step_agreement": (shift_agree / shift_total) if shift_total else None,
        })
    return per_pair


def summarize_transposition(rows):
    if not rows:
        return {}
    return {
        "n_pairs": len(rows),
        "mean_argmax_acc_overall": float(np.mean([r["argmax_acc_overall"] for r in rows])),
        "mean_argmax_acc_bandmatched": float(np.mean([r["argmax_acc_bandmatched"] for r in rows])),
        "mean_shift_step_agreement": float(np.mean(
            [r["shift_step_agreement"] for r in rows if r["shift_step_agreement"] is not None])),
        "worst5_bandmatched": sorted(rows, key=lambda r: r["argmax_acc_bandmatched"])[:5],
    }


# ── bonus: register probe (E2/E3/E4 transposition of pat1/pat2) ────────────

def bonus_register_probe():
    # register-probe stems carry the same "_bpm161p5_32bars" suffix as the
    # frame-locked primary set (see test_midis_v2/manifest.json 'files').
    suffix = "_bpm161p5_32bars"
    triples = [("pat1_const16_1pitch" + suffix, "pat13_pat1_e2" + suffix, "pat14_pat1_e4" + suffix),
               ("pat2_const16_2pitch" + suffix, "pat15_pat2_e2" + suffix, "pat16_pat2_e4" + suffix)]
    out = []
    for base, e2, e4 in triples:
        for timbre in TM_TIMBRES[:3]:  # keep it light: 3 representative timbres
            row = {"base": base, "timbre": timbre}
            for tag, stem in (("E3", base), ("E2", e2), ("E4", e4)):
                lat_stem = f"{stem}__{timbre}"
                pred = load_pred("test_midis_v2", lat_stem)
                if pred is None:
                    row[tag] = None
                    continue
                pred12 = fold_to_12(pred)  # (3,12,T)
                band_energy = np.linalg.norm(pred12, axis=1).mean(-1)  # (3,) energy per band
                dominant_band = BAND_NAMES[int(np.argmax(band_energy))]
                # pitch-class 'E' = index 4
                pc_e_strength = pred12[:, 4, :].mean(-1)  # (3,)
                row[tag] = {"dominant_band": dominant_band,
                            "band_energy": [round(float(x), 3) for x in band_energy],
                            "pc_E_per_band": [round(float(x), 3) for x in pc_e_strength]}
            out.append(row)
    return out


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    gm = gm_pairs()
    tm = tm_pairs()
    print(f"[pairs] gm_timbre_pitch={len(gm)} test_midis_v2={len(tm)}", flush=True)

    all_pairs = gm + tm

    print("[metric1] readout fidelity (head vs audio-GT)...", flush=True)
    m1_rows, missing = metric1_readout(all_pairs)
    print(f"  scored {len(m1_rows)}, missing/failed {len(missing)}", flush=True)

    m1_pooled = summarize_readout(m1_rows)
    m1_by_set = {}
    for s in ("gm_timbre_pitch", "test_midis_v2"):
        rows_s = [r for r in m1_rows if r["set"] == s]
        m1_by_set[s] = summarize_readout(rows_s, group_key="pattern")

    # per-program breakdown (gm only) -- worst/best 10 pooled over patterns
    gm_rows = [r for r in m1_rows if r["set"] == "gm_timbre_pitch"]
    by_prog = {}
    for r in gm_rows:
        by_prog.setdefault(r["program"], []).append(r)
    prog_summary = []
    for prog, rs in by_prog.items():
        mid_vals = [r["timeavg_mid"] for r in rs]
        prog_summary.append({"program": prog, "name": GM_NAMES[prog], "family": family_name(prog),
                              "mean_timeavg_mid": float(np.mean(mid_vals)),
                              "mean_timeavg_bass": float(np.mean([r["timeavg_bass"] for r in rs])),
                              "mean_timeavg_air": float(np.mean([r["timeavg_air"] for r in rs]))})
    prog_summary.sort(key=lambda r: r["mean_timeavg_mid"])
    worst10_programs = prog_summary[:10]
    best10_programs = prog_summary[-10:][::-1]

    print("[metric2] timbre invariance (gm_timbre_pitch, fixed pattern x 120 programs)...", flush=True)
    m2 = metric2_timbre_invariance(None, gm)

    print("[metric3] pitch/note fidelity (head vs MIDI-derived GT)...", flush=True)
    m3_rows = metric3_midi_fidelity(all_pairs)
    m3_pooled = summarize_midi_fidelity(m3_rows)
    m3_by_set = {s: summarize_midi_fidelity([r for r in m3_rows if r["set"] == s])
                 for s in ("gm_timbre_pitch", "test_midis_v2")}

    print("[metric4] transposition / register (chromatic sweeps)...", flush=True)
    tm_sweeps = [p for p in tm if p["pattern"].startswith("sweep_chromatic")]
    gm_sweeps = [p for p in gm if p["pattern"] == "sweep"]
    m4_tm_rows = metric4_transposition(tm_sweeps)
    m4_gm_rows = metric4_transposition(gm_sweeps)
    m4_tm = summarize_transposition(m4_tm_rows)
    m4_gm = summarize_transposition(m4_gm_rows)

    print("[bonus] register probe (E2/E3/E4 band localization)...", flush=True)
    bonus_reg = bonus_register_probe()

    results = {
        "provenance": {
            "head_ckpt": HEAD_CKPT,
            "pair_sets": {
                "gm_timbre_pitch": str(GM_DIR),
                "test_midis_v2": str(TM_DIR),
            },
            "frame_rate_fps": FPS,
            "n_pairs_gm": len(gm), "n_pairs_tm": len(tm),
            "missing_pairs": missing,
        },
        "metric1_readout_fidelity": {
            "pooled": m1_pooled,
            "by_set": m1_by_set,
            "worst10_programs_by_timeavg_mid": worst10_programs,
            "best10_programs_by_timeavg_mid": best10_programs,
        },
        "metric2_timbre_invariance": m2,
        "metric3_midi_note_fidelity": {
            "pooled": m3_pooled,
            "by_set": m3_by_set,
        },
        "metric4_transposition": {
            "test_midis_v2_sweeps": {"summary": m4_tm, "per_pair": m4_tm_rows},
            "gm_timbre_pitch_sweep_bonus": {"summary": m4_gm, "n_programs": len(m4_gm_rows)},
        },
        "bonus_register_probe": bonus_reg,
    }

    out_path = HERE / "results.json"
    out_path.write_text(json.dumps(results, indent=1, default=str))
    print(f"[score_and_report] wrote {out_path} ({time.time()-t0:.1f}s total)", flush=True)


if __name__ == "__main__":
    main()
