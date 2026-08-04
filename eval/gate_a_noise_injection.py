"""gate_a_noise_injection.py — Gate A of the residual-preservation plan (docs/ai-research/
residual-preservation-2026-07-19.md §3). The FREE, decisive-first test: does restoring the
latent's high-frequency TEMPORAL spectrum (by adding corpus-shaped noise to existing z0
latents, no training, no re-sampling) pull the decoded audio haze toward real?

Mechanism under test: generations are HF-deficient along the time axis (corpus temporal
hf_frac ~0.40 vs gen ~0.30 — a real, loudness-independent deficit). If the haze is just a
missing-stationary-HF-texture problem, adding shaped noise to match the corpus temporal PSD
BY CONSTRUCTION should move decoded spectral_flatness from ~0.016 toward real 0.0076 — and
then we ship noise-injection / SDE sampling with NO training. If it doesn't move (or worsens),
the marginal-spectrum losses (L_psd/L_var/L_cov) are all insufficient and we proceed to Gate B.

Per channel c, along time: raise hf_frac to the corpus target by ADDING HF noise only
(content = the low-freq part is untouched), shaped to the corpus HF PSD. z0' = z0 + n.

Run (mir venv — numpy+librosa+onnxruntime): mir/bin/python eval/gate_a_noise_injection.py
Decodes are forced CPU (--provider cpu) so they don't contend with the GPU campaign.
"""
import glob
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

MM = Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix")
CORPUS = Path("/home/kim/Projects/latents_sa3")
DEC = Path("/home/kim/Projects/SAO/onnx/decode_onnx.py")
ONNX = Path("/home/kim/Projects/SAO/stable-audio-3/same_decoder_L128.onnx")
OUT = Path("/tmp/gate_a"); OUT.mkdir(exist_ok=True)
T = 280                      # gen latent length
SPLIT = T // 2 + 1           # rfft bins = 141; HF = upper half
HF0 = SPLIT // 2             # HF band start bin
RNG = np.random.default_rng(0)


def temporal_psd(z):
    """|rfft along time|^2, (C, F). z: (C, T) float32."""
    return np.abs(np.fft.rfft(z, axis=-1)) ** 2


def corpus_hf_target(n=200):
    """Corpus mean hf_frac + normalized HF PSD shape (over n crops, sliced to T)."""
    crops = sorted(glob.glob(str(CORPUS / "*.npy")))[:n]
    hf_fracs, hf_shape = [], np.zeros(SPLIT - HF0)
    for p in crops:
        z = np.load(p).astype(np.float32)[:, :T]         # corpus is (256, 4096) -> (256, T)
        P = temporal_psd(z)                               # (256, F)
        tot = P.sum(-1); hf = P[:, HF0:].sum(-1)
        hf_fracs.append((hf / (tot + 1e-12)))
        hf_shape += P[:, HF0:].mean(0)
    hf_frac = float(np.concatenate(hf_fracs).mean())
    hf_shape /= (hf_shape.sum() + 1e-12)
    return hf_frac, hf_shape


def inject(z, hf_frac_t, hf_shape):
    """z: (1,256,T) -> z' with per-channel temporal hf_frac raised to hf_frac_t by adding
    corpus-shaped HF noise. Low-freq content untouched."""
    x = z.astype(np.float32)[0]                           # (256, T)
    X = np.fft.rfft(x, axis=-1)                            # (256, F)
    P = np.abs(X) ** 2
    L = P[:, :HF0].sum(-1); H = P[:, HF0:].sum(-1)         # per-channel LF/HF power
    H_t = hf_frac_t * (L + H)                              # target HF power (so hf/(l+h)=t after)
    dH = np.clip(H_t - H, 0, None)                         # HF power to add per channel
    # build noise spectrum on HF bins: magnitude ~ sqrt(shape*dH), random phase
    mag = np.sqrt(hf_shape[None, :] * dH[:, None] + 1e-20)  # (256, HFbins)
    phase = np.exp(1j * RNG.uniform(0, 2 * np.pi, mag.shape))
    Nspec = np.zeros_like(X)
    Nspec[:, HF0:] = mag * phase
    n = np.fft.irfft(Nspec, n=T, axis=-1).astype(np.float32)
    return (x + n)[None].astype(np.float16)


def decode(npy, wav):
    subprocess.run([sys.executable, str(DEC), "--onnx", str(ONNX), "--npy", str(npy),
                    "--chunk-latents", "128", "--overlap", "16", "--provider", "cpu",
                    "--out", str(wav)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def flatness(wav):
    import librosa
    y, _ = librosa.load(str(wav), sr=22050, mono=True)
    S = np.abs(librosa.stft(y, n_fft=2048))
    return float(librosa.feature.spectral_flatness(S=S).mean())


def main():
    hf_frac_t, hf_shape = corpus_hf_target()
    print(f"[gate-A] corpus temporal hf_frac target = {hf_frac_t:.3f}; real audio flatness ref = 0.0076")
    # a handful of gen latents: the base+dora paired keys + a couple extra dora
    zs = glob.glob(str(MM / "*.z0.npy"))
    def key(p): return "__".join(os.path.basename(p).split("__")[-3:])
    base = {key(p): p for p in zs if os.path.basename(p).startswith("base__")}
    dora = {key(p): p for p in zs if not os.path.basename(p).startswith("base__")}
    picks = []
    for k in sorted(set(base) & set(dora))[:3]:
        picks += [("base", base[k]), ("dora", dora[k])]
    print(f"[gate-A] {len(picks)} latents (paired base+dora)\n")
    print(f"{'label':6s} {'clip':30s} {'flat_orig':>9s} {'flat_inj':>9s}  {'->real?':>8s}")
    rows = []
    for lab, p in picks:
        z = np.load(p)
        zp = inject(z, hf_frac_t, hf_shape)
        tag = os.path.basename(p).replace(".z0.npy", "")[:30]
        np_orig = OUT / f"{lab}_{tag}_orig.npy"; np_inj = OUT / f"{lab}_{tag}_inj.npy"
        np.save(np_orig, z.astype(np.float32)); np.save(np_inj, zp.astype(np.float32))
        w_orig = OUT / f"{lab}_{tag}_orig.wav"; w_inj = OUT / f"{lab}_{tag}_inj.wav"
        decode(np_orig, w_orig); decode(np_inj, w_inj)
        f0, f1 = flatness(w_orig), flatness(w_inj)
        moved = "toward" if f1 < f0 - 0.001 else ("away" if f1 > f0 + 0.001 else "flat")
        print(f"{lab:6s} {tag:30s} {f0:9.4f} {f1:9.4f}  {moved:>8s}")
        rows.append((lab, f0, f1))
    import statistics as st
    print(f"\n[gate-A] median flat  orig={st.median(r[1] for r in rows):.4f}  "
          f"inj={st.median(r[2] for r in rows):.4f}  (real 0.0076)")
    print("[gate-A] DECISION: injected << orig and toward 0.0076 => haze fixable free (ship SDE/noise). "
          "Unmoved/worse => marginal-spectrum losses insufficient => Gate B.")


if __name__ == "__main__":
    main()
