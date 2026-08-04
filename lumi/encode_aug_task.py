#!/usr/bin/env python
"""encode_aug_task.py -- single-GCD worker: SAME-encode augmented GOA FLAC crops to
latents (aug8 campaign, docs/superpowers/specs/2026-07-23-aug8-15ep-campaign.md).

Pattern reused from lumi/muscriptor_decode_task.py (decoder-only loading, offline
HF_HOME, per-process MIOpen /tmp redirect) but for ENCODE, and via the plain public
`AutoencoderModel.from_pretrained("same-l", ...)` path (stable-audio-3/scripts/
pre_encode_dataset.py's own loading convention) rather than muscriptor's from-medium-
base pretransform extraction -- same-l is already a standalone checkpoint, so there is
no DiT/conditioner to dodge and no reason to hand-assemble the pretransform.

Input: FLAC crops produced by lumi/augment_goa_bungee.py (already duration-matched to
their parent GOA crop -- see that script's docstring) + its manifest.jsonl (crop_id,
variant, semitones, speed, prompt, source_bpm per row). Per id in --shard: load FLAC,
encode with the SAME-L autoencoder, save <crop_id>__<variant>.npy (latent) +
<crop_id>__<variant>.json (metadata for train_lora.py --encoded_dir). Resumable
(skips existing .npy).

Metadata dict is DELIBERATELY MINIMAL for augmentation variants -- mirrors GHOST-NOTE's
avp augmentation-encode call (WORKLOG 2026-07-06): audio-domain scalar features computed
on the ORIGINAL crop (onset_density, spectral_*, harmonic_*, ...) describe the UNSHIFTED
source and would be actively wrong on a pitch/tempo-shifted variant, so they are NOT
copied forward. `prompt` and `source_bpm` ARE inherited (caption + BPM-family info
stays valid; `augmented_bpm` records the actual post-stretch value for tempo/combined
variants). This mirrors the same "Phase D open question" the avp encode left open --
not re-litigated here.
"""
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

# Force the HF cache to the one that actually holds SAME-L, offline -- same rationale
# as muscriptor_decode_task.py (belt-and-suspenders against a stale sbatch HF_HOME).
_LUMI_MODELS = "/project/project_465003186/models"
if os.path.isdir(_LUMI_MODELS):
    os.environ["HF_HOME"] = _LUMI_MODELS
    os.environ["HF_HUB_OFFLINE"] = "1"
    import tempfile
    _mio = os.path.join(tempfile.gettempdir(), f"miopen-{os.getpid()}")
    os.makedirs(_mio, exist_ok=True)
    os.environ["MIOPEN_USER_DB_PATH"] = _mio
    os.environ["MIOPEN_CUSTOM_CACHE_DIR"] = _mio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", required=True, help="text file, one crop_id__variant per line")
    ap.add_argument("--flac-dir", required=True, help="dir of <crop_id>__<variant>.flac (augment_goa_bungee.py --out)")
    ap.add_argument("--manifest", required=True, help="manifest.jsonl from augment_goa_bungee.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="same-l")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    ids = [l.strip() for l in open(a.shard) if l.strip()]
    todo = [i for i in ids if not (out / f"{i}.npy").exists()]
    print(f"[encode-aug] shard {Path(a.shard).name}: {len(todo)}/{len(ids)} to do", flush=True)
    if not todo:
        return

    # crop_id__variant -> manifest row (prompt/bpm/speed/semitones/source info)
    manifest = {}
    with open(a.manifest) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("status") not in ("ok", "skipped-exists"):
                continue
            key = f"{row['crop_id']}__{row['variant']}"
            manifest[key] = row

    import torch
    import soundfile as sf
    from stable_audio_3 import AutoencoderModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ae = AutoencoderModel.from_pretrained(a.model, device=device)

    for cid in todo:
        t0 = time.time()
        row = manifest.get(cid)
        flac_path = Path(a.flac_dir) / f"{cid}.flac"
        if row is None or not flac_path.exists():
            print(f"[SKIP] {cid} (no manifest row or missing flac)", flush=True)
            continue
        try:
            audio, sr = sf.read(str(flac_path), dtype="float32", always_2d=True)  # [T, C]
            x = torch.from_numpy(audio.T).unsqueeze(0).to(device)  # [1, C, T]
            if x.shape[1] == 1:
                x = x.repeat(1, 2, 1)  # mono source -> stereo, matches ae.encode's force_channels
            with torch.no_grad():
                latent = ae.encode(x, sr)
            latent_np = latent[0].cpu().numpy()
            np.save(out / f"{cid}.npy", latent_np)

            source_bpm = row.get("source_bpm")
            speed = row.get("speed", 1.0)
            meta = {
                "crop_id": row["crop_id"],
                "variant": row["variant"],
                "semitones": row.get("semitones"),
                "speed": speed,
                "is_augmentation": True,
                "augment_engine": "bungee",
                "prompt": row.get("prompt"),
                "source_bpm": source_bpm,
                "augmented_bpm": None if source_bpm is None else round(source_bpm * speed, 3),
                "source_path": row.get("source_path"),
                "sample_rate": sr,
            }
            (out / f"{cid}.json").write_text(json.dumps(meta))
            print(f"[ok] {cid} latent={latent_np.shape} {time.time()-t0:.1f}s", flush=True)
        except Exception as e:
            print(f"[FAIL] {cid} {type(e).__name__}: {str(e)[:160]}", flush=True)


if __name__ == "__main__":
    main()
