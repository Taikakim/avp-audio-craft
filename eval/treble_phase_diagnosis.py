#!/usr/bin/env python
"""treble_phase_diagnosis.py — locate the HF-treble failure (Kim 2026-08-01: "the single
thing keeping outputs from being producer-relevant"). Autopsy BEFORE fix (Kim's directive):
three candidate homes, different fix each — codec discard / DiT collapse / decoder improv.

TEST A — round-trip (isolates the CODEC, no DiT):
  real clip -> SAME encode -> SAME decode. Compare HF (>8 kHz) magnitude retention AND
  phase coherence (STFT phase; group-delay stability) reconstruction-vs-original.
  Clean round-trip => latent does NOT discard treble => problem is generation-side.
  Metallic round-trip => codec ceiling => reconstruction filter is the only lever.

TEST B — encoded vs generated (isolates the DiT):
  per-channel latent energy in the HF-phase channels (from the tone-ladder's peak_freq
  arrays) — encoded real latents vs saved generated z0. Collapse in generated => the DiT
  under-produces HF phase structure (the low-variance-eigendirection / melody-wall
  mechanism in treble guise) => E1a/E1c candidates apply.

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/treble_phase_diagnosis.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import glob
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import stft

from stable_audio_3 import StableAudioModel

CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
LADDER = Path("/run/media/kim/Mantu/sa3_lora_runs/phase_shift_sweep")
GEN_Z0 = "/run/media/kim/Mantu/sa3_control_runs/**/*.z0.npy"      # saved generations
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/treble_diagnosis")
SR = 44100
CLIP_S = 10.0
HF_HZ = 8000
N_TRACKS = 12


def hf_metrics(orig, recon, sr):
    """HF magnitude retention + phase coherence, recon vs orig."""
    f, _, So = stft(orig, fs=sr, nperseg=2048, noverlap=1536)
    _, _, Sr = stft(recon, fs=sr, nperseg=2048, noverlap=1536)
    n = min(So.shape[1], Sr.shape[1])
    So, Sr = So[:, :n], Sr[:, :n]
    hf = f > HF_HZ
    mag_o, mag_r = np.abs(So[hf]), np.abs(Sr[hf])
    mag_ret = float(mag_r.mean() / (mag_o.mean() + 1e-9))          # 1 = preserved
    # phase coherence: how aligned is recon HF phase with orig (weighted by orig mag)
    dphi = np.angle(Sr[hf]) - np.angle(So[hf])
    w = mag_o / (mag_o.sum() + 1e-9)
    phase_coh = float(np.abs((w * np.exp(1j * dphi)).sum()))       # 1 = perfect, 0 = random
    # HF spectral-flatness delta (metallic = raised flatness/whitening)
    flat = lambda M: float(np.exp(np.log(M + 1e-9).mean()) / (M.mean() + 1e-9))
    return {"hf_mag_retention": round(mag_ret, 4),
            "hf_phase_coherence": round(phase_coh, 4),
            "hf_flatness_orig": round(flat(mag_o), 4),
            "hf_flatness_recon": round(flat(mag_r), 4)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    n_clip = int(SR * CLIP_S)

    tracks = [d for d in sorted(CORPUS.iterdir()) if (d / "full_mix.flac").exists()][:N_TRACKS]

    # ---- TEST A: round-trip
    rows, enc_lat = [], []
    for d in tracks:
        a, sr = sf.read(d / "full_mix.flac", dtype="float32", always_2d=True)
        if a.shape[0] < int(60 * sr) + n_clip:
            continue
        seg = a[int(60 * sr):int(60 * sr) + n_clip].T          # [2,N]
        x = torch.tensor(seg[None]).to(device, mdtype)
        with torch.no_grad():
            z = cdm.pretransform.encode(x)
            rec = cdm.pretransform.decode(z)
        enc_lat.append(z[0].float().cpu().numpy())             # [256,T]
        o = seg.mean(0)
        r = rec[0].float().cpu().numpy().mean(0)[:len(o)]
        rows.append(hf_metrics(o, r, sr))
        print(f"[A] {d.name[:30]}: mag_ret {rows[-1]['hf_mag_retention']:.3f} "
              f"phase_coh {rows[-1]['hf_phase_coherence']:.3f} "
              f"flat {rows[-1]['hf_flatness_orig']:.3f}->{rows[-1]['hf_flatness_recon']:.3f}", flush=True)

    A = {k: round(float(np.mean([r[k] for r in rows])), 4) for k in rows[0]}

    # ---- TEST B: encoded vs generated energy in HF-phase channels
    B = {"status": "skipped (no ladder or no generated z0)"}
    lad = sorted(LADDER.glob("sweep_ladder_*hz.npz")) or sorted(LADDER.glob("sweep_tone440.npz"))
    gen = glob.glob(GEN_Z0, recursive=True)
    if lad and gen:
        # HF-phase channels = channels whose ladder peak_freq is high AND locked
        hf_ch = set()
        for f in lad:
            z = np.load(f)
            hf_ch |= set(np.where((z["peak_freq"] > 2000) & (z["osc_score"] > 20))[0].tolist())
        hf_ch = sorted(hf_ch)
        enc = np.concatenate([l for l in enc_lat], axis=1)      # [256, sum T]
        genl = []
        for g in gen[:200]:
            try:
                zz = np.squeeze(np.load(g)).astype(np.float32)
                if zz.ndim == 2 and 256 in zz.shape:
                    genl.append(zz if zz.shape[0] == 256 else zz.T)
            except Exception:
                pass
        if hf_ch and genl:
            G = np.concatenate(genl, axis=1)
            enc_e = enc[hf_ch].var(1).mean()
            gen_e = G[hf_ch].var(1).mean()
            all_enc = enc.var(1).mean(); all_gen = G.var(1).mean()
            B = {"n_hf_channels": len(hf_ch),
                 "enc_hf_var": round(float(enc_e), 4), "gen_hf_var": round(float(gen_e), 4),
                 "hf_ratio_gen_over_enc": round(float(gen_e / (enc_e + 1e-9)), 4),
                 "allband_ratio_gen_over_enc": round(float(all_gen / (all_enc + 1e-9)), 4),
                 "n_generated": len(genl)}
            print(f"[B] HF-phase channels {len(hf_ch)}: gen/enc var ratio "
                  f"{B['hf_ratio_gen_over_enc']:.3f} (all-band {B['allband_ratio_gen_over_enc']:.3f})")

    verdict = ("CODEC preserves treble (round-trip clean) => latent does NOT discard it; "
               "problem is generation-side => E1a/E1c candidates, or a phase-repair postnet "
               "is optional polish"
               if A["hf_phase_coherence"] > 0.5 and A["hf_mag_retention"] > 0.6 else
               "CODEC degrades treble on round-trip => reconstruction/phase-repair filter is "
               "the required lever (DiT cannot recover discarded info)")
    print(f"\nTEST A mean: {A}\nVERDICT: {verdict}")
    (OUT / "results.json").write_text(json.dumps(
        {"test_A_roundtrip": A, "test_A_perclip": rows, "test_B_enc_vs_gen": B,
         "hf_cutoff_hz": HF_HZ, "n_tracks": len(rows), "verdict": verdict,
         "result": None, "kim_feedback": None}, indent=2))
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
