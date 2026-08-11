#!/usr/bin/env python
"""encode_test_midis.py -- Phase G of the latent-melody-encoding analysis.

SAME-encode the 65 controlled synthetic renders (eval/musicology/test_midis/renders/*.wav,
13 MIDIs x 5 timbres, frame-locked at BPM 161.499 so 1 sixteenth == 1 latent frame) to
z0 latents for the melody-encoding study (where/how-linearly pitch lives in the SAME space).

Pretransform-only load (no DiT / no T5-Gemma), same pattern as lumi/muscriptor_decode_task.py.
Output: eval/musicology/test_midis/latents/<render-stem>.z0.npy  (fp16, [256, T])

GPU use is a single short batch (~2-4 min); caller holds SAO/.gpu.lock around this script.
"""
import os
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"
import json
import time
from pathlib import Path

import numpy as np

RENDERS = Path("/home/kim/Projects/SAO/eval/musicology/test_midis/renders")
OUT = Path("/home/kim/Projects/SAO/eval/musicology/test_midis/latents")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    import torch
    import soundfile as sf
    from safetensors.torch import load_file
    from stable_audio_3.model_configs import all_models
    from stable_audio_3.factory import create_pretransform_from_config
    from stable_audio_3.loading_utils import copy_state_dict

    wavs = sorted(RENDERS.glob("*.wav"))
    todo = [w for w in wavs if not (OUT / f"{w.stem}.z0.npy").exists()]
    print(f"[encode] {len(todo)}/{len(wavs)} to do", flush=True)
    if not todo:
        return

    cfg_path, ckpt_path = all_models["medium-base"].resolve()
    _cfg = json.load(open(cfg_path))
    sr = _cfg["sample_rate"]
    pt = create_pretransform_from_config(_cfg.get("model", _cfg), sr).to("cuda").half().eval().requires_grad_(False)
    _sd = load_file(ckpt_path)
    copy_state_dict(pt, {k[len("pretransform."):]: v for k, v in _sd.items() if k.startswith("pretransform.")})
    ds = int(pt.downsampling_ratio)
    print(f"[encode] pretransform up: sr={sr} ds={ds}", flush=True)

    for w in todo:
        t0 = time.time()
        y, in_sr = sf.read(w, dtype="float32", always_2d=True)  # [N, C]
        assert in_sr == sr, f"{w.name}: sr {in_sr} != {sr}"
        x = torch.from_numpy(y.T)  # [C, N]
        if x.shape[0] == 1:
            x = x.repeat(2, 1)
        n = x.shape[-1]
        pad = (ds - n % ds) % ds
        if pad:
            x = torch.nn.functional.pad(x, (0, pad))
        x = x.unsqueeze(0).cuda().half()
        with torch.no_grad():
            z = pt.encode(x)  # [1, 256, T]
        z = z[0].float().cpu().numpy().astype(np.float16)
        np.save(OUT / f"{w.stem}.z0.npy", z)
        print(f"[ok] {w.stem} z={z.shape} {time.time()-t0:.1f}s", flush=True)

    print("[encode] done", flush=True)


if __name__ == "__main__":
    main()
