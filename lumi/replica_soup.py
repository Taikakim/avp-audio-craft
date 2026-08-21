#!/usr/bin/env python3
"""replica_soup.py — average the N replica checkpoints of one epoch into a soup ckpt
(C3-on-A10 material, 2026-08-21: the Pattern-2 fleet arms accidentally produced 8
independent same-init/same-recipe replicas per epoch — classic model-soup conditions).

Input: a run dir + epoch index. Collects epoch=E-step=S.ckpt + its -vN siblings
(each = ONE replica's coherent adapter state, per EXPERIMENTS A10), elementwise-averages
every state_dict tensor, and writes a SLIM soup ckpt (state_dict + lora_config + provenance)
that load_lora() / render_matrix_cells consumes like any adapter ckpt.

--epochs "11,13,15,17,19" averages across epochs AND replicas (temporal x replica grand
mean) into one soup. Caveat recorded in the output meta: LoRA/DoRA soup averages A, B and
magnitude separately (B·A is bilinear, so the soup's effective ΔW is not the mean ΔW) —
defensible for same-init replicas (standard LoRA-soup practice), noted honestly.

Run (CPU, container or any torch env):
  python replica_soup.py --run-dir <dir> --epoch 19 --out <dir>/rsoup_ep19.weights.ckpt
  python replica_soup.py --run-dir <dir> --epochs 11,13,15,17,19 --out <dir>/rtsoup_ep11-19.weights.ckpt
"""
import argparse
import glob
import os

import torch


def collect_replicas(run_dir, epoch):
    pats = sorted(glob.glob(os.path.join(run_dir, f"epoch={epoch}-step=*.ckpt")))
    return [p for p in pats if not p.endswith(".weights.ckpt")]


def average_ckpts(paths):
    """Elementwise mean of state_dict tensors across ckpts; lora_config from the first.
    All ckpts must share the exact key set (same run, same arch)."""
    assert paths, "no checkpoints to soup"
    acc, lora_config, n = None, None, 0
    keys0 = None
    for p in paths:
        ck = torch.load(p, map_location="cpu", weights_only=False)
        sd = ck.get("state_dict", ck)
        if lora_config is None:
            lora_config = ck.get("lora_config", {})
        if keys0 is None:
            keys0 = set(sd.keys())
            acc = {k: v.double().clone() for k, v in sd.items()}
        else:
            assert set(sd.keys()) == keys0, f"key mismatch in {p}"
            for k, v in sd.items():
                acc[k] += v.double()
        n += 1
        del ck, sd
    mean = {k: (v / n).float() for k, v in acc.items()}
    return mean, lora_config, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--epoch", type=int, default=None)
    ap.add_argument("--epochs", default=None, help="comma list; averages epochs AND replicas")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    epochs = ([a.epoch] if a.epoch is not None
              else [int(x) for x in a.epochs.split(",")])
    paths = []
    for e in epochs:
        got = collect_replicas(a.run_dir, e)
        print(f"[rsoup] epoch {e}: {len(got)} replicas")
        paths += got
    mean, lora_config, n = average_ckpts(paths)
    out = {"state_dict": mean, "lora_config": lora_config,
           "soup": {"kind": "replica" if len(epochs) == 1 else "replica+temporal",
                    "run_dir": a.run_dir, "epochs": epochs, "n_ckpts": n,
                    "note": "elementwise mean of A/B/magnitude across same-init replicas "
                            "(A10); NOT mean-of-deltaW (B*A bilinear) — standard LoRA-soup "
                            "practice, caveat recorded"}}
    torch.save(out, a.out)
    print(f"[rsoup] wrote {a.out}  ({n} ckpts averaged, {len(mean)} tensors)")


if __name__ == "__main__":
    main()
