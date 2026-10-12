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
import glob
import json
import os
import re
import subprocess
import sys
import threading
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
    # 2026-09-27 round b (operator request via CONTINUITY): gradient-spike clipping, the lr-matched
    # gate-off control, and 10x-effective-lr arms (older runs sound more mature even at ep0; the gate
    # made the nominal 3e-4 an effective ~6e-5). b04-b06 may go unstable -- that is a result too.
    ("b01_adagc104",           modular("3e-4") + ["--grad-clip-mode", "adagc", "--adagc-lambda", "1.04"]),
    ("b02_adagc3",             modular("3e-4") + ["--grad-clip-mode", "adagc", "--adagc-lambda", "3"]),
    ("b03_nogate_6e-5",        modular("6e-5", snr=False)),
    ("b04_nogate_6e-4",        modular("6e-4", snr=False)),
    ("b05_nogate_6e-4_adagc3", modular("6e-4", snr=False) + ["--grad-clip-mode", "adagc", "--adagc-lambda", "3"]),
    ("b06_full_3e-3",          modular("3e-3")),
]


class ResourceTracker:
    """Samples VRAM (via sysfs) and host process-tree RSS (via /proc) every poll_interval seconds."""
    def __init__(self, pid: int, poll_interval: float = 2.0):
        self.pid = pid
        self.interval = poll_interval
        self.stop_event = threading.Event()
        self.peak_vram_bytes = 0
        self.peak_rss_bytes = 0
        self.peak_sys_ram_bytes = 0
        self.vram_samples = []
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)

    def _get_vram_bytes(self):
        for path in ("/sys/class/drm/card1/device/mem_info_vram_used",
                     "/sys/class/drm/card0/device/mem_info_vram_used"):
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        return int(f.read().strip())
                except Exception:
                    pass
        return 0

    def _get_tree_rss_bytes(self):
        pids = {self.pid}
        queue = [self.pid]
        while queue:
            curr = queue.pop(0)
            for cf in glob.glob(f"/proc/{curr}/task/*/children"):
                try:
                    with open(cf) as f:
                        for c in f.read().split():
                            c_pid = int(c)
                            if c_pid not in pids:
                                pids.add(c_pid)
                                queue.append(c_pid)
                except Exception:
                    pass
        total = 0
        for p in pids:
            try:
                with open(f"/proc/{p}/status") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            total += int(line.split()[1]) * 1024
                            break
            except Exception:
                pass
        return total

    def _get_sys_ram_used_bytes(self):
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        if k in ("MemTotal", "MemAvailable"):
                            mem[k] = int(v) * 1024
            if "MemTotal" in mem and "MemAvailable" in mem:
                return mem["MemTotal"] - mem["MemAvailable"]
        except Exception:
            pass
        return 0

    def _poll_loop(self):
        while not self.stop_event.is_set():
            vram = self._get_vram_bytes()
            if vram > 0:
                self.vram_samples.append(vram)
                if vram > self.peak_vram_bytes:
                    self.peak_vram_bytes = vram
            rss = self._get_tree_rss_bytes()
            if rss > self.peak_rss_bytes:
                self.peak_rss_bytes = rss
            sys_ram = self._get_sys_ram_used_bytes()
            if sys_ram > self.peak_sys_ram_bytes:
                self.peak_sys_ram_bytes = sys_ram
            self.stop_event.wait(self.interval)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2.0)
        mean_vram = (sum(self.vram_samples) / len(self.vram_samples)) if self.vram_samples else 0
        return {
            "peak_vram_bytes": self.peak_vram_bytes,
            "mean_vram_bytes": int(mean_vram),
            "peak_rss_bytes": self.peak_rss_bytes,
            "peak_sys_ram_bytes": self.peak_sys_ram_bytes,
            "peak_vram_gb": round(self.peak_vram_bytes / (1024**3), 2),
            "peak_rss_gb": round(self.peak_rss_bytes / (1024**3), 2),
            "peak_sys_ram_gb": round(self.peak_sys_ram_bytes / (1024**3), 2),
        }


def log(msg):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "chain.log", "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def main():
    only = set(sys.argv[1:])
    # Math-thread cap per training process. 4 was the shared-box oversubscription guard (MASTER s5);
    # this chain runs ONE training at a time, so 16 by default (raised 2026-09-26 on request).
    threads = os.environ.get("ABLATION_THREADS", "16")
    log(f"chain start (threads={threads}); waiting for the reference run and any running arm to exit")
    # also wait for an arm started by an EARLIER instance of this chain (hand-over without overlap)
    for pat in (WAIT_FOR, "name ablation_goa5k_", *filter(None, os.environ.get("ABLATION_WAIT_EXTRA", "").split(";"))):
        while subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode == 0:
            time.sleep(60)
    env = dict(os.environ, FLASH_ATTENTION_TRITON_AMD_ENABLE="FALSE", ROCR_VISIBLE_DEVICES="0",
               PYTORCH_TUNABLEOP_ENABLED="0", MIOPEN_FIND_MODE="2", OMP_NUM_THREADS=threads,
               MKL_NUM_THREADS=threads, OPENBLAS_NUM_THREADS=threads, NUMEXPR_NUM_THREADS=threads)
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
            t0 = time.time()
            with open(OUT / run / "train.log", "a") as lf:
                proc = subprocess.Popen([PY, TRAIN, *COMMON, "--name", run, *args,
                                         "--purpose", f"cumulative ablation arm {name} of the shampoo-run recipe",
                                         "--hypothesis", "attribute the 5-15x low weight-space velocity to a component"],
                                        cwd=SAO, env=env, stdout=lf, stderr=subprocess.STDOUT)
                tracker = ResourceTracker(proc.pid, poll_interval=2.0)
                tracker.start()
                rc = proc.wait()
                res = tracker.stop()
            elapsed = time.time() - t0
            ok = (OUT / run / f"step={STEPS}.ckpt").exists()

            # Parse it/s from train.log if available
            train_it_s = None
            try:
                tlog = (OUT / run / "train.log").read_text(errors="ignore")
                matches = re.findall(r"([\d\.]+)it/s", tlog)
                if matches:
                    train_it_s = float(matches[-1])
            except Exception:
                pass

            overall_it_s = round(STEPS / elapsed, 4) if elapsed > 0 else None
            sec_per_it = round(elapsed / STEPS, 2) if elapsed > 0 else None

            profile = {
                "arm": name,
                "rc": rc,
                "checkpoint": ok,
                "elapsed_sec": round(elapsed, 1),
                "overall_it_s": overall_it_s,
                "sec_per_it": sec_per_it,
                "train_it_s": train_it_s,
                **res
            }
            with open(OUT / run / "resource_profile.json", "w") as pf:
                json.dump(profile, pf, indent=2)

            speed_str = f"{overall_it_s:.3f} it/s ({sec_per_it:.2f} s/step)" if overall_it_s else "N/A"
            vram_str = f"{res['peak_vram_gb']:.2f} GB"
            ram_str = f"{res['peak_rss_gb']:.2f} GB (sys: {res['peak_sys_ram_gb']:.2f} GB)"
            log(f"{name}: exit rc={rc} checkpoint={'yes' if ok else 'MISSING'} | {speed_str} | peak VRAM {vram_str} | peak RAM {ram_str}")
        finally:
            subprocess.run([GUARD, "release", "WINTERMUTE", str(os.getpid())], capture_output=True)
    log("chain done")


if __name__ == "__main__":
    main()
