#!/usr/bin/env python3
"""z88_dawtruth.py — is register decodable from SAME z0 with CLEAN (DAW-truth) labels?

Settles the z→88 yellow-light (corpus centroid-corr ~0.5, MuScriptor-label-limited). Trains a
readout z -> DAW-truth 88-key roll on ONE track (Two Suns) with a SECTION-DISJOINT split
(alternating sections train/test -> no positional memorisation, both span varied content), and
compares the clean-label decodability to the corpus MuScriptor number (lin 0.499 / mlp 0.522).
If clean-label centroid-corr >> 0.5, MuScriptor noise was the limiter (register IS there, the
movement conditioner is viable); if ~0.5, z's register content is genuinely ~half = a real ceiling.

CAVEATS (stated): within-track = an UPPER bound on decodability (can exploit track-specific
structure); target = merged MIDI roll, so audio-track pitches (Saranghi/Victoria) are unlabelled
content in z (noise on the target) — full-mix latent vs MIDI-only labels, honest mismatch.

Run (SAO venv, GPU): z88_dawtruth.py --z <latent.npy> --roll <_MERGED.roll.npy> --align <align.json>
"""
import argparse, json, os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F

FRAME_DUR = 4096.0 / 44100.0
THR = 0.1


class RO(nn.Module):
    def __init__(self, arch, ctx, K, hidden=512):
        super().__init__(); self.arch = arch; k = 2 * ctx + 1
        if arch == "lin":
            self.h = nn.Conv1d(256, K, k, padding=ctx)
        else:
            self.c1 = nn.Conv1d(256, hidden, k, padding=ctx); self.c2 = nn.Conv1d(hidden, K, 1)
    def forward(self, x):
        return self.h(x) if self.arch == "lin" else self.c2(F.gelu(self.c1(x)))


def run(arch, ctx, Xtr, Atr, Xte, Ate, Cte, dev, norm, K, epochs=60):
    ks = torch.arange(K, device=dev).float()
    m = RO(arch, ctx, K).to(dev)
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3 if arch == "lin" else 1e-3, weight_decay=1e-4)
    pos = Atr.mean(); pw = torch.tensor((1 - pos) / max(float(pos), 1e-4), device=dev)
    xtr = ((torch.from_numpy(Xtr).to(dev) - norm[0]) / norm[1])[None]      # (1,256,Ttr)
    atr = torch.from_numpy(Atr).to(dev).T[None]                            # (1,K,Ttr)
    for ep in range(epochs):
        m.train(); opt.zero_grad()
        loss = F.binary_cross_entropy_with_logits(m(xtr), atr, pos_weight=pw)
        loss.backward(); opt.step()
    m.eval()
    with torch.no_grad():
        xte = ((torch.from_numpy(Xte).to(dev) - norm[0]) / norm[1])[None]
        p = torch.sigmoid(m(xte))[0]                                       # (K,Tte)
        a = torch.from_numpy(Ate).to(dev).T                               # (K,Tte)
        pred = (p > 0.5).float()
        tp = (pred * a).sum(); prec = tp / pred.sum().clamp_min(1); rec = tp / a.sum().clamp_min(1)
        f1 = (2 * prec * rec / (prec + rec).clamp_min(1e-9)).item()
        pc = (p * ks[:, None]).sum(0) / p.sum(0).clamp_min(1e-6)           # pred centroid (Tte,)
        ct = torch.from_numpy(Cte).to(dev)
        msk = ~torch.isnan(ct)
        cc = float(torch.corrcoef(torch.stack([pc[msk], ct[msk]]))[0, 1])
        mae = float((pc[msk] - ct[msk]).abs().mean())
    return dict(frame_f1=round(f1, 4), centroid_corr=round(cc, 4), centroid_mae_keys=round(mae, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--z", required=True); ap.add_argument("--roll", required=True)
    ap.add_argument("--align", required=True); ap.add_argument("--kmin", type=int, default=21)
    args = ap.parse_args()
    z = np.load(args.z); z = z[0] if z.ndim == 3 else z            # (256,Tz)
    roll = np.load(args.roll).astype(np.float32)                   # (Troll,88)
    T = min(z.shape[1], roll.shape[0]); z = z[:, :T]; roll = roll[:T]
    K = roll.shape[1]
    A = (roll > THR).astype(np.float32)
    s = roll.sum(1); C = np.where(s > 1e-6, (roll * np.arange(K)).sum(1) / np.maximum(s, 1e-6), np.nan).astype(np.float32)

    al = json.load(open(args.align)); spb = al["sec_per_beat"]
    secs = sorted(al["sections"], key=lambda c: c["t0b"])
    # frame -> section index; alternate sections into train/test
    fsec = np.full(T, -1, np.int64)
    for i, c in enumerate(secs):
        f0 = int(round(c["t0b"] * spb / FRAME_DUR)); f1 = int(round(c["endb"] * spb / FRAME_DUR))
        fsec[max(0, f0):min(T, f1)] = i
    tr = (fsec >= 0) & (fsec % 2 == 0); te = (fsec >= 0) & (fsec % 2 == 1)
    print(f"T={T} ({T*FRAME_DUR:.0f}s) | train frames {tr.sum()} (even sections) | test {te.sum()} (odd)")
    print(f"active-key frac {A.mean():.4f} | sections {len(secs)}")

    dev = "cuda"; torch.manual_seed(0)
    sub = z[:, ::4].astype(np.float32); mu = sub.mean(1); sd = sub.std(1) + 1e-6
    norm = (torch.tensor(mu, device=dev)[:, None], torch.tensor(sd, device=dev)[:, None])
    Xtr, Atr = z[:, tr].astype(np.float32), A[tr]
    Xte, Ate, Cte = z[:, te].astype(np.float32), A[te], C[te]
    print("\n=== z -> DAW-truth 88-key decodability (section-disjoint) ===")
    print(f"{'arch':<10}{'frame_f1':>10}{'cent_corr':>11}{'cent_mae':>10}   (corpus MuScriptor: lin .499 / mlp .522)")
    for arch, ctx in [("lin", 1), ("mlp", 2)]:
        r = run(arch, ctx, Xtr, Atr, Xte, Ate, Cte, dev, norm, K)
        print(f"{arch+'_ctx'+str(ctx):<10}{r['frame_f1']:>10}{r['centroid_corr']:>11}{r['centroid_mae_keys']:>10}")


if __name__ == "__main__":
    main()
