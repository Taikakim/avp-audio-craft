#!/usr/bin/env python
"""train_hf_repair.py — train a small Snake-conv post-net to restore HF detail lost by the
frozen SAME codec (part 2/3 of the SA3 HF-repair pipeline).

The net is a Vocos/BigVGAN-lite waveform-to-waveform refiner: a stack of dilated
Snake-activated residual conv blocks. It maps the SAME-decoded audio (degraded) toward
the original crop (target). The output projection is ZERO-INITIALISED and the net is
applied as a global residual (y = x + net(x)), so at init the net is EXACTLY identity —
training only has to learn the correction. NO GAN in v1 (kept simple/correct;
adversarial / BigVGAN-discriminator is a documented v2 option, see bottom of file).

Loss = multi-resolution STFT (magnitude L1 + log-magnitude L1 at fft {512,1024,2048})
     + L1 waveform
     + HF-band-weighted STFT (extra weight on bins > 4 kHz — that's where the deficit is,
       measured env_corr 0.54/0.58 vs MP3-128 0.97/0.99).

Trains on the cached pairs from build_hf_repair_pairs.py (no GPU codec pass needed here).
Held-out split read from the manifest's is_val flag. Checkpoints per epoch + csv log.

Run (SA3 venv; small net, trains fast on GPU, works on CPU for smoke tests):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
    stable-audio-3/.venv/bin/python eval/train_hf_repair.py \
      --pairs-dir /run/media/kim/Mantu/sa3_lora_runs/hf_repair_pairs \
      --epochs 40 --lr 3e-4 --hf-weight 2.0

HFRepairNet and MultiResSTFTLoss are imported by eval_hf_repair.py — single source here.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.utils.checkpoint
import torch.nn as nn
import torch.nn.functional as F

SR = 44100


# ----------------------------------------------------------------------------- Snake -----
class Snake1d(nn.Module):
    """Snake activation: x + (1/a) * sin^2(a x), learnable per-channel a (init 1.0).
    Reimplemented standalone — the SA3 fork has NO importable Snake class (its
    blocks.ResidualUnit is ELU-only; PatchedPretransform's use_snake kwarg is dormant/
    unwired), so a self-contained impl keeps this post-net free of the model package."""
    def __init__(self, channels):
        super().__init__()
        self.alpha = nn.Parameter(torch.ones(1, channels, 1))

    def forward(self, x):
        a = self.alpha
        return x + (1.0 / (a + 1e-9)) * torch.sin(a * x) ** 2


class SnakeResBlock(nn.Module):
    """Dilated Snake residual unit: Snake -> Conv(k=7, dilation=d) -> Snake -> Conv(k=1),
    plus a residual add. Mirrors the DAC/BigVGAN residual-unit shape."""
    def __init__(self, channels, dilation):
        super().__init__()
        pad = (7 - 1) // 2 * dilation
        self.block = nn.Sequential(
            Snake1d(channels),
            nn.Conv1d(channels, channels, 7, dilation=dilation, padding=pad),
            Snake1d(channels),
            nn.Conv1d(channels, channels, 1),
        )

    def forward(self, x):
        return x + self.block(x)


class HFRepairNet(nn.Module):
    """Waveform HF-repair post-net. Global residual + zero-init output => identity at init.

    channels=160, dilations=[1,3,9] repeated n_stacks=4 => 12 residual units => ~2.5M
    params, inside the 2-5M target. (Design decision — flagged in the pipeline report;
    tune channels/n_stacks to move within the band.)"""
    def __init__(self, channels=160, dilations=(1, 3, 9), n_stacks=4, io_channels=2,
                 use_checkpoint=True):
        super().__init__()
        self.use_checkpoint = use_checkpoint   # gradient checkpointing (OFF avoids ROCm recompile stall)
        self.in_conv = nn.Conv1d(io_channels, channels, 7, padding=3)
        blocks = []
        for _ in range(n_stacks):
            for d in dilations:
                blocks.append(SnakeResBlock(channels, d))
        self.blocks = nn.ModuleList(blocks)
        self.out_snake = Snake1d(channels)
        self.out_conv = nn.Conv1d(channels, io_channels, 7, padding=3)
        # Zero-init the output projection => net(x)=0 at init => y = x (exact identity start).
        nn.init.zeros_(self.out_conv.weight)
        nn.init.zeros_(self.out_conv.bias)

    def forward(self, x):
        h = self.in_conv(x)
        for b in self.blocks:
            # gradient-checkpoint the residual stack in training: recompute each block in
            # backward instead of retaining all 12 blocks' Snake intermediates (~12x less
            # activation memory; the Snake sin(a*x)^2 tensors are what OOM'd a 16GB card).
            if self.use_checkpoint and self.training and h.requires_grad:
                h = torch.utils.checkpoint.checkpoint(b, h, use_reentrant=False)
            else:
                h = b(h)
        h = self.out_conv(self.out_snake(h))
        return x + h  # global residual: refinement rides on top of the decoded signal


# ------------------------------------------------------------------ multi-res STFT loss -----
class MultiResSTFTLoss(nn.Module):
    """Multi-resolution STFT loss = sum over fft sizes of (spectral-convergence-free)
    magnitude L1 + log-magnitude L1, plus an HF-band-weighted magnitude term that
    up-weights bins with centre frequency > hf_cutoff. Also adds an L1 waveform term.
    Stereo handled by folding channels into the batch."""
    def __init__(self, fft_sizes=(512, 1024, 2048), hf_weight=1.0, hf_cutoff=4000.0,
                 l1_wave=1.0, sr=SR):
        super().__init__()
        self.fft_sizes = list(fft_sizes)
        self.hops = [n // 4 for n in self.fft_sizes]
        self.hf_weight = hf_weight
        self.hf_cutoff = hf_cutoff
        self.l1_wave = l1_wave
        self.sr = sr
        self.windows = {n: torch.hann_window(n) for n in self.fft_sizes}

    def _stft_mag(self, x, n_fft, hop):
        # x: [B, T] -> magnitude [B, F, frames]
        w = self.windows[n_fft].to(x.device, x.dtype)
        spec = torch.stft(x, n_fft=n_fft, hop_length=hop, win_length=n_fft,
                          window=w, return_complex=True, center=True)
        return spec.abs()

    def forward(self, pred, target):
        # pred/target: [B, C, T] -> fold channels into batch
        B, C, T = pred.shape
        p = pred.reshape(B * C, T)
        t = target.reshape(B * C, T)
        total = pred.new_zeros(())
        for n_fft, hop in zip(self.fft_sizes, self.hops):
            mp = self._stft_mag(p, n_fft, hop)
            mt = self._stft_mag(t, n_fft, hop)
            mag_l1 = F.l1_loss(mp, mt)
            log_l1 = F.l1_loss(torch.log(mp + 1e-5), torch.log(mt + 1e-5))
            total = total + mag_l1 + log_l1
            if self.hf_weight > 0:
                freqs = torch.linspace(0, self.sr / 2, mp.shape[1], device=p.device)
                hf = (freqs > self.hf_cutoff).float().view(1, -1, 1)
                denom = hf.sum().clamp(min=1.0)
                hf_l1 = ((mp - mt).abs() * hf).sum() / (denom * mp.shape[0] * mp.shape[2])
                total = total + self.hf_weight * hf_l1
        if self.l1_wave > 0:
            total = total + self.l1_wave * F.l1_loss(pred, target)
        return total


# -------------------------------------------------------------------------- dataset -----
class PairDataset(torch.utils.data.Dataset):
    def __init__(self, pairs_dir, split, crop_n=None):
        self.dir = Path(pairs_dir)
        self.split = split
        self.crop_n = crop_n            # if set, (random for train / center for val) crop length
        meta = json.loads((self.dir / "manifest.json").read_text())
        self.items = [m for m in meta["pairs"]
                      if (m["is_val"] if split == "val" else not m["is_val"])]
        if not self.items:
            raise RuntimeError(f"no {split} pairs in {pairs_dir} (build pairs first)")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        d = np.load(self.dir / self.items[i]["file"])
        deg = torch.from_numpy(d["degraded"]).float()
        tgt = torch.from_numpy(d["target"]).float()
        T = deg.shape[-1]
        if self.crop_n and T > self.crop_n:
            if self.split == "train":
                st = int(torch.randint(0, T - self.crop_n + 1, (1,)).item())
            else:
                st = (T - self.crop_n) // 2         # center crop -> stable val loss
            deg = deg[..., st:st + self.crop_n]
            tgt = tgt[..., st:st + self.crop_n]
        return deg, tgt


def param_count(m):
    return sum(p.numel() for p in m.parameters())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs-dir", default="/run/media/kim/Mantu/sa3_lora_runs/hf_repair_pairs")
    ap.add_argument("--out-dir", default="/run/media/kim/Mantu/sa3_lora_runs/hf_repair_runs/v1")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--hf-weight", type=float, default=2.0)
    ap.add_argument("--hf-cutoff", type=float, default=4000.0)
    ap.add_argument("--channels", type=int, default=160)
    ap.add_argument("--n-stacks", type=int, default=4)
    ap.add_argument("--crop-seconds", type=float, default=1.5,
                    help="random(train)/center(val) crop length; caps activation memory + augments")
    ap.add_argument("--no-checkpoint", action="store_true",
                    help="disable gradient checkpointing (avoids ROCm recompile stall; needs smaller crop/batch)")
    ap.add_argument("--max-pairs", type=int, default=0,
                    help="cap dataset size for fast code-verification (0 = full)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    device = args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu"
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    net = HFRepairNet(channels=args.channels, n_stacks=args.n_stacks,
                      use_checkpoint=not args.no_checkpoint).to(device)
    print(f"[model] HFRepairNet params: {param_count(net):,} "
          f"(channels={args.channels}, n_stacks={args.n_stacks})", flush=True)
    loss_fn = MultiResSTFTLoss(hf_weight=args.hf_weight, hf_cutoff=args.hf_cutoff).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr)

    crop_n = int(SR * args.crop_seconds) if args.crop_seconds else None
    tr = PairDataset(args.pairs_dir, "train", crop_n=crop_n)
    va = PairDataset(args.pairs_dir, "val", crop_n=crop_n)
    if args.max_pairs:
        tr.items = tr.items[:args.max_pairs]
        va.items = va.items[:max(4, args.max_pairs // 8)]
    trl = torch.utils.data.DataLoader(tr, batch_size=args.batch_size, shuffle=True,
                                      num_workers=args.num_workers, drop_last=True)
    val = torch.utils.data.DataLoader(va, batch_size=args.batch_size, shuffle=False,
                                      num_workers=args.num_workers)
    print(f"[data] train={len(tr)} val={len(va)}", flush=True)

    (out / "args.json").write_text(json.dumps(vars(args), indent=1))
    csv_path = out / "train_log.csv"
    with open(csv_path, "w", newline="") as f:
        csv.writer(f).writerow(["epoch", "train_loss", "val_loss", "sec"])

    best = float("inf")
    for ep in range(args.epochs):
        t0 = time.time()
        net.train()
        tl = 0.0
        for si, (deg, tgt) in enumerate(trl):
            deg, tgt = deg.to(device), tgt.to(device)
            opt.zero_grad()
            loss = loss_fn(net(deg), tgt)
            if not torch.isfinite(loss):
                continue                                   # skip non-finite batch (guard)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)   # prevent grad explosion -> NaN
            opt.step()
            tl += loss.item()
            if si % 200 == 0:
                dt = time.time() - t0
                print(f"  ep{ep} step {si}/{len(trl)} loss {loss.item():.4f} "
                      f"{(si+1)/max(dt,1e-6):.1f} it/s", flush=True)
        tl /= max(1, len(trl))

        net.eval()
        vl = 0.0
        with torch.no_grad():
            for deg, tgt in val:
                deg, tgt = deg.to(device), tgt.to(device)
                vl += loss_fn(net(deg), tgt).item()
        vl /= max(1, len(val))
        dt = time.time() - t0

        torch.save({"model": net.state_dict(), "args": vars(args), "epoch": ep,
                    "val_loss": vl}, out / f"epoch_{ep:03d}.pt")
        if vl < best:
            best = vl
            torch.save({"model": net.state_dict(), "args": vars(args), "epoch": ep,
                        "val_loss": vl}, out / "best.pt")
        with open(csv_path, "a", newline="") as f:
            csv.writer(f).writerow([ep, f"{tl:.5f}", f"{vl:.5f}", f"{dt:.1f}"])
        print(f"[ep {ep:03d}] train {tl:.4f} val {vl:.4f} ({dt:.1f}s)"
              f"{'  *best' if vl == best else ''}", flush=True)

    print(f"[done] best val {best:.4f} -> {out}", flush=True)


# ---------------------------------------------------------------------------------------
# v2 options (documented, NOT implemented here to keep v1 simple/correct):
#   - Adversarial training with a BigVGAN/DAC multi-period + multi-resolution STFT
#     discriminator (add a hinge GAN loss + feature-matching loss on top of the current
#     reconstruction loss). Gives crisper "air" than STFT-L1 alone but needs careful
#     balancing; land only after v1's env_corr gain is confirmed real.
#   - Mel/perceptual weighting, SNR-in-band losses, and conditioning the post-net on the
#     latent z (not just the decoded waveform).
# ---------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
