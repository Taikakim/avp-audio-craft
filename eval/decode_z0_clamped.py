#!/usr/bin/env python
"""decode_z0_clamped.py — re-decode saved z0 latents with the VADD tier-3 std ceiling and score the result.

WHY (CONTINUITY, 2026-10-07; Kim's ask: one faultless DJ mixtape). Merged-adapter re-renders removed the
corruption from the euler/cfg7 clips of the mixtape corpus but not from the post-trained (`_ptm`, 8-step
ping-pong) ones, several of which sit at latent std 1.4-2.3. The decoder answers a too-wide latent with
single-sample discontinuities (EXPERIMENTS A14). VADD tier 3 is the cure that needs no re-sampling: scale the
whole latent by ceiling/std when std > ceiling, exactly as scripts/eval_demo_callback.py does before decode.
This applies it to latents we already saved next to every render, at several ceilings, and counts the
jumps (|diff| > 0.6) of each decode so the ceiling is chosen by measurement, not by the 1.25 in a report.

Same decode path as eval/model_matrix_gen.py: model.same.decode(z), truncate, peak-normalise on save.
USAGE  .venv/bin/python eval/decode_z0_clamped.py --z0-dir DIR --out-dir DIR --ceilings 0,1.25,1.0 [--write]
  ceiling 0 = no clamp (the baseline, measured the same way). --write saves wavs under <out-dir>/c<ceiling>/.
ADAPTIVE (--adaptive N): --z0-dir may repeat (first dir that has a clip wins; a clip's name minus any
  "__d48" is the key), and each clip is decoded at the GENTLEST ceiling in --ceilings (order = gentle ->
  strong, 0 first) whose decode has <= N jumps; one wav per clip lands in <out-dir>/final/, and
  decode_adaptive.json records ceiling, jumps and ok (False = no ceiling got it under N: drop the clip).
Run from a directory that is NOT the SAO root (MASTER §5: SAO/torchcodec shadows the real package).
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np  # noqa: E402
import torch  # noqa: E402

sys.path.insert(0, "/home/kim/Projects/SAO/control")
from sa3_control.audio_io import save_audio  # noqa: E402

JUMP = 0.6


def n_jumps(audio):
    """Count of single-sample |diff| > 0.6 on the mono mix of a peak-normalised (1,C,N) clip."""
    y = audio.float().mean(1)[0].numpy()
    return int((np.abs(np.diff(y)) > JUMP).sum())


def decode(model, z, c, dtype, sr, seconds):
    std = float(z.std())
    zz = z * (c / (std + 1e-8)) if (c > 0 and std > c) else z
    with torch.no_grad():
        audio = model.same.decode(zz.to("cuda", dtype))
    audio = audio.float().cpu()[:, :, :int(seconds * sr)]
    return audio / max(float(audio.abs().max()), 1e-8)


def adaptive(a, model, dtype, sr, ceilings):
    clips = {}
    for d in a.z0_dir:
        for zp in sorted(d.glob("*.z0.npy")):
            clips.setdefault(zp.name[:-len(".z0.npy")].replace("__d48", ""), zp)
    if a.only_keys:
        keep = {ln.strip().replace("__d48", "") for ln in a.only_keys.read_text().splitlines() if ln.strip()}
        clips = {k: v for k, v in clips.items() if k in keep}
        print(f"{len(clips)}/{len(keep)} requested clips have a latent", flush=True)
    out = a.out_dir / "final"
    out.mkdir(exist_ok=True)
    rows = []
    for key, zp in clips.items():
        z = torch.from_numpy(np.load(zp).astype(np.float32))
        best = None
        for c in ceilings:
            audio = decode(model, z, c, dtype, sr, a.seconds)
            j = n_jumps(audio)
            if best is None or j < best[1]:
                best = (c, j, audio)
            if j <= a.adaptive:
                break
        c, j, audio = best
        save_audio(str(out / (key + ".wav")), audio[0], sr)
        rec = {"clip": key, "source": str(zp.parent), "std": float(z.std()), "ceiling": c, "jumps": j,
               "ok": j <= a.adaptive}
        rows.append(rec)
        print(json.dumps(rec), flush=True)
    (a.out_dir / "decode_adaptive.json").write_text(json.dumps(rows, indent=1))
    print(f"{len(rows)} clips, ok {sum(r['ok'] for r in rows)}, clamped {sum(r['ceiling'] > 0 for r in rows)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--z0-dir", type=Path, action="append", required=True)
    ap.add_argument("--adaptive", type=int, default=None)
    ap.add_argument("--only-keys", type=Path, default=None, help="text file, one clip key per line (name minus __d48); others are skipped")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--ceilings", default="0,1.25")
    ap.add_argument("--seconds", type=float, default=48.0)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    ceilings = [float(c) for c in a.ceilings.split(",")]
    a.out_dir.mkdir(parents=True, exist_ok=True)

    from stable_audio_3 import StableAudioModel
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    dtype = next(model.same.parameters()).dtype
    sr = model.model.sample_rate

    if a.adaptive is not None:
        return adaptive(a, model, dtype, sr, ceilings)
    rows = []
    for zp in sorted(a.z0_dir[0].glob("*.z0.npy")):
        z = torch.from_numpy(np.load(zp).astype(np.float32))
        std = float(z.std())
        rec = {"clip": zp.name[:-len(".z0.npy")], "std": std}
        for c in ceilings:
            zz = z * (c / (std + 1e-8)) if (c > 0 and std > c) else z
            with torch.no_grad():
                audio = model.same.decode(zz.to("cuda", dtype))
            audio = audio.float().cpu()[:, :, :int(a.seconds * sr)]
            audio = audio / max(float(audio.abs().max()), 1e-8)   # peak-normalise like save_audio(normalize=True)
            rec[f"jumps_c{c:g}"] = n_jumps(audio)
            if a.write:
                d = a.out_dir / f"c{c:g}"
                d.mkdir(exist_ok=True)
                save_audio(str(d / (rec["clip"] + ".wav")), audio[0], sr)
        rows.append(rec)
        print(json.dumps(rec), flush=True)
    (a.out_dir / "decode_clamped.json").write_text(json.dumps(rows, indent=1))
    for c in ceilings:
        k = f"jumps_c{c:g}"
        v = np.array([r[k] for r in rows])
        print(f"ceiling {c:g}: clips>50 jumps {int((v > 50).sum())}, >10 {int((v > 10).sum())}, total {int(v.sum())}")


if __name__ == "__main__":
    main()
