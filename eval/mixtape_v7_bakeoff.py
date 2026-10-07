#!/usr/bin/env python
"""mixtape_v7_bakeoff.py — spec S1b: which separator puts the BASSLINE in its bass stem? (psytrance trap)

WHY (GHOST-NOTE 2026-10-07, C's item A): the 4-stem BS-RoFormer we used (SYH99999) leaves the bass stem with ~0 % of the
harmonic low band; the rolling bassline lands in other/drums. This script writes 4-stem dirs (bass/drums/other/vocals .wav at
the clip's own scale, one sub-dir per clip, same numbering as mixtape_v7_stems) for the same clips from other separators so
eval/stem_bass_capture.py can score each by its median CAPTURE (pass bar: median >= 0.60, no clip < 0.30):
  sw      jarredou BS-RoFormer SW (6 stems: bass drums other vocals guitar piano; guitar+piano are folded into 'other')
  demucs  htdemucs_ft (4 stems)
  hpss    NO model: HPSS of the full mix's <150 Hz band -> harmonic = 'bass', percussive = kick into 'drums', everything
          above 150 Hz = 'other'.  Capture is ~1 BY CONSTRUCTION for this baseline; what it shows is whether a plain DSP
          split already beats the learned ones, and what is left in the other stems.
RUN (mir venv; sw and demucs need the GPU: hold the lock via Misc/gpu_guard.sh; hpss is CPU):
  ROCR_VISIBLE_DEVICES=0 /home/kim/Projects/mir/mir/bin/python eval/mixtape_v7_bakeoff.py --model sw|demucs|hpss \
      --stems-root <mixtape_v7_stems> --out-dir <dir>/<model> --every 5
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

MIR = Path("/home/kim/Projects/mir")
sys.path.insert(0, str(MIR / "src"))
sys.path.insert(0, str(MIR))

NAMES = ("bass", "drums", "other", "vocals")


def run_sw(clips, out):
    import torch
    from preprocessing.bs_roformer_sep import load_audio, load_bs_roformer, separate_audio
    sep, mc, ac, ic = load_bs_roformer("jarredou-BS-ROFO-SW-Fixed-drums", str(MIR / "models" / "bs-roformer"), "cuda")
    inst = list(mc.instruments) if mc.instruments else ["bass", "drums", "other", "vocals", "guitar", "piano"]
    for k, p in clips:
        audio, sr = load_audio(p, ac.sample_rate)
        g = 0.9 / max(float(np.abs(audio).max()), 1e-8)
        y = separate_audio(sep, (audio * g).astype(np.float32), ac, mc, ic, torch.device("cuda")) / g
        st = {n: y[inst.index(n)] for n in NAMES}
        st["other"] = st["other"] + sum(y[inst.index(n)] for n in inst if n not in NAMES)
        save(out, k, st, sr)


def run_demucs(clips, out):
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    m = get_model("htdemucs_ft").cuda().eval()
    for k, p in clips:
        x, sr = sf.read(p, dtype="float32")
        assert sr == m.samplerate, (sr, m.samplerate)
        w = torch.from_numpy(x.T).cuda()
        ref = w.mean(0)
        wn = (w - ref.mean()) / (ref.std() + 1e-8)
        with torch.no_grad():
            y = apply_model(m, wn[None], device="cuda", split=True, overlap=0.25)[0]
        y = (y * (ref.std() + 1e-8) + ref.mean()).cpu().numpy()
        save(out, k, {n: y[m.sources.index(n)].T for n in NAMES}, sr)


def run_hpss(clips, out):
    import librosa
    from scipy.signal import butter, sosfiltfilt
    for k, p in clips:
        x, sr = sf.read(p, dtype="float32")
        lo = sosfiltfilt(butter(4, 150, "low", fs=sr, output="sos"), x, axis=0)
        hi = x - lo
        H = np.zeros_like(lo)
        for c in range(x.shape[1]):
            S = librosa.stft(lo[:, c], n_fft=4096, hop_length=1024)
            Hs, Ps = librosa.decompose.hpss(S, kernel_size=(31, 17))
            H[:, c] = librosa.istft(Hs, hop_length=1024, length=len(lo))
        save(out, k, {"bass": H, "drums": lo - H, "other": hi, "vocals": np.zeros_like(x)}, sr)


def save(out, k, st, sr):
    d = Path(out) / f"{k:02d}"
    d.mkdir(parents=True, exist_ok=True)
    for n in NAMES:
        sf.write(str(d / f"{n}.wav"), st[n], sr, subtype="FLOAT")
    print(f"[bakeoff] {k:02d} written", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["sw", "demucs", "hpss"])
    ap.add_argument("--stems-root", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--every", type=int, default=5)
    a = ap.parse_args()
    root = Path(a.stems_root)
    dirs = sorted(p for p in root.iterdir() if p.is_dir())[::a.every]
    clips = [(int(d.name), str(d / "full_mix.wav")) for d in dirs]
    {"sw": run_sw, "demucs": run_demucs, "hpss": run_hpss}[a.model](clips, a.out_dir)


if __name__ == "__main__":
    main()
