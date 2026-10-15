#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-16)
"""dronesweep_rescale_decode.py -- does scaling the runaway latents of force_scalar back to a healthy level rescue them?

WHY (listening + measurement 2026-10-16): the AVP drone sweep's force_scalar arms (fullft, EMA renders, ep7) have a final latent std
of ~3 at every cfg, including cfg 1 (healthy SA3 ~1.0-1.15), i.e. the fine-tuned model itself runs the latent level away. Asked:
"could we ... just scale down the latents uniformly 3x?". This decodes the EXISTING force_scalar latents (no re-render, CPU only)
two ways: each latent rescaled to std 1.1, and all divided by 3. If the content is still musical underneath, this is cheap; if it
drifted off-manifold, it will be a quieter drone (then the in-sampler anchor or a base blend is the route).
Set: force_scalar_s1 + _s2, ep7, cfg 7, prompts kl_0/kl_1/kl_2/housestyle/kimlong/rb_common_0 (12 latents x 2 variants).
Output: Mantu/sa3_control_runs/dronesweep_rescale_20261016/. RUN: SAO/.venv/bin/python eval/dronesweep_rescale_decode.py
"""
import glob
import json
import os
import re
import sys

import numpy as np

SRC = "/home/kim/Projects/SAO/renders_pull/dronesweep"
OUT = "/run/media/kim/Mantu/sa3_control_runs/dronesweep_rescale_20261016"
PROMPTS = ("kl_0", "kl_1", "kl_2", "housestyle", "kimlong", "rb_common_0")
TARGET_STD = 1.1


def main():
    import torch
    import soundfile as sf
    torch.set_num_threads(8)
    from stable_audio_3.model import AutoencoderModel
    os.makedirs(OUT, exist_ok=True)
    files = []
    for arm in ("force_scalar_s1", "force_scalar_s2"):
        for p in PROMPTS:
            files += sorted(glob.glob(f"{SRC}/dronesweep_{arm}__ep7__cfg7__w100__{p}__s*.z0.npy"))
    print(f"[rescale] {len(files)} latents", flush=True)
    ae = AutoencoderModel.from_pretrained("same-l", device="cpu")
    sr = ae.sample_rate
    rows = []
    for f in files:
        z = np.load(f).astype(np.float32)
        std = float(z.astype(np.float64).std())
        base = os.path.basename(f)[:-len(".z0.npy")]
        for tag, k in (("norm1.1", TARGET_STD / std), ("div3", 1 / 3)):
            dst = f"{OUT}/{base}__{tag}.wav"
            if not os.path.exists(dst):
                with torch.no_grad():
                    x = ae.decode(torch.from_numpy(z * k)).float()
                x = x[0].cpu().numpy() if x.ndim == 3 else x.cpu().numpy()
                pk = float(np.abs(x).max()) or 1e-9
                sf.write(dst, (x / pk * 0.8913 if pk > 1 else x).T, sr)
            rows.append({"src": base, "variant": tag, "scale": round(k, 4), "z_std_in": round(std, 3), "z_std_out": round(std * k, 3),
                         "file": os.path.basename(dst), "orig_wav": f"{base}.wav"})
            print(f"  {base} {tag} (x{k:.3f})", flush=True)
    json.dump({"purpose": __doc__.split("Output:")[0].strip(), "source": SRC, "rows": rows, "kim_feedback": None},
              open(f"{OUT}/run_meta.json", "w"), indent=1)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
