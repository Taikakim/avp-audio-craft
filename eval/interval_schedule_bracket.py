#!/usr/bin/env python
"""interval_schedule_bracket.py -- Kim's overnight ask (2026-07-12/13, via CONTINUITY,
"THE BIG ONE"): DoRA sigma-interval x cfg x weight bracket sweep on the two most recent
r128 checkpoints. Kim specified the interval bracket in STEP-COUNT FRACTIONS (0=start of
generation/high-noise, 1=end/clean); the DiT interval mechanism is SIGMA-native
(dit.py:466, checked as interval[0] <= sigma <= interval[1] every step). Converts via
sampling.build_schedule() -- the EXACT function generate() uses internally -- so the sigma
values match what actually happens at inference, not an approximation.

sigmas = build_schedule(steps, dist_shift=model.sampling_dist_shift, ...) is seq_len-
INVARIANT here (LogSNRShift default has rate=0), verified empirically before writing this.
bound(frac) = sigmas[round(frac * steps)]. interval=(sigma_at_end_frac, sigma_at_start_frac)
since sigma decreases monotonically as step-fraction increases, and the interval tuple
needs (lo, hi).

Writes into the SAME model_matrix manifest.jsonl (WINTERMUTE's schema) so cells land on
the existing model_matrix.html with zero GUI changes -- each interval combo becomes its
own "ckpt" dropdown entry (e.g. "ep10_iv0.0-1.0"), cfg/strength(=weight) stay native axes.
Extra fields (interval_frac, interval_sigma) record BOTH domains per Kim's ask, ignored
by the existing GUI JS.

Run (SA3 venv):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/interval_schedule_bracket.py [--dry-run] [--only goa|avp]
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = Path.home() / ".cache/evals_aac/model_matrix"
MANIFEST = STAGING / "manifest.jsonl"
RENDER_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix")

STEPS = 24
DURATION = 20.0
INTERVAL_STARTS = (0.0, 0.1, 0.2, 0.3, 0.4)
INTERVAL_ENDS = (1.0, 0.9, 0.8, 0.7, 0.6)
WEIGHTS = (1.0, 1.5, 2.0)
CFGS = (7.0, 15.0, 24.0)

# 2-prompt subset (Kim: keep it small so the night fits) -- one rarity-band prompt,
# one kimlong-style detailed prompt, matching the established model_matrix convention.
PROMPTS = [
    {"id": "rb_bracket_0", "text": "2020s goa trance, melodic mood, 148 bpm", "seed": 1102008041},
    {"id": "kl_bracket_0", "text": ("This track is a high-energy Psytrance piece that blends driving "
                                     "trance rhythms with the hypnotic, acid-inflected textures typical "
                                     "of the genre."), "seed": 1000},
]

MODELS = {
    "goa": {
        "label": "dora128_47s_cont_from5",
        "ckpt": Path("/home/kim/Projects/sa3_local_runs/dora128_47s_cont_from5/epoch=4-step=6750.ckpt"),
        "ckpt_tag": "ep10",  # lineage total epoch (continuation ep4 of 5, + newcaptions_5ep's 5)
    },
    "avp": {
        "label": "dora128adj_avp_aug10_lr1e4",
        "ckpt": Path("/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_aug10_lr1e4/epoch=74-step=3000.ckpt"),
        "ckpt_tag": "ep74",
    },
}


def clip_name(label, ckpt_tag, cfg, weight, start_frac, end_frac, pid, seed):
    return (f"{label}__{ckpt_tag}_iv{start_frac:.1f}-{end_frac:.1f}__cfg{int(cfg)}"
            f"__w{int(round(weight * 100)):03d}__{pid}__s{seed}.wav")


def manifest_key(e):
    return f'{e["model"]}|{e["ckpt"]}|{e["cfg"]}|{e["strength"]}|{e["prompt_id"]}'


def load_existing_keys():
    if not MANIFEST.exists():
        return set()
    keys = set()
    for ln in MANIFEST.read_text().splitlines():
        try:
            keys.add(manifest_key(json.loads(ln)))
        except Exception:
            pass
    return keys


def append_manifest(entry):
    STAGING.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "a") as f:
        f.write(json.dumps(entry) + "\n")


def transcode(wav_path, m4a_path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                    "-c:a", "aac", "-b:a", "192k", str(m4a_path)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=["goa", "avp"], default=None)
    args = ap.parse_args()

    models = {args.only: MODELS[args.only]} if args.only else MODELS

    n_cells = len(models) * len(INTERVAL_STARTS) * len(INTERVAL_ENDS) * len(WEIGHTS) * len(CFGS) * len(PROMPTS)
    print(f"[bracket] {len(models)} model(s) x {len(INTERVAL_STARTS)}x{len(INTERVAL_ENDS)} intervals "
          f"x {len(WEIGHTS)} weights x {len(CFGS)} cfgs x {len(PROMPTS)} prompts -> {n_cells} renders")
    if args.dry_run:
        return

    existing = load_existing_keys()
    print(f"[bracket] {len(existing)} cells already in matrix manifest, resuming")

    import torch  # noqa: E402
    sys.path.insert(0, str(ROOT / "control"))
    from sa3_control.audio_io import save_audio          # noqa: E402
    from stable_audio_3 import StableAudioModel           # noqa: E402
    from stable_audio_3.inference.sampling import build_schedule  # noqa: E402

    RENDER_DIR.mkdir(parents=True, exist_ok=True)

    for key, spec in models.items():
        model = StableAudioModel.from_pretrained("medium-base", device="cuda")
        sr = model.model.sample_rate
        model.load_lora([str(spec["ckpt"])])
        real_shift = model.model.sampling_dist_shift
        real_sigmas = build_schedule(STEPS, dist_shift=real_shift, effective_seq_len=2048, device="cpu")
        print(f"[load] {spec['label']}/{spec['ckpt_tag']} -- sigmas[0]={real_sigmas[0]:.4f} "
              f"sigmas[-1]={real_sigmas[-1]:.4f}", flush=True)

        for start_frac in INTERVAL_STARTS:
            for end_frac in INTERVAL_ENDS:
                sigma_hi = float(real_sigmas[round(start_frac * STEPS)])   # early/noisy -> high sigma
                sigma_lo = float(real_sigmas[round(end_frac * STEPS)])     # late/clean -> low sigma
                ckpt_tag = f"{spec['ckpt_tag']}_iv{start_frac:.1f}-{end_frac:.1f}"
                for weight in WEIGHTS:
                    for cfg in CFGS:
                        for prompt in PROMPTS:
                            key_str = f'{spec["label"]}|{ckpt_tag}|{cfg}|{weight}|{prompt["id"]}'
                            wav_name = clip_name(spec["label"], spec["ckpt_tag"], cfg, weight,
                                                  start_frac, end_frac, prompt["id"], prompt["seed"])
                            m4a_name = wav_name.replace(".wav", ".m4a")
                            if key_str in existing:
                                continue
                            try:
                                model.set_lora_strength(weight)
                            except Exception:
                                pass
                            wav_path = RENDER_DIR / wav_name
                            if not wav_path.exists():
                                t0 = time.time()
                                out = model.generate(
                                    prompt=prompt["text"], duration=DURATION, steps=STEPS,
                                    cfg_scale=float(cfg), seed=int(prompt["seed"]), batch_size=1,
                                    lora_configs=[{"lora_index": 0, "interval": (sigma_lo, sigma_hi)}],
                                )
                                save_audio(wav_path, out[0].float().cpu(), sr, normalize=True)
                                print(f"  [{spec['label']}/{ckpt_tag} cfg{cfg} w{weight} {prompt['id']}] "
                                      f"{time.time() - t0:5.1f}s", flush=True)
                            m4a_path = RENDER_DIR / m4a_name
                            if not m4a_path.exists():
                                transcode(wav_path, m4a_path)
                            append_manifest({
                                "model": spec["label"], "ckpt": ckpt_tag, "cfg": cfg, "strength": weight,
                                "prompt_id": prompt["id"], "prompt_text": prompt["text"],
                                "seed": prompt["seed"], "file": m4a_name,
                                "interval_frac": [start_frac, end_frac],
                                "interval_sigma": [round(sigma_lo, 4), round(sigma_hi, 4)],
                            })
                            existing.add(key_str)
        del model
        torch.cuda.empty_cache()
    print("[bracket] done", flush=True)


if __name__ == "__main__":
    main()
