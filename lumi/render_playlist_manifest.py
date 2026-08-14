#!/usr/bin/env python
"""render_playlist_manifest.py — LUMI worker for Kim's 24h T4096 playlist (Dadabots
homage). Reads a shard of eval/build_playlist_manifest.py's 128-entry manifest and
renders each entry with ITS OWN (label, prompt, seed, weight) — a job list, not a grid
(unlike render_matrix_cells.py, which this borrows its load/save logic from verbatim).

Same manifest drives all four stages Kim asked for; only frames/cfg/dist_shift/
pt_medium change between stages, so seeds/prompts/models/weights stay identical and
every stage is a true matched-pair comparison against stage A:
  A: --frames 4096 --steps 50                                  (the playlist itself)
  B: --frames 256 / --frames 1024 --steps 50                   (length/HF comparison)
  C: --frames 4096 --steps 50 --dist-shift-rate 1.0 --subset N (length-adaptive
     schedule ON — model ships with rate=0 hardcoded, LogSNRShift's OWN class default
     is rate=1.0; this is a pure inference-time override, no retraining, confirmed
     2026-08-15 via model.generate()'s documented dist_shift= param)
  D: --frames 4096 --steps 50 --cfg-override 1 --pt-medium     (post-trained model,
     same seeds+weights; entries whose stage-A model was full-FT have no adapter to
     carry over, so those render as PLAIN post-trained medium — flagged per-clip in
     the output mmline.json as "no_adapter_fullft_source": true, not silently merged)

Groups a shard's entries by label before rendering so each of the (up to) 12 distinct
T4096 checkpoints loads ONCE, not once per clip.
"""
import argparse
import json
import time
from pathlib import Path

RUNS = Path("/scratch/project_465003186/runs")
STEPS = 50


def resolve_ckpt(label):
    run_dir = RUNS / label
    ckpts = sorted(
        (p for p in run_dir.glob("epoch=*.ckpt") if not p.name.endswith(".weights.ckpt")),
        key=lambda p: p.stat().st_mtime,
    )
    return ckpts[-1] if ckpts else None


def load_fullft_ema(model, ckpt_path):
    import torch
    ck = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    sd_raw = ck.get("state_dict", ck)
    tgt = model.model.model
    want = set(dict(tgt.named_parameters())) | set(dict(tgt.named_buffers()))
    pfx = "diffusion_ema.ema_model."
    sd = {(k[len(pfx):] if k.startswith(pfx) else k): v for k, v in sd_raw.items()}
    missing, _ = tgt.load_state_dict(
        {k: v.to(next(tgt.parameters()).dtype) for k, v in sd.items() if k in want},
        strict=False)
    cov = 1 - len(missing) / max(1, len(list(tgt.state_dict())))
    assert cov > 0.99, f"{ckpt_path}: EMA fullft ckpt covers only {cov:.1%}"
    del ck, sd_raw, sd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--shard", required=True, help="I/N, e.g. 0/8")
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--cfg-override", type=float, default=None)
    ap.add_argument("--dist-shift-rate", type=float, default=None,
                     help="override LogSNRShift.rate (model default is 0/inert); "
                          "None = use the checkpoint's normal (inert) schedule")
    ap.add_argument("--pt-medium", action="store_true",
                     help="post-trained 'medium' base instead of medium-base; adapters "
                          "from full-FT-sourced manifest entries are DROPPED (no base "
                          "to carry a full-FT delta onto), plain PT-medium instead")
    ap.add_argument("--subset", type=int, default=None,
                     help="only render the first N manifest entries (by idx) — for "
                          "stage C's 64-clip subset")
    ap.add_argument("--stage", required=True, help="A/B/C/D, tags output filenames + mmline")
    a = ap.parse_args()

    entries = json.loads(Path(a.manifest).read_text())
    if a.subset is not None:
        entries = [e for e in entries if e["idx"] < a.subset]
    shard_i, shard_n = (int(x) for x in a.shard.split("/"))
    mine = [e for e in entries if e["idx"] % shard_n == shard_i]
    mine.sort(key=lambda e: e["label"])  # group by label -> one load per distinct model
    print(f"[playlist shard {a.shard}] {len(mine)}/{len(entries)} entries, "
          f"{len(set(e['label'] for e in mine))} distinct labels", flush=True)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    import numpy as np
    import torch
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel
    from stable_audio_3.inference.distribution_shift import LogSNRShift

    dist_shift = (LogSNRShift(anchor_length=2000, anchor_logsnr=-6.2,
                               rate=a.dist_shift_rate, logsnr_end=2.0)
                  if a.dist_shift_rate is not None else None)

    duration = round(a.frames / (44100 / 4096), 2)
    sample_size = a.frames * 4096

    current_label = None
    model = None
    model_for_label_missing = False
    for e in mine:
        label, is_fullft = e["label"], e["is_fullft"]
        pt_medium = a.pt_medium
        skip_adapter = pt_medium and is_fullft  # stage D: no full-FT delta to carry over

        model_key = ("PT" if pt_medium else "base", None if skip_adapter else label)
        if model_key != current_label:
            if model is not None:
                del model
                torch.cuda.empty_cache()
            t0 = time.time()
            model = StableAudioModel.from_pretrained(
                "medium" if pt_medium else "medium-base", device="cuda")
            if not skip_adapter:
                ckpt = resolve_ckpt(label)
                if ckpt is None:
                    print(f"[playlist] SKIP label={label}: no checkpoint in {RUNS/label}", flush=True)
                    current_label = model_key
                    model_for_label_missing = True
                    continue
                if is_fullft:
                    load_fullft_ema(model, ckpt)
                else:
                    model.load_lora([str(ckpt)])
            current_label = model_key
            model_for_label_missing = False
            print(f"[playlist] loaded {model_key} ({'no-adapter PT' if skip_adapter else label}) "
                  f"in {time.time()-t0:.0f}s", flush=True)
        if model_for_label_missing:
            continue

        if not is_fullft and not skip_adapter:
            try:
                model.set_lora_strength(e["weight"])
            except Exception:
                pass

        cfg = a.cfg_override if a.cfg_override is not None else e["cfg"]
        tag = f"stage{a.stage}_idx{e['idx']:03d}"
        wav_path = out / f"{tag}__{label}__cfg{int(cfg)}__w{int(round(e['weight']*100)):03d}__s{e['seed']}.wav"
        if wav_path.exists():
            print(f"[playlist] skip existing {wav_path.name}", flush=True)
            continue

        t0 = time.time()
        gen_kwargs = dict(prompt=e["prompt"], duration=duration, steps=STEPS,
                           cfg_scale=float(cfg), seed=int(e["seed"]), batch_size=1,
                           sample_size=sample_size, return_latents=True)
        if dist_shift is not None:
            gen_kwargs["dist_shift"] = dist_shift
        z0 = model.generate(**gen_kwargs)
        decode_dtype = next(model.same.parameters()).dtype
        with torch.no_grad():
            audio = model.same.decode(z0.to(decode_dtype))
        sr = model.model.sample_rate
        audio = audio.to(torch.float32)[:, :, :int(duration * sr)]
        np.save(wav_path.with_suffix(".z0.npy"), z0.detach().to(torch.float16).cpu().numpy())
        save_audio(wav_path, audio[0].cpu(), sr, normalize=True)
        wav_path.with_suffix(".mmline.json").write_text(json.dumps({
            "stage": a.stage, "idx": e["idx"], "label": label, "corpus": e["corpus"],
            "is_fullft": is_fullft, "no_adapter_fullft_source": skip_adapter,
            "pt_medium": pt_medium, "prompt": e["prompt"], "track": e["track"],
            "seed": e["seed"], "cfg": cfg, "weight": e["weight"], "steps": STEPS,
            "frames": a.frames, "duration": duration,
            "dist_shift_rate": a.dist_shift_rate,
            "file": wav_path.name.replace(".wav", ".m4a"),
        }))
        print(f"  [{tag} {label} {duration}s] {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
