#!/usr/bin/env python
"""mixtape_assemble_v7.py — DJ mix v7, Phase 0: ONE integer-sample placement timeline, constant tempo
inside every crossfade window, windows in bars, one constant phase shift per transition.

WHY (GHOST-NOTE, 2026-10-07; spec docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md, section 2).
v6 concatenated per-pair composites, so every one of its 39 splices REPLAYED the incoming clip from its
entry point (eval/mixtape_audit_continuity.py found it). Here no pair render exists: each clip is placed once
on a single timeline and overlap-added, so a clip's body continues from the exact sample where its crossfade
left it, by construction.

RULES IMPLEMENTED (spec R0.1-R0.4):
  R0.1  placement list in integer samples; positions never taken from a pair run_meta; an assert per splice.
  R0.2  tempo: ONLY the outgoing clip is stretched (bungee, in the mir venv, never sox), in its body BEFORE
        the window, slew <= 0.5 BPM per bar, held constant through the window; the incoming clip is never
        stretched inside its entry window. |BPM gap| > --max-gap is refused (re-sort / drop instead).
        After a stretch every downbeat grid is re-detected (madmom, mir venv) on the stretched audio.
  R0.3  B's entry downbeat lands on an A downbeat; the residual is ONE constant shift, estimated by
        cross-correlating the 40-150 Hz band over the whole window, search +-1/4 beat, mild penalty on
        large shifts. Residual, shift and the tempo schedule are written to run_meta.
  R0.4  window length = bars: min(--bars, (usable_bars - 4) // 2) per transition.
The mix is peak-normalised ONCE at the end (never per transition).

USAGE (CPU only; run from the eval dir, not the SAO root, torchcodec shadow):
  cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python mixtape_assemble_v7.py \\
      --order .../work48b/order_final.json --bounds .../work48b/bounds.json --pairs .../work48b/pairs.json \\
      --out-dir /run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0 [--drop-first] [--bars 12]
"""
import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfiltfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dj_beatmatch import madmom_downbeats  # noqa: E402
from chroma_morph_transitions import MIR_VENV_PY  # noqa: E402

SR = 44100
MAX_SLEW_BPM_PER_BAR = 0.5
BAND = (40.0, 150.0)


def bar_sec(bpm):
    return 240.0 / bpm


def bungee_tail(audio, times, speeds):
    """Piecewise-linear speed schedule over OUTPUT time (same loop as dj_beatmatch._bungee_stretch_schedule,
    but also returns the per-chunk output lengths so source->output positions can be mapped exactly).
    audio (C, N) -> (C, M), lens (K,) output samples produced per 0.25 s source chunk."""
    with tempfile.TemporaryDirectory() as td:
        src, dst, dl = f"{td}/in.npy", f"{td}/out.npy", f"{td}/len.npy"
        np.save(src, audio.T)
        code = f"""
import numpy as np
from bungee_python import bungee as B
d = np.load({src!r}).astype(np.float32)
sr = {SR}
st = B.Bungee(sample_rate=sr, channels=d.shape[1])
times = np.array({[float(t) for t in times]!r}, dtype=np.float64)
speeds = np.array({[float(s) for s in speeds]!r}, dtype=np.float64)
chunk = int(0.25 * sr)
outs, lens, out_sec = [], [], 0.0
for lo in range(0, d.shape[0], chunk):
    sp = float(np.interp(out_sec, times, speeds))
    st.set_speed(sp)
    y = np.asarray(st.process(d[lo:lo + chunk]), dtype=np.float32)
    if y.ndim == 1:
        y = y.reshape(-1, d.shape[1])
    outs.append(y); lens.append(y.shape[0])
    out_sec += y.shape[0] / sr
np.save({dst!r}, np.concatenate(outs, axis=0)); np.save({dl!r}, np.array(lens))
"""
        subprocess.run([MIR_VENV_PY, "-c", code], check=True, capture_output=True)
        return np.load(dst).T, np.load(dl)


def src_to_out(src_sample, lens):
    """map a sample offset inside the stretched source tail to its output sample (linear inside a chunk)."""
    chunk = int(0.25 * SR)
    k, r = divmod(int(src_sample), chunk)
    k = min(k, len(lens) - 1)
    return int(lens[:k].sum() + round(lens[k] * r / chunk))


def lowband(x):
    return sosfiltfilt(butter(4, BAND, "bandpass", fs=SR, output="sos"), x.mean(0))


def kick_env(x):
    """40-150 Hz band -> Hilbert envelope -> low-passed at 40 Hz -> zero-mean: the kick pulses, not the bass notes.
    (The waveform null test decorrelates when the two clips have different basslines; the pulse train does not.)"""
    from scipy.signal import hilbert
    b = lowband(x)
    e = np.abs(hilbert(b))
    e = sosfiltfilt(butter(2, 40, "low", fs=SR, output="sos"), e)
    return e - e.mean()


def phase_shift(a_seg, b_seg, beat_samples, penalty=0.05):
    """B delayed by s samples (s>0) maximises the normalised correlation of the kick envelopes over +-1/4 beat,
    with a mild penalty on large shifts. Returns (shift, ncc_best, ncc_zero)."""
    a, b = kick_env(a_seg), kick_env(b_seg)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    m = int(round(beat_samples / 4))
    c = fftconvolve(a, b[::-1], mode="full")          # c[n-1+s] = sum_j a[j] b[j-s]: b delayed by s lines up with a
    best, best_score, ncc = 0, -np.inf, {}
    for s in range(-m, m + 1):
        ov = n - abs(s)
        lo_a, lo_b = max(0, s), max(0, -s)
        na = np.sqrt((a[lo_a:lo_a + ov] ** 2).sum()) * np.sqrt((b[lo_b:lo_b + ov] ** 2).sum())
        v = float(c[n - 1 + s] / max(na, 1e-12))
        ncc[s] = v
        score = v - penalty * abs(s) / m
        if score > best_score:
            best, best_score = s, score
    return best, ncc[best], ncc[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--bounds", required=True)
    ap.add_argument("--pairs", required=True, help="v6 pairs.json, used ONLY for the per-clip BPM (a_bpm/b_bpm)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--bars", type=int, default=12)
    ap.add_argument("--drop-first", action="store_true", help="drop the lone 120 BPM head clip")
    ap.add_argument("--max-gap", type=float, default=5.0)
    ap.add_argument("--min-bars", type=int, default=16,
                    help="drop clips with fewer usable bars (a ~20 s canonical clip is 11 bars: its window would be 3)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N clips (smoke test)")
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    order = json.loads(Path(a.order).read_text())
    bounds = json.loads(Path(a.bounds).read_text())
    pairs = json.loads(Path(a.pairs).read_text())
    bpm_of = {Path(p["a_path"]).stem: p["a_bpm"] for p in pairs}
    bpm_of[Path(pairs[-1]["b_path"]).stem] = pairs[-1]["b_bpm"]
    dropped = []
    if a.drop_first:
        dropped.append(order[0]["id"])
        order = order[1:]
    if a.limit:
        order = order[:a.limit]
    n = len(order)
    clips = [{"id": o["id"], "path": o["path"], "bpm": float(bpm_of[Path(o["path"]).stem])} for o in order]
    print(f"[v7] {n} clips, bpm {min(c['bpm'] for c in clips):.1f}-{max(c['bpm'] for c in clips):.1f}", flush=True)

    # ---- native audio + downbeats (cached) --------------------------------------------------------
    dbc_path = out / "downbeats_native.json"
    dbc = json.loads(dbc_path.read_text()) if dbc_path.exists() else {}
    for c in clips:
        x, sr = sf.read(c["path"], dtype="float32")
        assert sr == SR, c["path"]
        c["x"] = x.T.copy()
        if c["id"] not in dbc:
            dbc[c["id"]] = [float(t) for t in madmom_downbeats(c["x"], SR)]
            dbc_path.write_text(json.dumps(dbc))
        c["db"] = np.array(dbc[c["id"]])
        key = c["id"]
        bk = bounds.get(key) or bounds[next(k for k in bounds if key.startswith(k) or k.startswith(key[:60]))]
        c["in_s"] = float(c["db"][np.argmin(abs(c["db"] - bk["start"]))])
        c["out_s"] = float(c["db"][np.argmin(abs(c["db"] - bk["end_pre_zc"]))])
        c["in_i"] = int(np.argmin(abs(c["db"] - c["in_s"])))
        c["out_i"] = int(np.argmin(abs(c["db"] - c["out_s"])))
        c["usable_bars"] = c["out_i"] - c["in_i"]
        print(f"  {c['id'][:48]:48s} bpm {c['bpm']:.2f} bars {c['usable_bars']}", flush=True)

    short_dropped = [c["id"] for c in clips if c["usable_bars"] < a.min_bars]
    if short_dropped:
        print(f"[v7] dropping {len(short_dropped)} clips with < {a.min_bars} usable bars", flush=True)
    dropped += short_dropped
    clips = [c for c in clips if c["usable_bars"] >= a.min_bars]
    n = len(clips)

    # ---- per-transition geometry -----------------------------------------------------------------
    trans = []
    for i in range(n - 1):
        A, B = clips[i], clips[i + 1]
        gap = B["bpm"] - A["bpm"]
        if abs(gap) > a.max_gap:
            raise SystemExit(f"transition {i}: |BPM gap| {gap:.1f} > {a.max_gap}; re-sort or drop a clip")
        W = min(a.bars, (min(A["usable_bars"], B["usable_bars"]) - 4) // 2)
        assert W >= 2, f"transition {i}: window too short ({W} bars)"
        trans.append({"i": i, "gap": gap, "W": W})

    # ---- stretch the outgoing clip's body, re-detect grids on the stretched audio ------------------
    for i, c in enumerate(clips):
        c["Wprev"] = trans[i - 1]["W"] if i > 0 else 0
        c["Wnext"] = trans[i]["W"] if i < n - 1 else 0
        c["sched"] = None
        c["X"], c["Xdb"] = c["x"], c["db"]
        if i == n - 1:
            continue
        gap = trans[i]["gap"]
        if abs(gap) < 0.05:
            continue
        speed = clips[i + 1]["bpm"] / c["bpm"]
        win_i = c["out_i"] - c["Wnext"]                        # downbeat index where the exit window starts
        r0 = c["in_i"] + c["Wprev"] + 1                        # earliest ramp start (entry window + 1 bar margin)
        need = max(1, math.ceil(abs(gap) / MAX_SLEW_BPM_PER_BAR))
        ramp_end = win_i - 1                                   # ramp must finish 1 bar before the window
        ramp_start = max(r0, ramp_end - need)
        ramp_bars = ramp_end - ramp_start
        slew_ok = ramp_bars >= need
        if ramp_bars < 1:
            raise SystemExit(f"clip {i}: no room for a tempo ramp (r0 {r0}, window {win_i})")
        s0 = int(round(c["db"][ramp_start] * SR))
        tail_src = c["x"][:, s0:]
        out_dur = ramp_bars * bar_sec(c["bpm"]) / ((1 + speed) / 2)
        Y, lens = bungee_tail(tail_src, [0.0, out_dur], [1.0, speed])
        X = np.concatenate([c["x"][:, :s0], Y], axis=1)
        # analytic position of each native downbeat after s0
        mapped = np.array([s0 + src_to_out(int(round(t * SR)) - s0, lens) if t * SR >= s0 else int(round(t * SR))
                           for t in c["db"]]) / SR
        det = np.array(madmom_downbeats(X, SR))
        # trust the analytic map; refine to a detected downbeat only when it agrees within 30 ms (madmom on
        # stretched audio sometimes lands half a bar off, and snapping to that would misplace a window)
        near = np.array([det[np.argmin(abs(det - m))] if len(det) else m for m in mapped])
        snap = np.where(abs(near - mapped) < 0.03, near, mapped)
        err = (snap - mapped)[c["in_i"]:c["out_i"] + 1]
        c["X"], c["Xdb"] = X, snap
        c["sched"] = {"speed": speed, "ramp_start_bar": int(ramp_start), "ramp_bars": int(ramp_bars),
                      "slew_bpm_per_bar": abs(gap) / ramp_bars, "slew_ok": bool(slew_ok), "gap_bpm": gap,
                      "map_vs_detect_ms_max": float(1000 * np.abs(err).max()),
                      "map_vs_detect_ms_med": float(1000 * np.median(np.abs(err)))}
        print(f"  stretch clip {i}: gap {gap:+.2f} bpm, ramp {ramp_bars} bars (need {need}), map-vs-detect "
              f"max {c['sched']['map_vs_detect_ms_max']:.0f} ms", flush=True)

    # ---- placement list ---------------------------------------------------------------------------
    T = 0
    place = []
    for i, c in enumerate(clips):
        db = c["Xdb"]
        in_pos = int(round(db[c["in_i"]] * SR))
        if i < n - 1:
            W = c["Wnext"]
            p = int(round(db[c["out_i"] - W] * SR))             # exit window start (an A downbeat, stretched grid)
            L = int(round(W * bar_sec(clips[i + 1]["bpm"]) * SR))
            end_pos = p + L
        else:
            p = L = 0
            end_pos = int(round(db[c["out_i"]] * SR))
        place.append({"i": i, "id": c["id"], "T": T, "in_pos": in_pos, "p": p, "L": L, "end_pos": end_pos,
                      "shift": 0, "resid": None})
        if i < n - 1:
            B = clips[i + 1]
            b_in = int(round(B["Xdb"][B["in_i"]] * SR))
            a_seg = c["X"][:, p:p + L]
            b_seg = B["X"][:, b_in:b_in + L]
            beat = 60.0 / B["bpm"] * SR
            s, ncc_b, ncc_0 = phase_shift(a_seg, b_seg, beat)
            place[-1]["shift"] = int(s)
            place[-1]["resid"] = {"ncc_best": ncc_b, "ncc_zero": ncc_0, "improvement": ncc_b - ncc_0,
                                  "search_ms": 1000 * beat / 4 / SR}
            T = T + (p - in_pos) + int(s)
        # NOTE: s>0 delays B relative to A (B enters later), matching phase_shift's sign convention

    # ---- render by overlap-add (integers only) ------------------------------------------------------
    total = place[-1]["T"] + (place[-1]["end_pos"] - place[-1]["in_pos"])
    mix = np.zeros((2, total + SR), dtype=np.float32)
    for i, c in enumerate(clips):
        pl = place[i]
        seg = c["X"][:, pl["in_pos"]:pl["end_pos"]].astype(np.float32).copy()
        g = np.ones(seg.shape[1], dtype=np.float32)
        Lin = clips[i]["Wprev"] and place[i - 1]["L"]
        if i > 0 and Lin:
            g[:Lin] *= np.linspace(0, 1, Lin, endpoint=False, dtype=np.float32)
        if i < n - 1:
            off = pl["p"] - pl["in_pos"]
            g[off:off + pl["L"]] *= np.linspace(1, 0, pl["L"], endpoint=False, dtype=np.float32)
        mix[:, pl["T"]:pl["T"] + seg.shape[1]] += seg * g
        # R0.1 assert: this clip contributes source samples [in_pos, end_pos) at timeline [T, T+len): a constant
        # offset T - in_pos, so source position advances 1:1 with the timeline in the rendered time base.
        assert seg.shape[1] == pl["end_pos"] - pl["in_pos"]
        if i < n - 1:
            nxt = place[i + 1]
            assert nxt["T"] == pl["T"] + (pl["p"] - pl["in_pos"]) + pl["shift"], f"splice {i}: placement drift"
    mix = mix[:, :total]
    tail = min(total, 4 * SR)                               # the last clip has no exit window: 4 s fade-out
    mix[:, -tail:] *= np.linspace(1, 0, tail, dtype=np.float32)
    peak = float(np.abs(mix).max())
    mix *= 0.891 / max(peak, 1e-9)
    sf.write(out / "mixtape_full_plain.wav", mix.T, SR, subtype="PCM_16")

    # ---- timeline.json (format of build_dj_mixes_section::timeline) + run_meta + placement ------------
    clip_bounds, trans_t = [0.0], []
    for i in range(n - 1):
        pl = place[i]
        t0 = (pl["T"] + pl["p"] - pl["in_pos"]) / SR
        t1 = t0 + pl["L"] / SR
        trans_t.append([round(t0, 2), round(t1, 2)])
        clip_bounds.append(round((t0 + t1) / 2, 2))
    dur = total / SR
    clip_bounds.append(round(dur, 2))
    try:
        from build_dj_mixes_section import short
    except Exception:
        short = lambda s: s[:30]
    (out / "timeline.json").write_text(json.dumps({"dur": round(dur, 2), "clips": [short(c["id"]) for c in clips],
                                                  "clip_bounds": clip_bounds, "trans": trans_t}))
    (out / "order_used.json").write_text(json.dumps([{"id": c["id"], "path": c["path"]} for c in clips]))
    meta = {
        "purpose": "DJ mix v7 phase 0: one integer-sample placement timeline (no concatenated pair renders), constant "
                   "tempo inside every window, windows in bars, one constant phase shift per transition",
        "hypothesis": "removes the v6 replay at every splice (audit median -10 s) and the in-window tempo ramps; "
                      "kill criterion: any phase 0 gate number failing",
        "spec": "docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md",
        "script": "eval/mixtape_assemble_v7.py", "variant": "plain (a2a deferred: needs the GPU)",
        "bars_param": a.bars, "dropped": dropped, "n_clips": n, "dur_sec": dur, "peak_before_norm": peak,
        "transitions": [{"i": t["i"], "gap_bpm": t["gap"], "window_bars": t["W"],
                         "shift_samples": place[t["i"]]["shift"], "shift_ms": 1000 * place[t["i"]]["shift"] / SR,
                         "align": place[t["i"]]["resid"], "out_tempo_schedule": clips[t["i"]]["sched"]} for t in trans],
        "kim_feedback": None,
    }
    (out / "run_meta.json").write_text(json.dumps(meta, indent=1))
    sh = np.array([abs(p["shift"]) / SR * 1000 for p in place[:-1]])
    print(f"[v7] wrote {out}/mixtape_full_plain.wav  {dur / 60:.1f} min, {n} clips, {len(trans)} transitions; "
          f"shift ms med {np.median(sh):.0f} max {sh.max():.0f}", flush=True)


if __name__ == "__main__":
    main()
