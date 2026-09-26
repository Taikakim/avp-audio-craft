#!/usr/bin/env python3
"""Cumulative ablation of the shampoo-run recipe, down to a plain AdamW DoRA (W 2026-09-26).

WHY: goa5k_r128_shampoo_subloss_k5_2026-09-26 and goa3_avp_r128_shampoo_b16_3e4_2026-09-25 move
5-15x less in weight space per step than every other recent DoRA run (checkpoint-stats: lora_B
1.2-1.8 per 1k steps vs 19-29). Shampoo whitening cannot be the cause on its own -- the Mousse
update renormalises to the pre-unwhitening msign norm, so whitening changes direction, not length.
This chain removes one component at a time (cumulatively) so the slowdown can be attributed.

Every arm: latents_sa3 (5,400 crops), T256, batch 16, seed 42, 1011 steps (3 epochs), warmup 1000,
one checkpoint at step 1011 -- the same point as the reference run's step=1011.ckpt. CSV logger, so
each arm's loss is readable afterwards. Arms are resumable: an arm whose step=1011.ckpt exists is
skipped. Waits for the reference run to exit first, and holds the GPU lock per arm.

Analysis: eval/ablation_velocity_report.py.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

SAO = Path("/home/kim/Projects/SAO")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/ablation_goa5k_2026-09-26")
PY = str(SAO / ".venv/bin/python")
TRAIN = str(SAO / "stable-audio-3/scripts/train_lora_modular.py")
GUARD = str(SAO / "Misc/gpu_guard.sh")
WAIT_FOR = "name goa5k_r128_shampoo_subloss_k5_2026-09-26"
STEPS = 1011

COMMON = ["--encoded_dir", "/home/kim/Projects/latents_sa3", "--caption_probs", "0,0.9,0.1",
          "--frames", "256", "--model", "medium-base", "--rank", "128", "--lora_alpha", "128",
          "--adapter_type", "dora-rows", "--batch-size", "16", "--num-workers", "10",
          "--warmup-steps", "1000", "--steps", str(STEPS), "--checkpoint_every", "200000",
          "--eval_demos", "--no-inline-demos", "--eval_milestones", str(STEPS), "--logger", "csv",
          "--output-dir", str(OUT)]

# Components of the full recipe, in removal order. Each is (name, args-when-present).
SUBSPACE = ["--subspace-loss-basis", "lumi/melody_subspace15_selective_v3.npz", "--subspace-loss-weight", "5"]
SNR = ["--modular-snr-gate"]
BRAKE = ["--modular-radial-brake", "0.8"]
VADD = ["--var-dampening", "1.15", "--var-barrier-weight", "0.08", "--var-damp-opt"]
MAGMULT = ["--modular-magnitude-update", "multiplicative"]
SHAMPOO = ["--modular-whitening", "shampoo"]
SF = ["--modular-schedule-free", "--modular-sf-c-warmup", "1000", "--modular-sf-r", "1.0"]
MODULAR_BASE = ["--optimizer", "modular", "--modular-lmo-poly", "cubic5", "--modular-beta1", "0.9",
                "--modular-wd", "0.02", "--modular-wd-overtraining"]


def modular(lr, snr=True, brake=True, vadd=True, magmult=True, shampoo=True, sf=True,
            normuon=True, subspace=True):
    a = MODULAR_BASE + ["--lr", lr]
    a += SNR if snr else []
    a += BRAKE if brake else []
    a += VADD if vadd else []
    a += MAGMULT if magmult else ["--modular-magnitude-update", "additive"]
    a += SHAMPOO if shampoo else ["--modular-whitening", "none"]
    a += SF if sf else ["--modular-no-schedule-free"]
    a += [] if normuon else ["--modular-no-normuon"]
    a += SUBSPACE if subspace else []
    return a


ARMS = [  # (name, args) -- cumulative: each arm drops one more component than the previous
    ("a00_full",          modular("3e-4")),
    ("a01_no_snr",        modular("3e-4", snr=False)),
    ("a02_no_brake",      modular("3e-4", snr=False, brake=False)),
    ("a03_no_vadd",       modular("3e-4", snr=False, brake=False, vadd=False)),
    ("a04_additive_mag",  modular("3e-4", snr=False, brake=False, vadd=False, magmult=False)),
    ("a05_no_shampoo",    modular("3e-4", snr=False, brake=False, vadd=False, magmult=False, shampoo=False)),
    ("a06_no_sf",         modular("3e-4", snr=False, brake=False, vadd=False, magmult=False, shampoo=False,
                                  sf=False)),
    ("a07_no_normuon",    modular("3e-4", snr=False, brake=False, vadd=False, magmult=False, shampoo=False,
                                  sf=False, normuon=False)),
    ("a08_no_subspace",   modular("3e-4", snr=False, brake=False, vadd=False, magmult=False, shampoo=False,
                                  sf=False, normuon=False, subspace=False)),
    ("a09_plain_adamw",   ["--optimizer", "adamw", "--lr", "1e-4"]),
    # lr A/B on the FULL recipe (the other suspect besides the SNR gate)
    ("a10_full_lr5e-4",   modular("5e-4")),
]


def log(msg):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "chain.log", "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def main():
    only = set(sys.argv[1:])
    log("chain start; waiting for the reference run to exit")
    while subprocess.run(["pgrep", "-f", WAIT_FOR], capture_output=True).returncode == 0:
        time.sleep(60)
    env = dict(os.environ, FLASH_ATTENTION_TRITON_AMD_ENABLE="FALSE", ROCR_VISIBLE_DEVICES="0",
               PYTORCH_TUNABLEOP_ENABLED="0", MIOPEN_FIND_MODE="2", OMP_NUM_THREADS="4",
               MKL_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", NUMEXPR_NUM_THREADS="4")
    for name, args in ARMS:
        if only and name not in only:
            continue
        run = f"ablation_goa5k_{name}"
        if (OUT / run / f"step={STEPS}.ckpt").exists():
            log(f"{name}: checkpoint exists, skipped")
            continue
        while subprocess.run([GUARD, "acquire", "WINTERMUTE", str(os.getpid())],
                             env=dict(env, KIND="batch", NOTE=f"W ablation arm {name}"),
                             capture_output=True).returncode != 0:
            time.sleep(120)
        try:
            log(f"{name}: start  {' '.join(args)}")
            (OUT / run).mkdir(parents=True, exist_ok=True)
            with open(OUT / run / "train.log", "a") as lf:
                rc = subprocess.run([PY, TRAIN, *COMMON, "--name", run, *args,
                                     "--purpose", f"cumulative ablation arm {name} of the shampoo-run recipe",
                                     "--hypothesis", "attribute the 5-15x low weight-space velocity to a component"],
                                    cwd=SAO, env=env, stdout=lf, stderr=subprocess.STDOUT).returncode
            ok = (OUT / run / f"step={STEPS}.ckpt").exists()
            log(f"{name}: exit rc={rc} checkpoint={'yes' if ok else 'MISSING'}")
        finally:
            subprocess.run([GUARD, "release", "WINTERMUTE", str(os.getpid())], capture_output=True)
    log("chain done")


if __name__ == "__main__":
    main()
