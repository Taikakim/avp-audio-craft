#!/usr/bin/env python
"""hf_clarity_fulltracks.py — the codec-clarity ladder on LONG, BEAT-SYNCED clips
(Kim 2026-08-07: "beat-synced 2 min clips from the 60%-70% point where there probably is the
most hf action, and auto-loop should be ok too"; local-only, "I have 96GB of RAM").

Differences from hf_clarity_diagnosis.py (the 8 s excerpt version), all deliberate:
  * ~2 MINUTES, not 8 s — 8 s is too short to judge "air", which is what this test is about.
  * BEAT-SYNCED via mir's existing per-track `.DOWNBEATS` grid (4458/4461 tracks have one).
    Start AND end snap to downbeats, so the clip is a whole number of bars and the page's
    auto-loop is musically seamless rather than a click every repeat.
  * From the 60-70% point of the track — Kim's call: that's typically the busiest passage,
    so it stresses HF detail hardest.
  * STEREO, not mono-summed. The 8 s leg collapses to mono because its METRIC is mono; here
    the purpose is the ear, and stereo is where "air" actually lives.
LOCAL ONLY: ~40 MB of FLAC per variant per clip, 7 variants each — never rsynced to the public
page (which stays small per spec §4). The local server on :8792 serves it.

WHY CHUNKED SAME: the pretransform can't take 2 minutes of stereo in one pass on a 16 GB card.
Encode/decode runs in overlapping windows that are whole multiples of the 4096-sample latent
hop, with cross-faded seams, and the output keeps the input's exact length — that sample
alignment is what makes the page's Δ null-test a real null test.

Run (SA3 venv, GPU — hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/hf_clarity_fulltracks.py \
      [--tracks 3] [--seconds 120]
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import hilbert

sys.path.insert(0, str(Path(__file__).parent))
from hf_clarity_diagnosis import CORPUS, OUT, SR  # noqa: E402

from stable_audio_3 import StableAudioModel  # noqa: E402

HOP = 4096          # pretransform latent hop; chunk sizes must be whole multiples of it
CHUNK_S = 20        # audio per GPU pass
OVERLAP_S = 2       # cross-faded, discarded symmetrically


def lag_of(ref, y):
    """Codec delay in samples, by broadband-envelope xcorr (same method as the 8 s leg's
    align(), but returning the LAG so one shift can be applied to BOTH stereo channels —
    per-channel alignment would smear the stereo image)."""
    n = min(len(ref), len(y))
    er = np.abs(hilbert(ref[:n:16])).astype(np.float64)
    ey = np.abs(hilbert(y[:n:16])).astype(np.float64)
    er -= er.mean(); ey -= ey.mean()
    xc = np.correlate(er, ey, mode="full")
    return int(xc.argmax() - (len(ey) - 1)) * 16


def apply_lag(v, lag, n):
    """Shift a (2, N) stereo array by `lag` samples and trim/pad to n."""
    if lag > 0:
        v = np.concatenate([np.zeros((v.shape[0], lag), np.float32), v], 1)
    elif lag < 0:
        v = v[:, -lag:]
    if v.shape[1] < n:
        v = np.pad(v, ((0, 0), (0, n - v.shape[1])))
    return v[:, :n]


def pick_window(dbeats, dur, want_s):
    """Downbeat-snapped [start, end) inside the 60-70% region, length ~want_s and a whole
    number of bars so the loop is seamless. Returns None if the grid can't cover it."""
    db = [t for t in dbeats if 0 <= t <= dur]
    if len(db) < 4:
        return None
    lo = dur * 0.60
    starts = [t for t in db if t >= lo]
    if not starts:
        return None
    start = starts[0]                                   # first downbeat at/after 60%
    if start > dur * 0.70:                              # 60-70% window has no downbeat
        return None
    ends = [t for t in db if t > start]
    if not ends:
        return None
    end = min(ends, key=lambda t: abs((t - start) - want_s))   # nearest downbeat to want_s
    if end - start < want_s * 0.5:                      # track ran out -- too short to be useful
        return None
    return start, end


def stereo_codec(y, kbps, tmp, ext, enc_args):
    wav, out, dec = tmp / "in.wav", tmp / f"o{kbps}.{ext}", tmp / f"d{ext}{kbps}.wav"
    sf.write(wav, y.T, SR)
    subprocess.run(["ffmpeg", "-y", "-i", str(wav), *enc_args, "-b:a", f"{kbps}k", str(out)],
                   capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(out), str(dec)], capture_output=True)
    d, _ = sf.read(dec, dtype="float32", always_2d=True)
    return d.T


def same_roundtrip(seg, cdm, device, mdtype):
    """SAME encode->decode over a long segment, chunked, cross-faded, length-preserving."""
    n = seg.shape[1]
    win = (CHUNK_S * SR // HOP) * HOP
    ov = (OVERLAP_S * SR // HOP) * HOP
    out = np.zeros_like(seg)
    wsum = np.zeros(n, dtype=np.float32)
    pos = 0
    while pos < n:
        end = min(pos + win + 2 * ov, n)
        piece = seg[:, pos:end]
        if piece.shape[1] < HOP:
            out[:, pos:end] += piece
            wsum[pos:end] += 1.0
            break
        pad = (-piece.shape[1]) % HOP
        if pad:
            piece = np.pad(piece, ((0, 0), (0, pad)))
        with torch.no_grad():
            rec = cdm.pretransform.decode(cdm.pretransform.encode(
                torch.tensor(piece[None]).to(device, mdtype)))
        r = rec[0].float().cpu().numpy()[:, :end - pos]
        w = np.ones(r.shape[1], dtype=np.float32)
        t = min(ov, r.shape[1] // 2)
        if t > 0:
            ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, t, dtype=np.float32))
            if pos > 0:
                w[:t] = ramp
            if end < n:
                w[-t:] = ramp[::-1]
        out[:, pos:end] += r * w
        wsum[pos:end] += w
        if end >= n:
            break
        pos += win
    return out / np.maximum(wsum, 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", type=int, default=3)
    ap.add_argument("--seconds", type=float, default=120.0)
    a = ap.parse_args()

    audio_dir = OUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype

    picked = []
    for d in sorted(CORPUS.iterdir()):
        f = d / "full_mix.flac"
        dbf = d / f"{d.name}.DOWNBEATS"
        if not (f.exists() and dbf.exists()):
            continue
        info = sf.info(f)
        if info.samplerate != SR or info.duration < a.seconds * 1.6:
            continue
        try:
            db = [float(x) for x in dbf.read_text().split()]
        except ValueError:
            continue
        w = pick_window(db, info.duration, a.seconds)
        if w:
            picked.append((d, w))
        if len(picked) >= a.tracks:
            break

    manifest = []
    for i, (d, (t0, t1)) in enumerate(picked):
        y, _ = sf.read(d / "full_mix.flac", dtype="float32", always_2d=True,
                       start=int(t0 * SR), stop=int(t1 * SR))
        seg = y.T[:2] if y.shape[1] >= 2 else np.repeat(y.T, 2, 0)
        n = seg.shape[1]
        print(f"[long{i:02d}] {d.name[:40]}  {t0:.1f}s->{t1:.1f}s "
              f"({n/SR:.1f}s, downbeat-snapped)", flush=True)

        versions = {"SAME": same_roundtrip(seg, cdm, device, mdtype)}
        with tempfile.TemporaryDirectory() as td:
            for k in (128, 320):
                versions[f"mp3_{k}"] = stereo_codec(seg, k, Path(td), "mp3", ["-c:a", "libmp3lame"])
            for k in (128, 192, 320):
                versions[f"m4a_{k}"] = stereo_codec(seg, k, Path(td), "m4a", ["-c:a", "aac"])

        cdir = audio_dir / f"long{i:02d}"
        cdir.mkdir(exist_ok=True)
        sf.write(cdir / "original.flac", seg.T, SR)
        entry = {"label": f"{d.name}  ·  {t0/60:.1f}–{t1/60:.1f} min (beat-synced, loops)",
                 "long": True, "loop": True,
                 "audio": {"original": f"audio/long{i:02d}/original.flac"}}
        for vname, v in versions.items():
            lag = lag_of(seg[0], v[0])
            va = apply_lag(v, lag, n)
            resid = 20 * np.log10((np.sqrt(np.mean((seg - va) ** 2)) + 1e-12) /
                                  (np.sqrt(np.mean(seg ** 2)) + 1e-12))
            print(f"    {vname:<10} lag {lag:>6} samples   residual {resid:6.1f} dB", flush=True)
            sf.write(cdir / f"{vname}.flac", va.T, SR)
            entry["audio"][vname] = f"audio/long{i:02d}/{vname}.flac"
        manifest.append(entry)

    p = OUT / "longclips.json"
    p.write_text(json.dumps(manifest, indent=1))
    print(f"[done] {len(manifest)} beat-synced clips -> {p}")


if __name__ == "__main__":
    main()
