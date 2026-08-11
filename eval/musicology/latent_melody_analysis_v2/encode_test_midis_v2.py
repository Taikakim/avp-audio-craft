#!/usr/bin/env python
"""encode_test_midis_v2.py -- SAME-encode the v2 melody-battery renders (~900 wavs).

Same pretransform-only pattern as v1 (../latent_melody_analysis/encode_test_midis.py):
medium-base pretransform, fp16, no DiT / no T5-Gemma. Batches same-length wavs
(batch<=8) so the whole set encodes in one short GPU-lock window.

Output: eval/musicology/test_midis_v2/latents/<render-stem>.z0.npy (fp16, [256, T]).
Caller holds /home/kim/Projects/SAO/.gpu.lock around this script.
"""
import os
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

RENDERS = Path("/home/kim/Projects/SAO/eval/musicology/test_midis_v2/renders")
OUT = Path("/home/kim/Projects/SAO/eval/musicology/test_midis_v2/latents")
OUT.mkdir(parents=True, exist_ok=True)
BATCH = 8


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

    # pad ALL files to one global length -> uniform batches (trailing silence is
    # harmless: the conv encoder is local and analysis crops to manifest frames)
    nmax = max(sf.info(w).frames for w in wavs)
    npad_g = nmax + (ds - nmax % ds) % ds
    groups = {npad_g: todo}

    t_all = time.time()
    done = 0
    for npad, files in sorted(groups.items()):
        for i in range(0, len(files), BATCH):
            chunk = files[i:i + BATCH]
            xs = []
            for w in chunk:
                y, in_sr = sf.read(w, dtype="float32", always_2d=True)
                assert in_sr == sr, f"{w.name}: sr {in_sr} != {sr}"
                x = torch.from_numpy(y.T)
                if x.shape[0] == 1:
                    x = x.repeat(2, 1)
                pad = npad - x.shape[-1]
                if pad:
                    x = torch.nn.functional.pad(x, (0, pad))
                xs.append(x)
            xb = torch.stack(xs).cuda().half()
            try:
                with torch.no_grad():
                    zb = pt.encode(xb)  # [B, 256, T]
                for w, z in zip(chunk, zb):
                    np.save(OUT / f"{w.stem}.z0.npy", z.float().cpu().numpy().astype(np.float16))
            except torch.cuda.OutOfMemoryError:
                print("[oom] falling back to per-file", flush=True)
                del xb
                torch.cuda.empty_cache()
                for w, x in zip(chunk, xs):
                    with torch.no_grad():
                        z = pt.encode(x.unsqueeze(0).cuda().half())[0]
                    np.save(OUT / f"{w.stem}.z0.npy", z.float().cpu().numpy().astype(np.float16))
            done += len(chunk)
            print(f"[ok] {done}/{len(todo)} (len {npad}) {time.time()-t_all:.0f}s", flush=True)

    print(f"[encode] done in {time.time()-t_all:.0f}s", flush=True)


if __name__ == "__main__":
    main()
