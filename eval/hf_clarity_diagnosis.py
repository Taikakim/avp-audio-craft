#!/usr/bin/env python
"""hf_clarity_diagnosis.py — HF CLARITY (not metallic-ness) diagnosis (Kim 2026-08-01:
"lack of clarity, like 128kbps MP3 late 90s; the ear DOES decode airy-region info").

Reframe: the producer-relevant defect is loss of HF TEMPORAL-ENVELOPE DETAIL and fine
structure (transients, shimmer, "air"), NOT carrier-phase randomness. This probe measures
that, and places SAME's encode->decode round-trip ON THE SAME AXES AS REAL MP3 (128k/320k)
so "how bad, in units producers know" is answerable.

Per clip, per version vs ORIGINAL, in two bands (presence 4-8kHz, air 8-16kHz),
after envelope-xcorr time alignment. Versions (Kim 2026-08-06 — m4a leg added so the
audition serving codec sits on the SAME axis as MP3 and the SAME round-trip):
  SAME                       : the frozen SA3 codec encode->decode round-trip
  mp3_128, mp3_320           : real libmp3lame MP3 anchors (the "producer units")
  m4a_128, m4a_192, m4a_320  : native-AAC .m4a at OUR audition serving bitrates
                               (128/192) + a 320 anchor matching mp3_320
  env_corr      : corr of band Hilbert-envelope (temporal detail retention; 1=perfect)
  fastmod_ret   : envelope modulation-spectrum energy >20Hz, ver/orig (crispness)
  crest_ret     : band crest factor ver/orig (transient sharpness; <1 = smeared)
  flatness_delta: band spectral flatness ver-orig (>0 = detail->wash = the veil)
  energy_ret    : band RMS ver/orig (bandwidth/rolloff)
Plus full-signal 85%-power spectral-rolloff freq per version (bass-dominated, so a
weak HF discriminator — read the band env_corr, not rolloff).

Also exports the aligned, measured mono audio for the first EXPORT_N clips as LOSSLESS
FLAC (OUT/audio/) so codec artifacts survive intact to the ear on the audit page;
build_clarity_audit_page.py turns results.json + that audio into the online page.

Run (SA3 venv, GPU for the SAME leg, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/hf_clarity_diagnosis.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, sosfiltfilt, hilbert, welch

from stable_audio_3 import StableAudioModel

CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/hf_clarity")
SR = 44100
CLIP_S = 8.0
N_TRACKS = 12
EXPORT_N = 4          # first N clips get their aligned audio dumped for the audit page
BANDS = {"presence_4-8k": (4000, 8000), "air_8-16k": (8000, 16000)}


def bandpass(y, lo, hi):
    hi = min(hi, SR / 2 - 100)
    return sosfiltfilt(butter(4, [lo, hi], btype="band", fs=SR, output="sos"), y)


def align(ref, y):
    """shift y to best-match ref via broadband-envelope xcorr (mp3 codec delay)."""
    n = min(len(ref), len(y))
    ref, y = ref[:n], y[:n]
    er = np.abs(hilbert(ref[::16])); ey = np.abs(hilbert(y[::16]))
    er -= er.mean(); ey -= ey.mean()
    xc = np.correlate(er, ey, mode="full")
    lag = (xc.argmax() - (len(ey) - 1)) * 16
    if lag > 0:
        y = np.concatenate([np.zeros(lag, np.float32), y])[:n]
    elif lag < 0:
        y = y[-lag:]
        y = np.concatenate([y, np.zeros(n - len(y), np.float32)])
    return ref, y[:n]


def band_metrics(o, v, lo, hi):
    bo, bv = bandpass(o, lo, hi), bandpass(v, lo, hi)
    eo, ev = np.abs(hilbert(bo)), np.abs(hilbert(bv))
    env_corr = float(np.corrcoef(eo, ev)[0, 1])
    def fastmod(e):
        f, p = welch(e - e.mean(), fs=SR, nperseg=8192)
        return p[f > 20].sum() / (p.sum() + 1e-12)
    fastmod_ret = float(fastmod(ev) / (fastmod(eo) + 1e-12))
    crest_ret = float((np.abs(bv).max() / (bv.std() + 1e-9)) /
                      (np.abs(bo).max() / (bo.std() + 1e-9) + 1e-9))
    def flat(b):
        f, p = welch(b, fs=SR, nperseg=4096)
        m = p[(f >= lo) & (f <= hi)] + 1e-12
        return float(np.exp(np.log(m).mean()) / m.mean())
    energy_ret = float(bv.std() / (bo.std() + 1e-9))
    return {"env_corr": round(env_corr, 3), "fastmod_ret": round(fastmod_ret, 3),
            "crest_ret": round(crest_ret, 3), "flatness_delta": round(flat(bv) - flat(bo), 4),
            "energy_ret": round(energy_ret, 3)}


def rolloff(y):
    f, p = welch(y, fs=SR, nperseg=8192)
    c = np.cumsum(p)
    return float(f[np.searchsorted(c, 0.85 * c[-1])])


def _codec_roundtrip(y, kbps, tmp, ext, enc_args):
    """encode y (mono) to <ext> at kbps via ffmpeg, decode back, return mono float32."""
    wav, out, dec = tmp / "in.wav", tmp / f"o{kbps}.{ext}", tmp / f"d{ext}{kbps}.wav"
    sf.write(wav, y, SR)
    subprocess.run(["ffmpeg", "-y", "-i", str(wav), *enc_args, "-b:a", f"{kbps}k",
                    str(out)], capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(out), str(dec)], capture_output=True)
    d, _ = sf.read(dec, dtype="float32", always_2d=True)
    return d.mean(1)


def mp3(y, kbps, tmp):
    return _codec_roundtrip(y, kbps, tmp, "mp3", ["-c:a", "libmp3lame"])


def m4a(y, kbps, tmp):
    # native AAC (no libfdk) in an m4a container = exactly our audition serving codec
    return _codec_roundtrip(y, kbps, tmp, "m4a", ["-c:a", "aac"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    have_ffmpeg = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    n_clip = int(SR * CLIP_S)
    tracks = [d for d in sorted(CORPUS.iterdir()) if (d / "full_mix.flac").exists()][:N_TRACKS]

    audio_dir = OUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    agg = {}
    clips_manifest = []          # per-exported-clip: label + {version: relpath}
    ci = 0
    for d in tracks:
        a, sr = sf.read(d / "full_mix.flac", dtype="float32", always_2d=True)
        if a.shape[0] < int(60 * sr) + n_clip:
            continue
        seg = a[int(60 * sr):int(60 * sr) + n_clip].T
        o = seg.mean(0).astype(np.float32)
        with torch.no_grad():
            rec = cdm.pretransform.decode(cdm.pretransform.encode(
                torch.tensor(seg[None]).to(device, mdtype)))
        versions = {"SAME": rec[0].float().cpu().numpy().mean(0)[:len(o)]}
        if have_ffmpeg:
            with tempfile.TemporaryDirectory() as td:
                for k in (128, 320):
                    versions[f"mp3_{k}"] = mp3(o, k, Path(td))
                for k in (128, 192, 320):
                    versions[f"m4a_{k}"] = m4a(o, k, Path(td))
        export = ci < EXPORT_N
        clip_audio = {}
        if export:
            cdir = audio_dir / f"clip{ci:02d}"
            cdir.mkdir(exist_ok=True)
            sf.write(cdir / "original.flac", o, SR)   # unaligned reference (t=0)
            clip_audio["original"] = f"audio/clip{ci:02d}/original.flac"
        for vname, v in versions.items():
            oa, va = align(o, v.astype(np.float32))
            for bname, (lo, hi) in BANDS.items():
                agg.setdefault((vname, bname), []).append(band_metrics(oa, va, lo, hi))
            agg.setdefault((vname, "rolloff_hz"), []).append(rolloff(va))
            if export:
                sf.write(cdir / f"{vname}.flac", va, SR)  # aligned -> same-playhead
                clip_audio[vname] = f"audio/clip{ci:02d}/{vname}.flac"
        if export:
            clips_manifest.append({"label": d.name, "audio": clip_audio})
        agg.setdefault(("original", "rolloff_hz"), []).append(rolloff(o))
        print(f"[clip] {d.name[:34]}: SAME air env_corr "
              f"{band_metrics(*align(o, versions['SAME'].astype(np.float32)), 8000, 16000)['env_corr']:.3f}",
              flush=True)
        ci += 1

    # aggregate
    summary = {}
    for (vname, bname), lst in agg.items():
        if bname == "rolloff_hz":
            summary.setdefault(vname, {})["rolloff_hz"] = round(float(np.mean(lst)), 0)
        else:
            summary.setdefault(vname, {})[bname] = {
                k: round(float(np.mean([r[k] for r in lst])), 3) for k in lst[0]}
    (OUT / "results.json").write_text(json.dumps(
        {"summary": summary, "n_tracks": len(tracks), "bands": BANDS,
         "have_mp3_anchors": have_ffmpeg, "clips": clips_manifest,
         "reading": "env_corr/crest_ret near 1 = temporal detail kept; <<1 = smeared. "
                    "flatness_delta>0 = detail->wash (the veil). Compare SAME to the mp3_* / "
                    "m4a_* codec anchors to place the round-trip on the codec clarity ladder.",
         "result": None, "kim_feedback": None}, indent=2))
    print("\nSUMMARY (air 8-16k):")
    for v in summary:
        air = summary[v].get("air_8-16k", {})
        print(f"  {v:<10} env_corr {air.get('env_corr','-')} crest_ret "
              f"{air.get('crest_ret','-')} flat_delta {air.get('flatness_delta','-')} "
              f"rolloff {summary[v].get('rolloff_hz','-')}Hz")
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
