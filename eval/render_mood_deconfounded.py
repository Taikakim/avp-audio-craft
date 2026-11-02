#!/usr/bin/env python3
"""render_mood_deconfounded.py -- Conditional De-Confounding (Gaussian Kriging +
Library-Floor Repulsion) test on the canonical fine-grained matrix prompt:
  PROMPT = "2020s goa trance, melodic mood, 148 bpm", SEED = 1102008041, CFG = 7.0

Compares naive sparse 3-tag targets against 56-dim Conditionally De-Confounded targets
derived from the 5,400 Goa mood crops (/run/media/kim/Mantu/latents_sa3_mood/*.npy)
after regressing out the 2-PC MTG-Jamendo stock/library common-mode confound.

Targets rendered across g in [1024, 2048, 4096, 8192] on Base, AdamW ep5, Goa LoRA ep63,
and Combo Fusion+Goa (50/50):
  1. Deconf_Melodic   : {"melodic": 3.5}
  2. Deconf_Space     : {"space": 3.5}
  3. Deconf_Dark      : {"dark": 3.5}
  4. Deconf_Uplifting : {"uplifting": 3.5, "happy": 2.5, "melodic": 1.5}
  5. Deconf_AntiDark  : {"melodic": 2.5, "uplifting": 2.5, "energetic": 2.0, "dark": -3.5, "slow": -2.5}
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import sys, time, json, glob, subprocess, argparse
from pathlib import Path
import numpy as np
import torch
import torch.nn.utils.parametrize as P

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stable-audio-3"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "control"))

from stable_audio_3 import StableAudioModel
from sa3_control.audio_io import save_audio

HEAD_CKPT = "/run/media/kim/Mantu/latch_sweep/mood_56d_best_40ep_20261031/C3_mood_lr8e-4_b64_cos40/latch_sa3_effnet_moodtheme_ep40.pt"
MOOD_NPY_DIR = Path("/run/media/kim/Mantu/latents_sa3_mood")
METADATA_JSON = Path("/home/kim/Projects/mir/models/essentia/mtg_jamendo_moodtheme-discogs-effnet-1.json")

OUT_WAV_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/mood_finegrained_20261031")
OUT_AAC_DIR = Path("/home/kim/evals_aac/mood_finegrained")
OUT_WAV_DIR.mkdir(parents=True, exist_ok=True)
OUT_AAC_DIR.mkdir(parents=True, exist_ok=True)
DECONF_CACHE_JSON = OUT_AAC_DIR / "deconf_targets.json"

LATENT_FRAMES = 280
DURATION = 20.0
STEPS = 24
SAMPLE_RATE = 44100
PROMPT = "2020s goa trance, melodic mood, 148 bpm"
SEED = 1102008041
CFG = 7.0

CKPT_ADAMW = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/adamw_bf16_sweep/adamw_avp_t512_bs4_lr5e5/epoch=9-step=5980.ckpt"
CKPT_FUSION = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/dorlor_ab/dorlor_avpaug_lora_fusion_r128a45_t256_bf16_bs128_s2/epoch=159-step=2880.weights.ckpt"
CKPT_GOA = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/dorlor_ab/dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s1/epoch=63-step=2688.weights.ckpt"

MODELS = [
    {
        "id": "base",
        "name": "Medium Base",
        "type": "base",
        "loras": []
    },
    {
        "id": "adamw",
        "name": "AdamW ep5",
        "type": "lora",
        "loras": [(CKPT_ADAMW, 1.0)]
    },
    {
        "id": "goa",
        "name": "Goa LoRA r128 ep63",
        "type": "lora",
        "loras": [(CKPT_GOA, 1.0)]
    },
    {
        "id": "combo_fusion_goa",
        "name": "Combo: Fusion + Goa (50/50)",
        "type": "lora",
        "loras": [(CKPT_FUSION, 0.5), (CKPT_GOA, 0.5)]
    },
]

LIB_TAGS = [
    "advertising", "commercial", "corporate", "background", "documentary",
    "movie", "trailer", "game", "sport", "christmas"
]

MUS_TAGS = [
    "melodic", "energetic", "space", "retro", "dark", "dream", "relaxing",
    "meditative", "calm", "soundscape", "film", "epic", "deep", "uplifting",
    "happy", "party", "positive", "upbeat", "groovy", "cool", "heavy",
    "powerful", "fast", "slow", "sad", "melancholic", "emotional"
]

SPECS = {
    "Deconf_Melodic": {"melodic": 3.5},
    "Deconf_Space": {"space": 3.5},
    "Deconf_Dark": {"dark": 3.5},
    "Deconf_Uplifting": {"uplifting": 3.5, "happy": 2.5, "melodic": 1.5},
    "Deconf_AntiDark": {"melodic": 2.5, "uplifting": 2.5, "energetic": 2.0, "dark": -3.5, "slow": -2.5},
}


def compute_or_load_deconf_targets() -> dict:
    with open(METADATA_JSON, "r") as f:
        classes = json.load(f)["classes"]

    if DECONF_CACHE_JSON.exists():
        with open(DECONF_CACHE_JSON, "r") as f:
            cached = json.load(f)
        if all(k in cached.get("targets", {}) for k in SPECS):
            print(f"Loaded cached de-confounded targets from {DECONF_CACHE_JSON}")
            out = {}
            for k in SPECS:
                vec = np.array(cached["targets"][k]["vector"], dtype=np.float32)
                out[k] = np.repeat(vec[:, None], LATENT_FRAMES, axis=1)
            return out

    print(f"Computing de-confounded covariance & Kriging targets over {MOOD_NPY_DIR} ...")
    files = sorted(glob.glob(str(MOOD_NPY_DIR / "*.npy")))
    means = []
    for p in files:
        arr = np.load(p, mmap_mode="r")
        means.append(arr.mean(axis=1))
    P_mat = np.clip(np.array(means, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    Z_mat = np.log(P_mat / (1.0 - P_mat))  # (5400, 56)

    lib_idx = [classes.index(c) for c in LIB_TAGS]
    mus_idx = [classes.index(c) for c in MUS_TAGS]

    # 1. Extract top 2 PCs of the 10 dead library tags (common-mode confound)
    Z_lib = Z_mat[:, lib_idx]
    Z_lib_std = (Z_lib - Z_lib.mean(axis=0)) / Z_lib.std(axis=0)
    U_l, S_l, Vt_l = np.linalg.svd(Z_lib_std, full_matrices=False)
    F_lib = U_l[:, :2] * S_l[:2]  # (N, 2)

    # 2. Regress out F_lib from the 27 musical tags in logit space
    Z_mus = Z_mat[:, mus_idx]
    mu_mus = Z_mus.mean(axis=0)
    sd_mus = Z_mus.std(axis=0)
    U_mus = (Z_mus - mu_mus) / sd_mus

    X_conf = np.column_stack([np.ones(len(F_lib)), F_lib])
    Beta = np.linalg.lstsq(X_conf, U_mus, rcond=None)[0]
    U_deconf = U_mus - X_conf @ Beta
    sd_deconf = U_deconf.std(axis=0)
    U_deconf_std = U_deconf / sd_deconf

    # De-confounded 27x27 covariance matrix
    Sigma = np.cov(U_deconf_std, rowvar=False)

    # Clean Goa baseline probabilities (top 40% cleanest Goa tracks with lowest library floor)
    clean_mask = (-F_lib[:, 0]) > np.quantile(-F_lib[:, 0], 0.60)
    p_goa_base = P_mat[clean_mask].mean(axis=0)
    z_goa_base = np.log(p_goa_base / (1.0 - p_goa_base))

    cache_payload = {
        "classes": classes,
        "p_goa_base": [round(float(x), 6) for x in p_goa_base],
        "targets": {}
    }
    out_targets = {}

    for tgt_name, spec_dict in SPECS.items():
        S_indices = [MUS_TAGS.index(k) for k in spec_dict.keys()]
        u_S = np.array([spec_dict[k] for k in spec_dict.keys()], dtype=np.float64)

        Sigma_SS = Sigma[np.ix_(S_indices, S_indices)] + 0.15 * np.eye(len(S_indices))
        Sigma_MS = Sigma[:, S_indices]
        delta_u_M = Sigma_MS @ np.linalg.solve(Sigma_SS, u_S)

        vec_56 = np.zeros(56, dtype=np.float32)
        for m_i, c_idx in enumerate(mus_idx):
            du = float(delta_u_M[m_i])
            if du >= 0.0:
                z_val = z_goa_base[c_idx] + du * sd_mus[m_i]
                p_val = 1.0 / (1.0 + np.exp(-z_val))
                vec_56[c_idx] = float(p_val)
            else:
                # Active cosine repulsion for conditionally opposed anti-moods
                vec_56[c_idx] = float(0.35 * (du / 3.0))

        # Active repulsion on the 10 dead library tags
        for c_idx in lib_idx:
            vec_56[c_idx] = -0.15

        pos_idx = np.argsort(vec_56)[::-1][:7]
        neg_idx = np.argsort(vec_56)[:6]
        pos_summary = [(classes[i], round(float(vec_56[i]), 4)) for i in pos_idx if vec_56[i] > 0.02]
        neg_summary = [(classes[i], round(float(vec_56[i]), 4)) for i in neg_idx if vec_56[i] < -0.02]
        print(f"  [{tgt_name}] spec={spec_dict}")
        print(f"    (+) Top positive: {pos_summary}")
        print(f"    (-) Top negative: {neg_summary}")

        cache_payload["targets"][tgt_name] = {
            "spec": spec_dict,
            "vector": [round(float(x), 6) for x in vec_56],
            "top_pos": pos_summary,
            "top_neg": neg_summary,
        }
        out_targets[tgt_name] = np.repeat(vec_56[:, None], LATENT_FRAMES, axis=1)

    with open(DECONF_CACHE_JSON, "w") as f:
        json.dump(cache_payload, f, indent=2)
    print(f"Saved de-confounded targets to {DECONF_CACHE_JSON}")
    return out_targets


def transcode_to_aac(wav_path: Path, aac_path: Path):
    if aac_path.exists() and aac_path.stat().st_size > 0:
        return
    cmd = [
        "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
        "-i", str(wav_path),
        "-c:a", "aac", "-b:a", "256k",
        str(aac_path)
    ]
    subprocess.run(cmd, check=True)


def merge_adapters(wrapper) -> int:
    n = 0
    for mod in list(wrapper.model.modules()) + list(wrapper.conditioner.modules()):
        if P.is_parametrized(mod):
            for name in list(mod.parametrizations.keys()):
                with torch.no_grad():
                    P.remove_parametrizations(mod, name, leave_parametrized=True)
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--models", default="all", help="Comma-separated model IDs or 'all'")
    args = ap.parse_args()

    active_models = MODELS
    if args.models != "all":
        selected_ids = [s.strip() for s in args.models.split(",")]
        active_models = [m for m in MODELS if m["id"] in selected_ids]

    targets = compute_or_load_deconf_targets()
    weights = [1024.0, 2048.0, 4096.0, 8192.0]

    conditions = []
    for tgt_name, tgt_arr in targets.items():
        for w in weights:
            conditions.append((f"{tgt_name}_g{int(w)}", tgt_arr, w))

    print(f"Total model configurations: {len(active_models)}")
    print(f"Total conditions per model: {len(conditions)} (5 deconf targets x 4 weights)")
    print(f"Grand total renders: {len(active_models) * len(conditions)}")

    task_idx = 0
    total_renders = len(active_models) * len(conditions)

    for m_cfg in active_models:
        m_id = m_cfg["id"]
        m_name = m_cfg["name"]

        print(f"\n=======================================================")
        print(f"[{m_id}] {m_name}")
        print(f"=======================================================")

        needed = []
        for cond_name, tgt, weight in conditions:
            stem = f"fine_{m_id}__{cond_name}__s{SEED}"
            wav_path = OUT_WAV_DIR / f"{stem}.wav"
            aac_path = OUT_AAC_DIR / f"{stem}.m4a"
            if not (aac_path.exists() and aac_path.stat().st_size > 0):
                needed.append((cond_name, tgt, weight, wav_path, aac_path))

        if not needed:
            print(f"All renders for {m_id} already exist! Skipping.")
            continue

        print(f"Loading model onto {args.device} for {len(needed)} renders...")
        model = StableAudioModel.from_pretrained("medium-base", device=args.device)

        if m_cfg["loras"]:
            paths = [p for p, _ in m_cfg["loras"]]
            print(f"  Applying {len(paths)} LoRA(s): {paths}")
            model.load_lora(paths)
            for idx, (_, strength) in enumerate(m_cfg["loras"]):
                model.set_lora_strength(float(strength), lora_index=idx)
            n_merged = merge_adapters(model.model)
            print(f"  Merged {n_merged} parametrized modules.")

        decode_dtype = next(model.same.parameters()).dtype

        for cond_name, tgt, weight, wav_path, aac_path in needed:
            task_idx += 1
            t0 = time.time()
            print(f"[{task_idx}/{total_renders}] Rendering {m_id} {cond_name} -> {wav_path.name} ...", flush=True)

            latch_configs = [{
                "model_path": HEAD_CKPT,
                "target_raw": tgt,
                "weight": float(weight),
                "loss_type": "cosine",
                "start_pct": 0.0,
                "end_pct": 1.0,
            }]
            latch_hparams = {"n_iter": 4, "gamma": 0.3}

            z0 = model.generate(
                prompt=PROMPT,
                duration=DURATION,
                steps=STEPS,
                cfg_scale=CFG,
                seed=SEED,
                batch_size=1,
                return_latents=True,
                latch_configs=latch_configs,
                latch_hparams=latch_hparams,
            )

            if not torch.isfinite(z0).all():
                print(f"WARNING: Non-finite latents in {wav_path.name}! Skipping.", flush=True)
                continue

            with torch.no_grad():
                audio = model.same.decode(z0.to(decode_dtype))
            audio = audio.to(torch.float32)[:, :, :int(DURATION * SAMPLE_RATE)]
            save_audio(str(wav_path), audio[0].cpu(), SAMPLE_RATE, normalize=True)
            transcode_to_aac(wav_path, aac_path)
            print(f"  -> Done in {time.time() - t0:.1f}s: {aac_path.name}", flush=True)

        del model
        torch.cuda.empty_cache()

    print("\nAll de-confounded renders complete!")


if __name__ == "__main__":
    main()
