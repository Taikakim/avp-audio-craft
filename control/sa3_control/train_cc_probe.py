"""Train the control-consistency probe: clean latent window -> onset_density scalar.

Supervised regression over latents_sa3 (<crop>.npy (1,256,4096) fp16 + <crop>.json
["onset_density"]). Random T-frame windows, segment-level label — the SAME semantics the
FiLM conditioner trains against (a window conditioned on its segment scalar), so the
consistency term is apples-to-apples. Labels normalized by (mean,std) computed on the
TRAIN split; stored in the checkpoint for consumers (cc_probe.load_probe).

Held-out validation prints MAE (raw onsets/s) and R^2 — the meter's quality gate.
Spec (incl. reward-hacking risk of a weak meter):
SAO/docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md

CPU-friendly (~0.5M params):
    stable-audio-3/.venv/bin/python -m sa3_control.train_cc_probe \
        --encoded_dir /home/kim/Projects/latents_sa3 --out cc_probe_onset.pt \
        --epochs 6 --crop-frames 512
"""
from __future__ import annotations

import argparse, glob, json, os, random, time

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

from sa3_control.cc_probe import OnsetDensityProbe


class _WinDS(Dataset):
    def __init__(self, items, crop, train=True):
        self.items, self.crop, self.train = items, crop, train

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        path, label = self.items[i]
        z = np.load(path, mmap_mode="r")                       # (1,256,T) or (256,T) fp16
        if z.ndim == 3:
            z = z[0]
        if z.ndim != 2:                                        # junk (e.g. 1-D silence) -> resample another
            return self[(i + 1) % len(self.items)]
        T = z.shape[-1]
        if self.train:
            s = random.randint(0, max(0, T - self.crop))
        else:                                                  # deterministic center crop for val
            s = max(0, (T - self.crop) // 2)
        w = np.asarray(z[:, s:s + self.crop], dtype=np.float32)
        lab = torch.from_numpy(label) if isinstance(label, np.ndarray) \
              else torch.tensor(label, dtype=torch.float32)
        return torch.from_numpy(w), lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoded_dir", default="/home/kim/Projects/latents_sa3")
    ap.add_argument("--out", default="cc_probe_onset.pt")
    ap.add_argument("--scalar-field", default="onset_density")
    ap.add_argument("--vector-field", default="",
                    help="train a VECTOR meter instead: a json key holding a dict of\n"
                         "named floats (e.g. style_genre -> 12-dim fingerprint). Keys are\n"
                         "sorted for a stable order and stored in the checkpoint.")
    ap.add_argument("--crop-frames", type=int, default=512)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--num-workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="debug: cap dataset size")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    torch.manual_seed(args.seed); random.seed(args.seed)

    items, vec_keys = [], None
    field = args.vector_field or args.scalar_field
    for npy in sorted(glob.glob(os.path.join(args.encoded_dir, "*.npy"))):
        jp = npy[:-4] + ".json"
        if not os.path.exists(jp):
            continue
        m = json.load(open(jp))
        if field not in m:
            continue
        if args.vector_field:
            d = m[field]
            if vec_keys is None:
                vec_keys = sorted(d.keys())
            items.append((npy, np.array([float(d[k]) for k in vec_keys], dtype=np.float32)))
        else:
            items.append((npy, float(m[field])))
    if args.limit:
        items = items[:args.limit]
    random.shuffle(items)
    n_val = max(1, int(len(items) * args.val_frac))
    val_items, tr_items = items[:n_val], items[n_val:]

    if args.vector_field:
        mean, std = 0.0, 1.0                      # probabilities: keep raw scale
        print(f"[data] {len(tr_items)} train / {len(val_items)} val | "
              f"{field}: {len(vec_keys)}-dim vector {vec_keys[:3]}...", flush=True)
    else:
        labels = np.array([l for _, l in tr_items], dtype=np.float64)
        mean, std = float(labels.mean()), float(labels.std() + 1e-9)
        print(f"[data] {len(tr_items)} train / {len(val_items)} val | "
              f"{field}: mean={mean:.3f} std={std:.3f}", flush=True)

    norm = lambda y: (y - mean) / std
    tr = DataLoader(_WinDS([(p, norm(l)) for p, l in tr_items], args.crop_frames, True),
                    batch_size=args.batch, shuffle=True, num_workers=args.num_workers,
                    drop_last=True)
    va = DataLoader(_WinDS([(p, norm(l)) for p, l in val_items], args.crop_frames, False),
                    batch_size=args.batch, shuffle=False, num_workers=args.num_workers)

    out_dim = len(vec_keys) if args.vector_field else 1
    probe = OnsetDensityProbe(in_ch=256, out_dim=out_dim)
    opt = torch.optim.AdamW(probe.parameters(), lr=args.lr, weight_decay=1e-2)
    best_r2, t0 = -1e9, time.time()
    for ep in range(1, args.epochs + 1):
        probe.train()
        tl, n = 0.0, 0
        for z, y in tr:
            loss = torch.nn.functional.mse_loss(probe(z), y)
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
            tl += float(loss.detach()) * len(y); n += len(y)
        probe.eval()
        preds, ys = [], []
        with torch.no_grad():
            for z, y in va:
                preds.append(probe(z)); ys.append(y)
        p = torch.cat(preds); y = torch.cat(ys)
        ss_res = float(((p - y) ** 2).sum()); ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1.0 - ss_res / (ss_tot + 1e-12)
        mae_raw = float((p - y).abs().mean()) * std
        print(f"[ep {ep}/{args.epochs}] train_mse={tl/max(n,1):.4f}  "
              f"val_R2={r2:.3f}  val_MAE={mae_raw:.2f} onsets/s  ({time.time()-t0:.0f}s)",
              flush=True)
        if r2 > best_r2:
            best_r2 = r2
            torch.save({"state": probe.state_dict(),
                        "arch": {"in_ch": 256, "out_dim": out_dim},
                        "target_keys": vec_keys,
                        "scalar_norm": (mean, std), "val_r2": r2, "val_mae_raw": mae_raw,
                        "scalar_field": field, "crop_frames": args.crop_frames},
                       args.out)
    print(f"[done] best val_R2={best_r2:.3f} -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
