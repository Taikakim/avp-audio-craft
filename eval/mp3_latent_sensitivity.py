#!/usr/bin/env python
"""mp3_latent_sensitivity.py -- does MP3 source bitrate change the SAME latents?

Question (for the big-FT 256k+ MP3 corpus re-source decision): MP3 artifacts sit
below the SAME encoder's ~4096x compression floor, so at >=256k the latents should be
~indistinguishable from FLAC. Test it directly.

Method (per track):
  - take a fixed 256-frame (~23.79 s) window at the track MIDPOINT from the full-mix FLAC;
  - transcode that window to MP3 @ {320,256,192,128}k (libmp3lame), keep FLAC as reference;
  - decode each back to 44.1k stereo PCM;
  - align each MP3 to the FLAC by integer-sample cross-correlation (kills LAME's ~1.1k-sample
    codec delay -- the key alignment caveat), crop all to identical 256*ds samples;
  - encode every version through the medium-base SAME pretransform (fp16) -> latent [256, T];
    this is the SAME encode path used to build the melody/fifthjump calibration references,
    so the delta magnitudes are directly comparable.

Metrics vs the FLAC latent, per (track,bitrate):
  - relative L2 (Frobenius): ||z_mp3 - z_flac||_F / ||z_flac||_F
  - cosine (flattened)
  - per-FRAME delta norm ||z_mp3[:,t]-z_flac[:,t]||_2 (256-dim), mean & max over t
    -> directly comparable to the fifth-jump single-note delta (||d||~=5.64)
  - fraction of the per-frame delta lying in the 15-dim MELODY subspace (basis15)
  - per-channel delta RMS / per-channel latent std

Calibration yardsticks:
  (a) per-channel latent std (measured on the FLAC refs here)
  (b) single-note musical delta: fifth-jump ||d||~=4.44-6.90 (mean 5.64),
      eval/musicology/latent_melody_analysis_v2/stage3_fifthjump_v2.npz

CALLER holds /home/kim/Projects/SAO/.gpu.lock around this script. SA3 fast venv.
Outputs: results.json + per-track latents npz + REPORT.md in --out-dir (self-describing).
"""
import os
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

SR = 44100
BITRATES = [320, 256, 192, 128]  # kbps
PAD_SEC = 0.5                     # context each side for clean edges + alignment search
MAX_LAG = 8192                    # +/- samples for MP3<->FLAC alignment search
FIFTH = Path("/home/kim/Projects/SAO/eval/musicology/latent_melody_analysis_v2/stage3_fifthjump_v2.npz")
MELODY = Path("/home/kim/Projects/SAO/lumi/melody_subspace15_v2.npz")


def ffmpeg_pcm(args_in, extra):
    """Run ffmpeg, return decoded float32 stereo PCM as (2, N)."""
    cmd = ["/usr/bin/ffmpeg", "-v", "error", "-nostdin", *args_in, *extra,
           "-ar", str(SR), "-ac", "2", "-f", "f32le", "-c:a", "pcm_f32le", "pipe:1"]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    a = np.frombuffer(p.stdout, dtype="<f4").astype(np.float32)
    return a.reshape(-1, 2).T  # (2, N)


def extract_versions(flac, mid_sec, n_target, workdir):
    """Return dict version-> (2,N) padded PCM: 'flac' + each bitrate. Same source window."""
    win_dur = n_target / SR
    start = mid_sec - PAD_SEC
    dur = win_dur + 2 * PAD_SEC
    # FLAC reference (lossless) padded window -> wav on disk (source for the mp3 encodes)
    ref_wav = workdir / "ref.wav"
    subprocess.run(["/usr/bin/ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.6f}",
                    "-t", f"{dur:.6f}", "-i", str(flac), "-ar", str(SR), "-ac", "2",
                    "-c:a", "pcm_f32le", "-y", str(ref_wav)],
                   check=True, stderr=subprocess.PIPE)
    out = {"flac": ffmpeg_pcm(["-i", str(ref_wav)], [])}
    for br in BITRATES:
        mp3 = workdir / f"{br}.mp3"
        subprocess.run(["/usr/bin/ffmpeg", "-v", "error", "-nostdin", "-i", str(ref_wav),
                        "-c:a", "libmp3lame", "-b:a", f"{br}k", "-y", str(mp3)],
                       check=True, stderr=subprocess.PIPE)
        out[str(br)] = ffmpeg_pcm(["-i", str(mp3)], [])
    return out


def align_crop(ref, other, pad_samp, n_target):
    """Crop ref[pad:pad+N]; find integer lag maximizing corr, return (ref_seg, other_seg) (2,N)."""
    N = n_target
    ref_seg = ref[:, pad_samp:pad_samp + N]
    # correlate on a central mono subwindow for speed
    w0 = pad_samp + N // 2 - 32768
    w1 = w0 + 65536
    rm = ref[:, w0:w1].mean(0)
    rm = rm - rm.mean()
    best_lag, best = 0, -np.inf
    om_full = other.mean(0)
    for lag in range(-MAX_LAG, MAX_LAG + 1, 1):
        seg = om_full[w0 + lag:w1 + lag]
        if seg.shape[0] != rm.shape[0]:
            continue
        seg = seg - seg.mean()
        c = float(rm @ seg)
        if c > best:
            best, best_lag = c, lag
    s = pad_samp + best_lag
    return ref_seg, other[:, s:s + N], best_lag


def load_pretransform(device="cuda"):
    import torch
    from safetensors.torch import load_file
    from stable_audio_3.model_configs import all_models
    from stable_audio_3.factory import create_pretransform_from_config
    from stable_audio_3.loading_utils import copy_state_dict
    cfg_path, ckpt_path = all_models["medium-base"].resolve()
    cfg = json.load(open(cfg_path))
    sr = cfg["sample_rate"]
    assert sr == SR, f"config sr {sr} != {SR}"
    pt = create_pretransform_from_config(cfg.get("model", cfg), sr).to(device).half().eval().requires_grad_(False)
    sd = load_file(ckpt_path)
    copy_state_dict(pt, {k[len("pretransform."):]: v for k, v in sd.items() if k.startswith("pretransform.")})
    return pt, int(pt.downsampling_ratio)


def encode(pt, pcm_2N, n_frames):
    """pcm (2,N) -> latent (256, n_frames) float32."""
    import torch
    x = torch.from_numpy(pcm_2N).unsqueeze(0).cuda().half()  # (1,2,N)
    with torch.no_grad():
        z = pt.encode(x)[0]  # (256, T)
    z = z.float().cpu().numpy()
    return z[:, :n_frames]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", required=True, help="file with one full_mix.flac path per line")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--frames", type=int, default=256)
    args = ap.parse_args()
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    tracks = [l.strip() for l in open(args.tracks) if l.strip()]

    basis = np.load(MELODY)["basis15"].astype(np.float32)          # (15,256) orthonormal
    fifth = np.load(FIFTH)["deltas"].astype(np.float32)            # (10,256)
    fifth_norm = float(np.linalg.norm(fifth, axis=1).mean())      # ~5.64
    fifth_mel = float(np.mean([np.linalg.norm(basis @ d) for d in fifth]))

    pt, ds = load_pretransform()
    n_target = args.frames * ds
    pad_samp = int(round(PAD_SEC * SR))
    print(f"[cfg] ds={ds} frames={args.frames} n_target={n_target} ({n_target/SR:.3f}s) "
          f"fifth_norm={fifth_norm:.3f}", flush=True)

    rows = []
    lat_store = {}
    chan_std_accum = []
    t0 = time.time()
    for ti, flac in enumerate(tracks):
        flac = Path(flac)
        name = flac.parent.name
        import soundfile as sf
        dur = sf.info(str(flac)).frames / sf.info(str(flac)).samplerate
        mid = dur / 2.0
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            try:
                vers = extract_versions(flac, mid, n_target, td)
            except subprocess.CalledProcessError as e:
                print(f"[skip] {name}: ffmpeg fail {e}", flush=True)
                continue
            ref = vers["flac"]
            if ref.shape[1] < pad_samp + n_target:
                print(f"[skip] {name}: short window {ref.shape}", flush=True)
                continue
            lats = {}
            lags = {}
            ref_seg = ref[:, pad_samp:pad_samp + n_target]
            lats["flac"] = encode(pt, np.ascontiguousarray(ref_seg), args.frames)
            for br in BITRATES:
                o = vers[str(br)]
                _, o_seg, lag = align_crop(ref, o, pad_samp, n_target)
                if o_seg.shape[1] != n_target:
                    print(f"[skip] {name} br{br}: crop {o_seg.shape}", flush=True)
                    o_seg = np.zeros_like(ref_seg)
                lats[str(br)] = encode(pt, np.ascontiguousarray(o_seg), args.frames)
                lags[br] = lag
        zf = lats["flac"]                                   # (256, F)
        chan_std_accum.append(zf.std(axis=1))               # per-channel std over time
        zf_fro = float(np.linalg.norm(zf))
        for br in BITRATES:
            zm = lats[str(br)]
            d = zm - zf                                     # (256, F)
            frame_dn = np.linalg.norm(d, axis=0)            # (F,) per-frame 256-dim delta norm
            # melody fraction per frame (mean over frames), and abs melody-projected norm
            mel_proj = basis @ d                            # (15, F)
            mel_frac = float(np.mean((mel_proj ** 2).sum(0) / (frame_dn ** 2 + 1e-12)))
            mel_abs = float(np.linalg.norm(mel_proj, axis=0).mean())
            # per-channel delta rms vs per-channel latent std
            ch_drms = np.sqrt((d ** 2).mean(1))             # (256,)
            ch_std = zf.std(axis=1) + 1e-9
            rows.append({
                "track": name, "bitrate": br,
                "rel_l2_fro": round(float(np.linalg.norm(d) / zf_fro), 5),
                "cosine": round(float((zm.ravel() @ zf.ravel()) /
                                      (np.linalg.norm(zm) * zf_fro)), 6),
                "frame_delta_mean": round(float(frame_dn.mean()), 4),
                "frame_delta_max": round(float(frame_dn.max()), 4),
                "melody_frac": round(mel_frac, 4),
                "melody_abs_mean": round(mel_abs, 4),
                "chan_drms_over_std_mean": round(float((ch_drms / ch_std).mean()), 4),
                "lag_samples": lags[br],
            })
        lat_store[name] = np.stack([lats["flac"]] + [lats[str(b)] for b in BITRATES])
        print(f"[{ti+1}/{len(tracks)}] {name[:44]:44s} lags={lags} "
              f"d128={rows[-1]['frame_delta_mean']:.2f} {time.time()-t0:.0f}s", flush=True)

    chan_std = np.mean(chan_std_accum, axis=0)              # (256,)
    chan_std_mean = float(chan_std.mean())
    std_vec_norm = float(np.sqrt((chan_std ** 2).sum()))    # norm of a 1-sigma-per-channel vector

    # aggregate per bitrate
    agg = {}
    for br in BITRATES:
        r = [x for x in rows if x["bitrate"] == br]
        fdm = np.array([x["frame_delta_mean"] for x in r])
        agg[br] = {
            "n": len(r),
            "rel_l2_mean": round(float(np.mean([x["rel_l2_fro"] for x in r])), 5),
            "rel_l2_max": round(float(np.max([x["rel_l2_fro"] for x in r])), 5),
            "cosine_mean": round(float(np.mean([x["cosine"] for x in r])), 6),
            "cosine_min": round(float(np.min([x["cosine"] for x in r])), 6),
            "frame_delta_mean": round(float(fdm.mean()), 4),
            "frame_delta_max": round(float(np.max([x["frame_delta_max"] for x in r])), 4),
            "melody_frac_mean": round(float(np.mean([x["melody_frac"] for x in r])), 4),
            "melody_abs_mean": round(float(np.mean([x["melody_abs_mean"] for x in r])), 4),
            "chan_drms_over_std_mean": round(float(np.mean([x["chan_drms_over_std_mean"] for x in r])), 4),
            # calibration
            "frac_of_fifthjump": round(float(fdm.mean() / fifth_norm), 4),
            "frac_of_std_vec": round(float(fdm.mean() / std_vec_norm), 4),
        }

    result = {
        "purpose": "Measure how MP3 source bitrate perturbs SAME (medium-base pretransform) "
                   "latents vs FLAC, to decide if the 256k+ MP3 big-FT corpus needs FLAC re-sourcing.",
        "method_note": "256-frame midpoint window; MP3 aligned to FLAC by xcorr; medium-base "
                       "pretransform fp16 encode (same path as the melody/fifthjump calibration).",
        "n_tracks": len(lat_store), "frames": args.frames, "ds": ds, "sr": SR,
        "calibration": {
            "fifthjump_delta_norm_mean": round(fifth_norm, 4),
            "fifthjump_delta_norm_range": [round(float(np.linalg.norm(fifth, axis=1).min()), 3),
                                           round(float(np.linalg.norm(fifth, axis=1).max()), 3)],
            "fifthjump_melody_abs_mean": round(fifth_mel, 4),
            "per_channel_std_mean": round(chan_std_mean, 4),
            "one_sigma_vector_norm": round(std_vec_norm, 4),
            "melody_random_frac_baseline": round(15 / 256, 4),
        },
        "by_bitrate": agg,
        "per_track": rows,
        "refs": {"fifthjump": str(FIFTH), "melody_basis": str(MELODY),
                 "encode_ref_script": "eval/musicology/latent_melody_analysis_v2/encode_test_midis_v2.py"},
    }
    (out / "results.json").write_text(json.dumps(result, indent=1))
    np.savez_compressed(out / "latents.npz", **{k: v for k, v in lat_store.items()})
    print("saved", out / "results.json", flush=True)
    # console summary
    print("\nbitrate  relL2    cosine    frameΔ   /fifth  /σvec   melFrac")
    for br in BITRATES:
        a = agg[br]
        print(f"{br:>5}k  {a['rel_l2_mean']:.4f}  {a['cosine_mean']:.5f}  "
              f"{a['frame_delta_mean']:.3f}   {a['frac_of_fifthjump']:.3f}  "
              f"{a['frac_of_std_vec']:.3f}  {a['melody_frac_mean']:.4f}")
    print(f"\nfifthjump ||d||={fifth_norm:.3f}  per-ch σ={chan_std_mean:.3f}  "
          f"1σ-vec norm={std_vec_norm:.3f}  melody random baseline={15/256:.3f}")


if __name__ == "__main__":
    main()
