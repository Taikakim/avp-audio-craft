#!/usr/bin/env python
"""transport_vector_probe.py — is the SAME latent "bandwidth-aligned"? (Kim 2026-08-08,
after arXiv 2608.03721 "On the Geometry of Music Bandwidth Extension in Latent Spaces of
Audio Codecs", Koops/Tan/Quinton). Their claim: a SINGLE transport vector = clean−degraded
latent CENTROID difference on a reference set, added to degraded latents, rivals large
diffusion BWE — IF the codec latent is bandwidth-structured. GPU-FREE first pass: tests it
in the SAME latent using the existing mp3_latent_sensitivity latents (per track
(5,256,256) = [version, 256ch, 256fr]; version 0=FLAC clean, 1..4 = mp3@320/256/192/128k =
HF-degraded, frame-aligned to FLAC by the source xcorr).

Metric (held-out tracks): recovery_frac = 1 − ‖z_clean − (z_deg + v)‖ / ‖z_clean − z_deg‖,
per frame, mean. 1.0 = transport vector fully closes the gap (latent IS bandwidth-aligned);
~0 = it doesn't (not aligned → arithmetic won't restore, generative #62 justified). Controls:
random vector of matched norm (~0), per-track oracle vector (upper bound).

Run (any venv, NO GPU):  .venv/bin/python eval/transport_vector_probe.py
"""
import json
from pathlib import Path

import numpy as np

NPZ = "/run/media/kim/Mantu/sa3_control_runs/analysis/mp3_latent_sensitivity_2026-08-04/latents.npz"
OUT = Path("/home/kim/Projects/SAO/eval/musicology/transport_vector_probe_2026-08-08")
OUT.mkdir(parents=True, exist_ok=True)
BITRATES = {1: "320k", 2: "256k", 3: "192k", 4: "128k"}
RNG = np.random.RandomState(0)


def recovery(z_clean, z_deg, v):
    """1 − ‖clean−(deg+v)‖/‖clean−deg‖, per-frame mean. z_*: [N,256] frame stacks."""
    base = np.linalg.norm(z_clean - z_deg, axis=1)
    resid = np.linalg.norm(z_clean - (z_deg + v), axis=1)
    return float(np.mean(1.0 - resid / (base + 1e-9)))


def main():
    d = np.load(NPZ, allow_pickle=True)
    tracks = list(d.files)
    # [track][version] -> [256fr, 256ch]  (transpose from stored [ch,fr])
    L = {t: d[t].astype(np.float64).transpose(0, 2, 1) for t in tracks}  # (5, 256fr, 256ch)
    n = len(tracks)
    tr, te = tracks[: n * 2 // 3], tracks[n * 2 // 3:]
    print(f"tracks: {n} ({len(tr)} train / {len(te)} test); frames/track={L[tracks[0]].shape[1]}")

    rows = []
    for vi, name in BITRATES.items():
        # transport vector = clean−deg CENTROID over TRAIN (mean over tracks & frames) -> [256]
        clean_c = np.mean([L[t][0].reshape(-1, 256) for t in tr], axis=(0)).mean(0)
        deg_c = np.mean([L[t][vi].reshape(-1, 256) for t in tr], axis=(0)).mean(0)
        v = clean_c - deg_c

        # held-out recovery
        zc = np.concatenate([L[t][0].reshape(-1, 256) for t in te])
        zd = np.concatenate([L[t][vi].reshape(-1, 256) for t in te])
        rec = recovery(zc, zd, v)
        # controls
        vrand = RNG.randn(256); vrand *= np.linalg.norm(v) / (np.linalg.norm(vrand) + 1e-9)
        rec_rand = recovery(zc, zd, vrand)
        # per-track oracle upper bound (best constant vector per test track = its own clean−deg mean)
        orc = np.mean([recovery(L[t][0].reshape(-1, 256), L[t][vi].reshape(-1, 256),
                                L[t][0].reshape(-1, 256).mean(0) - L[t][vi].reshape(-1, 256).mean(0))
                       for t in te])
        gap = float(np.linalg.norm(zc - zd, axis=1).mean())
        rows.append({"bitrate": name, "gap_L2": round(gap, 3), "recovery_transport": round(rec, 4),
                     "recovery_random_ctrl": round(rec_rand, 4), "recovery_pertrack_oracle": round(orc, 4),
                     "transport_vec_norm": round(float(np.linalg.norm(v)), 3)})

    verdict = ("ALIGNED — a single transport vector meaningfully closes the HF gap; the arXiv-2608.03721 "
               "cheap baseline is on the table for SAME (test decode-verify next)."
               if max(r["recovery_transport"] for r in rows) > 0.30 else
               "NOT bandwidth-aligned — a single transport vector barely helps (recovery≈random); SAME's HF "
               "loss is not an arithmetic latent offset → generative restoration (#62) is justified.")
    summary = {"purpose": "is SAME latent bandwidth-aligned? (transport-vector baseline, arXiv 2608.03721)",
               "source": "mp3_latent_sensitivity latents.npz (FLAC vs mp3@320/256/192/128 -> SAME)",
               "held_out_tracks": len(te), "rows": rows, "verdict": verdict,
               "caveat": "MP3 HF-loss is a PROXY for SAME's own roundtrip HF loss; the SAME-own transport "
                         "vector needs a GPU encode of original-vs-SAME pairs (decode-verify stage)."}
    (OUT / "results.json").write_text(json.dumps(summary, indent=2))

    print(f"\n{'bitrate':<8}{'gap_L2':>9}{'transport':>11}{'random':>9}{'oracle':>9}")
    for r in rows:
        print(f"{r['bitrate']:<8}{r['gap_L2']:>9.2f}{r['recovery_transport']:>11.3f}"
              f"{r['recovery_random_ctrl']:>9.3f}{r['recovery_pertrack_oracle']:>9.3f}")
    print(f"\nVERDICT: {verdict}")
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
