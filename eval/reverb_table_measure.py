#!/usr/bin/env python3
"""reverb_table_measure.py — CPU batch reverb/stereo measurement over the SA3 DoRA
model-matrix + a real-music (goa) reference, for the "why do DoRA fine-tunes sound
like they add reverb / bathroom" study.

Per clip it computes THREE metric families and streams one JSON object per clip to a
JSONL file (resumable):

  1. stereo — EVERY metric from eval/stereo_phase_meter.py (imported + reused, not
     reimplemented): band-resolved L/R magnitude-squared coherence, mid/side energy
     ratio over time, stereo width/corr, vector-sum deficit, cepstral comb detector.
  2. Audio Commons reverb via timbral_models.timbral_reverb(path, dev_output=True) —
     BOTH continuous outputs kept: rt60_s and reverb_prob (our mir wrapper discards
     rt60; here we capture it).
  3. mono — mono-downmix reverb signature the L/R meter can't see (an in-channel
     smear): spectral flatness over time (mean + p90), a decay/late-energy proxy
     (log-energy-envelope decay slope + late/early energy ratio + envelope crest
     factor), and a low/high spectral-energy tilt (dB). All continuous.

Manifest (--manifest): a JSONL file with one JSON object per line, OR a plain file
list (one path per line). JSONL records must carry a "path"; they may also carry
metadata (label/ckpt/cfg/... for matrix clips) which is copied through verbatim, and
optional {crop_start_s, crop_dur_s} — when a crop is present the clip is loaded,
cropped, resampled to 44.1 kHz (the meter's calibrated rate) and materialised to a
temp wav so the meter HONORS the crop. Length-matches the 20 s generations.

Resumable: records whose "path" already appears in --out are skipped. Robust: each
clip runs in a worker under try/except so one bad file cannot abort the batch;
failures are recorded (ok=False, error, traceback) and logged to stderr.

Run (mir venv REQUIRED — stereo_phase_meter pulls mir's ExpandedExtractor):
  /home/kim/Projects/mir/mir/bin/python eval/reverb_table_measure.py \
      --manifest eval/matrix_clips.jsonl --out eval/reverb_matrix.jsonl [--limit N] [--workers 10]
"""
import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from math import gcd

# ---- hard import guard (mir venv required) ---------------------------------------
try:
    sys.path.insert(0, "/home/kim/Projects/mir/src")
    sys.path.insert(0, "/home/kim/Projects/SAO/eval")
    sys.path.insert(0, "/home/kim/Projects/SAO/latch")
    import numpy as np
    import soundfile as sf
    from scipy.signal import stft as _stft, resample_poly
    from core.file_utils import read_audio          # mir
    import stereo_phase_meter as spm                 # eval/ — metric family (1), reused
    import timbral_models                            # Audio Commons — metric family (2)
except Exception as e:  # noqa: BLE001
    sys.stderr.write(
        "FATAL: reverb_table_measure.py could not import a required dependency.\n"
        f"  underlying error: {type(e).__name__}: {e}\n"
        "  This script MUST run under the mir venv:\n"
        "    /home/kim/Projects/mir/mir/bin/python "
        "/home/kim/Projects/SAO/eval/reverb_table_measure.py --manifest M.jsonl --out O.jsonl\n"
    )
    sys.exit(2)

FS = 44100
EPS = 1e-12
NPERSEG = 2048
NOVERLAP = 1536


# ---- metric family (3): mono-domain reverb signature ----------------------------
def _mono_reverb_metrics(mono, sr):
    """In-channel smear metrics on the mono downmix. All continuous.

    (a) spectral flatness over time  -> mean + p90 (reverb/noise -> flatter)
    (b) decay / late-energy proxy    -> log-energy-envelope decay slope,
                                        late/early energy ratio, envelope crest factor
                                        (reverb fills the quiet gaps -> lower crest)
    (c) low/high spectral tilt (dB)  -> 20*log10( mean|X| @4-16k / mean|X| @20-500 )
    """
    f, _t, Z = _stft(mono, fs=sr, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    mag = np.abs(Z)                      # (freq, time)
    power = mag ** 2 + EPS

    # (a) spectral flatness per frame = geo-mean / arith-mean over frequency
    geo = np.exp(np.mean(np.log(power), axis=0))
    arith = np.mean(power, axis=0)
    flat = geo / (arith + EPS)
    sf_mean = float(np.mean(flat))
    sf_p90 = float(np.percentile(flat, 90))

    # (b) broadband energy envelope per STFT frame
    frame_energy = power.sum(axis=0)
    le = np.log(frame_energy + EPS)
    if len(le) > 2:
        x = np.arange(len(le), dtype=np.float64)
        decay_slope = float(np.polyfit(x, le, 1)[0])   # log-energy per frame
    else:
        decay_slope = float("nan")
    q = max(1, len(frame_energy) // 4)
    late_early_ratio = float(frame_energy[-q:].mean() / (frame_energy[:q].mean() + EPS))
    env_crest = float(np.percentile(frame_energy, 95) / (np.median(frame_energy) + EPS))

    # (c) spectral tilt: high-band vs low-band mean magnitude, in dB
    lo_mask = (f >= 20) & (f < 500)
    hi_mask = (f >= 4000) & (f < 16000)
    lo_e = float(mag[lo_mask].mean()) if lo_mask.any() else EPS
    hi_e = float(mag[hi_mask].mean()) if hi_mask.any() else EPS
    tilt_hi_lo_db = float(20.0 * np.log10((hi_e + EPS) / (lo_e + EPS)))

    return {
        "spectral_flatness_mean": round(sf_mean, 8),
        "spectral_flatness_p90": round(sf_p90, 8),
        "env_decay_slope": round(decay_slope, 8),
        "late_early_energy_ratio": round(late_early_ratio, 6),
        "env_crest_factor": round(env_crest, 6),
        "spectral_tilt_hi_lo_db": round(tilt_hi_lo_db, 6),
        "n_frames": int(len(frame_energy)),
    }


def _materialise_crop(path, crop_start_s, crop_dur_s):
    """Load, crop, resample->44.1k, ensure stereo, write a temp wav; return its path."""
    raw, sr = read_audio(path)
    raw = np.asarray(raw)
    if raw.ndim == 1:
        raw = np.stack([raw, raw], axis=-1)
    dur = crop_dur_s if crop_dur_s else 20.0
    s0 = int(round(crop_start_s * sr))
    n = int(round(dur * sr))
    s0 = max(0, min(s0, max(0, raw.shape[0] - n)))
    seg = raw[s0:s0 + n]
    if sr != FS:
        g = gcd(int(sr), FS)
        seg = resample_poly(seg, FS // g, int(sr) // g, axis=0)
    seg = np.clip(seg, -1.0, 1.0).astype(np.float32)
    tmpdir = "/dev/shm" if os.path.isdir("/dev/shm") else None
    fd, tmp = tempfile.mkstemp(suffix=".wav", dir=tmpdir)
    os.close(fd)
    sf.write(tmp, seg, FS, subtype="FLOAT")
    return tmp


def process(rec):
    """Per-clip worker. Never raises: errors are captured into the returned dict."""
    out = dict(rec)                       # carry manifest metadata through verbatim
    t0 = time.time()
    tmp = None
    path = rec.get("path")
    try:
        if path is None:
            raise ValueError("record has no 'path'")
        crop_start = rec.get("crop_start_s")
        if crop_start is not None:
            tmp = _materialise_crop(path, float(crop_start), rec.get("crop_dur_s"))
            analysis_path = tmp
        else:
            analysis_path = path

        # (1) stereo — reuse eval/stereo_phase_meter.analyze wholesale
        out["stereo"] = spm.analyze(analysis_path)

        # (2) Audio Commons reverb — keep BOTH rt60 and probability, continuous
        try:
            rt60, prob = timbral_models.timbral_reverb(analysis_path, dev_output=True)
            out["rt60_s"] = float(rt60)
            out["reverb_prob"] = float(prob)
        except Exception as e:  # noqa: BLE001
            out["rt60_s"] = None
            out["reverb_prob"] = None
            out["reverb_error"] = f"{type(e).__name__}: {e}"

        # (3) mono-domain smear metrics
        raw2, sr2 = read_audio(analysis_path)
        raw2 = np.asarray(raw2)
        mono = raw2.mean(axis=-1) if raw2.ndim > 1 else raw2
        out["mono"] = _mono_reverb_metrics(mono.astype(np.float64), sr2)

        out["ok"] = True
    except Exception as e:  # noqa: BLE001 — one bad clip must not kill the run
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    out["elapsed_s"] = round(time.time() - t0, 3)
    return out


def _load_manifest(path):
    """JSONL records (dicts with 'path') OR a plain one-path-per-line file list."""
    recs = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                recs.append({"path": line})
                continue
            if isinstance(obj, dict):
                recs.append(obj)
            elif isinstance(obj, str):
                recs.append({"path": obj})
    return recs


def _done_paths(out_path):
    done = set()
    if not os.path.exists(out_path):
        return done
    with open(out_path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = obj.get("path")
            if p is not None:
                done.add(p)
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True, help="JSONL records or plain file list")
    ap.add_argument("--out", required=True, help="output JSONL (appended, resumable)")
    ap.add_argument("--limit", type=int, default=None, help="process at most N new clips")
    ap.add_argument("--workers", type=int, default=10, help="Pool size (default 10)")
    args = ap.parse_args()

    recs = _load_manifest(args.manifest)
    done = _done_paths(args.out)
    todo = [r for r in recs if r.get("path") not in done]
    n_skip = len(recs) - len(todo)
    if args.limit is not None:
        todo = todo[:args.limit]

    print(f"[reverb] manifest={args.manifest} total={len(recs)} "
          f"already_done={n_skip} to_process={len(todo)} workers={args.workers}",
          file=sys.stderr)
    if not todo:
        print("[reverb] nothing to do", file=sys.stderr)
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)

    import multiprocessing as mp
    n_ok = n_err = 0
    t0 = time.time()
    # append mode; line-buffered so a killed run keeps everything already flushed
    with open(args.out, "a", buffering=1) as fh:
        if args.workers <= 1:
            it = (process(r) for r in todo)
        else:
            pool = mp.Pool(processes=args.workers, maxtasksperchild=40)
            it = pool.imap_unordered(process, todo)
        try:
            for i, res in enumerate(it, 1):
                fh.write(json.dumps(res, ensure_ascii=False) + "\n")
                if res.get("ok"):
                    n_ok += 1
                else:
                    n_err += 1
                    sys.stderr.write(f"[fail] {res.get('path')}: {res.get('error')}\n")
                if i % 50 == 0 or i == len(todo):
                    rate = i / (time.time() - t0 + EPS)
                    print(f"[reverb] {i}/{len(todo)} ok={n_ok} err={n_err} "
                          f"{rate:.2f} clip/s", file=sys.stderr)
        finally:
            if args.workers > 1:
                pool.close()
                pool.join()

    dt = time.time() - t0
    print(f"[reverb] done: {n_ok} ok, {n_err} err in {dt:.1f}s "
          f"({dt / max(1, n_ok + n_err):.2f}s/clip wall) -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
