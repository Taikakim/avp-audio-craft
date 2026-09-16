#!/usr/bin/env python
"""hf_latch_gradnorm_probe.py — WINTERMUTE 2026-09-16.

WHY: G's two bracket rounds (eval/hf_latch_bracket.py, WORKLOG 2026-09-16) found the
`rms_energy_air` LatCH head has no audible effect on the post-trained `medium`
checkpoint: every guided render sounded identical across gain 2..2048, yet all were
"strongly over-damped" vs the unguided baseline. The conclusion recorded there was
that the head must be RETRAINED for the rf_denoiser/8-step regime.

That retrain is a NO-OP and this probe exists to prove it cheaply before anyone spends
time on it. `latch/train_latch.py:67` maps BOTH "rectified_flow" and "rf_denoiser" to
the same forward noising (alpha=1-t, sigma=t), so `--objective rf_denoiser` produces a
bit-identical head. The only thing that changes is the metadata string that
`model.py:534` compares to raise its WARNING -- so retraining would DELETE the warning
while changing nothing, which is worse than leaving it.

THE REAL STRUCTURAL FACT: `sampling.py:445` makes pingpong the NATIVE sampler for
rf_denoiser, but `model.py:358` routes any non-empty latch_configs into
`sample_flow_euler_multi_latch_guided`. There is no guided pingpong sampler in the tree
(`grep latch inference/sampling.py` -> nothing). So merely ASKING for guidance converts
an 8-step pingpong render into an 8-step Euler render, before any head is consulted.

WHAT THIS MEASURES (numbers, not ears -- the upgrade over the by-ear bracket):

  arm 0  baseline_pingpong : no latch_configs      -> the model's native sampler
  arm 1  euler_gain0       : latch_configs, rho=mu=0 -> Euler, guidance TERM INERT
  arm 2  gain2             : rho=mu=2
  arm 3  gain2048          : rho=mu=2048            (1000x arm 2)

Arm 1 is the load-bearing one: it isolates the sampler swap from the head. Then

  d(arm1, arm0) = what the SAMPLER SWAP alone costs      <- expect LARGE if the
                                                            "over-damping" is the sampler
  d(arm2, arm1) = what guidance does at low gain
  d(arm3, arm2) = what a 1000x gain increase does        <- expect ~0 per G's report

plus per-step ||grad_var|| from log_norms=True, which separates the two candidate
mechanisms for gain-invariance:
  * norms ~= 0            -> the head contributes nothing on these latents
  * norms large, d(arm3,arm2) ~= 0 -> OVERSHOOT SATURATION: the mean-guidance loop runs
    z0 -= mu*grad_mean n_iter=4 times, so any mu past a threshold lands in the same
    attractor. That is TUNABLE TODAY (n_iter / mu) with no retrain.

Config is copied verbatim from G's bracket (same ckpt, prompt, seed, steps, cfg,
duration, target) so the numbers are directly comparable to what Kim heard.

CAVEAT carried over from G's script: the target is the head's OWN std_mean (-32.9611 dB),
which after model.py's standardization is EXACTLY 0.0 -- i.e. "make air energy
corpus-average", not "reduce it". Even with working guidance that is not a damping
request. Not fixed here on purpose: this probe answers "does guidance act at all", and
changing the target at the same time would confound that.

RUN (needs the GPU lock; ~4 short renders):

  python3 Misc/filelock.py acquire /home/kim/Projects/SAO/.gpu.lock \
      --handle WINTERMUTE --pid-aware --pid $$
  /home/kim/Projects/SAO/.venv/bin/python -u \
      /home/kim/Projects/SAO/eval/hf_latch_gradnorm_probe.py \
      2>&1 | tee /tmp/hf_latch_gradnorm.log
  python3 Misc/filelock.py release /home/kim/Projects/SAO/.gpu.lock --handle WINTERMUTE

`-u` is REQUIRED: the per-step grad norms go to stdout, which Python block-buffers when
redirected, while warnings go to unbuffered stderr (WORKLOG 2026-08-21 trap).

Run it as a FILE, never as `python -c` from the SAO root -- SAO/torchcodec/ shadows the
real package from that cwd and SA3 fails to load (MASTER §5).
"""
import os

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import json
from pathlib import Path

import numpy as np
import torch

from stable_audio_3 import StableAudioModel

FPS = 44100 / 4096

# --- verbatim from eval/hf_latch_bracket.py so the arms are comparable -------------
HF_HEAD = ("/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/"
           "latch_sa3_rms_energy_air_best.pt")
HF_TARGET_DB = -32.9611
CKPT = ("/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep/"
        "epoch=6-step=2093.weights.ckpt")
PROMPT = ("This track is a high-energy psytrance piece that blends classic Goa-trance "
          "hypnotic loops with the relentless drive of modern techno. Built around a "
          "pounding 4/4 kick, the production is polished and high-fidelity, employing a "
          "wide stereo field and dynamic panning of its signature elements.")
SEED = 1000
STEPS = 8
CFG = 1.0
DURATION = 48.0

OUT_DIR = Path("/tmp/hf_latch_gradnorm")


def rel_l2(a: torch.Tensor, b: torch.Tensor) -> float:
    """Relative L2 distance ||a-b|| / ||b||. 0.0 == bit-identical latents."""
    a = a.float().cpu()
    b = b.float().cpu()
    denom = b.norm().item()
    return float((a - b).norm().item() / max(denom, 1e-12))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from sa3_control.audio_io import save_audio

    print("[load] medium (POST-TRAINED, rf_denoiser/pingpong) + DoRA", flush=True)
    model = StableAudioModel.from_pretrained("medium", device="cuda")
    model.load_lora([CKPT])
    sr = model.model.sample_rate
    print(f"[load] diffusion_objective = {model.model.diffusion_objective!r}", flush=True)

    n_frames = round(DURATION * FPS)
    hf_target = np.full((1, n_frames), HF_TARGET_DB, dtype=np.float32)

    def latch_cfg():
        return [{"model_path": HF_HEAD, "target_raw": hf_target,
                 "weight": 1.0, "start_pct": 0.0, "end_pct": 1.0}]

    # (tag, latch_configs, latch_hparams)
    #
    # arm1-arm3 FORCE euler to reproduce the pre-fix behaviour on this post-trained
    # checkpoint. Before 2026-09-16 euler was hardcoded here, so these three arms are
    # exactly what G's bracket ran. arm4 is the fix: the same head, gain, seed and
    # checkpoint through the model's NATIVE pingpong sampler. Forcing the sampler
    # explicitly on both sides is what keeps the A/B honest -- otherwise "before" and
    # "after" would differ by the code version rather than by one named variable.
    arms = [
        ("arm0_baseline_pingpong", None, None),
        ("arm1_euler_gain0", latch_cfg(),
         {"rho": 0.0, "mu": 0.0, "log_norms": True, "sampler_type": "euler"}),
        ("arm2_euler_gain2", latch_cfg(),
         {"rho": 2.0, "mu": 2.0, "log_norms": True, "sampler_type": "euler"}),
        ("arm3_euler_gain2048", latch_cfg(),
         {"rho": 2048.0, "mu": 2048.0, "log_norms": True, "sampler_type": "euler"}),
        ("arm4_pingpong_gain2", latch_cfg(),
         {"rho": 2.0, "mu": 2.0, "log_norms": True, "sampler_type": "pingpong"}),
        ("arm5_pingpong_gain2048", latch_cfg(),
         {"rho": 2048.0, "mu": 2048.0, "log_norms": True, "sampler_type": "pingpong"}),
    ]

    z0 = {}
    for tag, lc, hp in arms:
        print(f"\n{'='*70}\n[gen] {tag}\n{'='*70}", flush=True)
        sink = []
        kw = dict(prompt=PROMPT, duration=DURATION, steps=STEPS, cfg_scale=CFG,
                  seed=SEED, batch_size=1, latents_sink=sink)
        if lc is not None:
            kw["latch_configs"] = lc
            kw["latch_hparams"] = hp
        out = model.generate(**kw)
        save_audio(str(OUT_DIR / f"{tag}.wav"), out[0].float().cpu(), sr)
        if not sink:
            print(f"[warn] {tag}: latents_sink stayed EMPTY -- distances unavailable",
                  flush=True)
        else:
            z0[tag] = sink[0].detach().float().cpu()
            t = z0[tag]
            finite = bool(torch.isfinite(t).all())
            print(f"[z0] {tag}: shape={tuple(t.shape)} std={t.std().item():.4f} "
                  f"finite={finite}", flush=True)
            if not finite:
                # the 2026-09-08 NaN-latent family: a non-finite z0 writes a full-scale
                # DC file that peaks at exactly 1.000. Say so rather than scoring it.
                print(f"[FAIL] {tag}: z0 is NON-FINITE -- this render is the known "
                      f"NaN/DC failure, not a guidance result.", flush=True)

    # ---- the three distances that decide the diagnosis ----------------------------
    print(f"\n{'='*70}\nRELATIVE L2 BETWEEN ARMS (0.0 == identical latents)\n{'='*70}",
          flush=True)
    dists = {}
    pairs = [
        # --- the pre-fix picture (all euler, as G's bracket ran it) ---------------
        ("sampler swap alone (arm1 vs arm0)", "arm1_euler_gain0", "arm0_baseline_pingpong"),
        ("euler: guidance at gain 2", "arm2_euler_gain2", "arm1_euler_gain0"),
        ("euler: 1000x gain increase", "arm3_euler_gain2048", "arm2_euler_gain2"),
        # --- the fix ---------------------------------------------------------------
        # THE decisive one: with the sampler correct, does gain finally do anything?
        ("pingpong: 1000x gain increase", "arm5_pingpong_gain2048", "arm4_pingpong_gain2"),
        ("fix effect at gain 2 (pingpong vs euler)", "arm4_pingpong_gain2", "arm2_euler_gain2"),
        ("pingpong guidance vs unguided baseline", "arm4_pingpong_gain2", "arm0_baseline_pingpong"),
    ]
    for label, a, b in pairs:
        if a in z0 and b in z0:
            d = rel_l2(z0[a], z0[b])
            dists[label] = d
            print(f"  {label:40s} {d:.6f}", flush=True)
        else:
            print(f"  {label:40s} (missing arm)", flush=True)

    print("\nHOW TO READ IT:", flush=True)
    print("  THE HEADLINE is 'pingpong: 1000x gain increase':", flush=True)
    print("    clearly > 0  -> the fix works. Gain acts once the sampler matches the", flush=True)
    print("       model, and the head never needed retraining.", flush=True)
    print("    still ~0     -> the sampler was NOT the (only) cause. Then read the", flush=True)
    print("       grad norms: ~0 = the head really is inert on these latents (a", flush=True)
    print("       retrain becomes arguable, though NOT the rf_denoiser one -- that", flush=True)
    print("       is still a no-op); large-but-gain-invariant = overshoot saturation,", flush=True)
    print("       tune n_iter/mu.", flush=True)
    print("  'sampler swap alone' large -> confirms the over-damping G heard was the", flush=True)
    print("     sampler, since that arm has guidance mathematically inert (rho=mu=0).", flush=True)
    print("  'sampler swap alone' ~0    -> my diagnosis was wrong. Say so plainly;", flush=True)
    print("     the euler/pingpong difference did not matter here.", flush=True)
    print("  'euler: 1000x gain' ~0 while 'pingpong: 1000x gain' > 0 is the whole", flush=True)
    print("     before/after in two numbers.", flush=True)

    (OUT_DIR / "run_meta.json").write_text(json.dumps({
        "purpose": "Decide whether the rms_energy_air LatCH head is inert on the "
                   "post-trained medium because of the head (-> retrain) or because "
                   "latch_configs silently swaps the native pingpong sampler for Euler "
                   "(-> guided pingpong sampler, no retrain). Arm1 (rho=mu=0) isolates "
                   "the sampler swap from the head.",
        "hypothesis": "The retrain G was asked for is a no-op: train_latch.py:67 maps "
                      "rectified_flow and rf_denoiser to identical forward noising, so "
                      "--objective rf_denoiser yields an identical head and only removes "
                      "the model.py:534 warning string.",
        "related_files": ["eval/hf_latch_bracket.py",
                          "stable-audio-3/stable_audio_3/model.py:358",
                          "stable-audio-3/stable_audio_3/inference/sampling.py:445",
                          "stable-audio-3/stable_audio_3/inference/latch_guided.py:83",
                          "latch/train_latch.py:67"],
        "ckpt": CKPT, "base_model": "medium (post-trained, rf_denoiser)",
        "prompt": PROMPT, "seed": SEED, "steps": STEPS, "cfg": CFG,
        "duration_s": DURATION, "hf_target_db": HF_TARGET_DB,
        "target_caveat": "target == head std_mean => standardized target is exactly 0.0, "
                         "i.e. 'corpus-average air energy', NOT a damping request. "
                         "Deliberately unchanged from G's bracket to avoid confounding.",
        "arms": [a[0] for a in arms],
        "result_rel_l2": dists,
        "kim_feedback": None,
    }, indent=2))
    print(f"\n[done] {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
