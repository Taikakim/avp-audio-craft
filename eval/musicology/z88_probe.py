#!/usr/bin/env python
"""z88_probe.py — is the register-aware 88-key note-grid linearly decodable from SAME z0?

The go/no-go for the 88-key movement conditioner (Kim 2026-08-12). Chroma is octave-folded;
the 88-key roll (prep_notegrid88.py) keeps register. Question: does z0 carry register-aware
pitch presence, or only pitch-class (like the native 384-d chroma)? If a LINEAR readout
recovers the roll (and esp. its pitch CENTROID = the movement signal), register survives and
the conditioner is viable; if only an MLP does, it's nonlinear/entangled.

Reuses head_a_ceiling/splits.json (artist-disjoint; notegrid88 built for the same melody ids).
Targets binarised (key active if roll>THR); BCEWithLogits (pos-weighted for sparsity).
Metrics: per-frame macro-F1 (confident frames), mean per-key AUC, and — the crux —
CENTROID CORRELATION (pred pitch-centroid vs true, over active frames) = does register/movement
track. Compares linear (register linearly present?) vs MLP (nonlinearly present?).

Run (SAO venv, GPU, under .gpu.lock):
  .venv/bin/python z88_probe.py --variant lin_ctx1|mlp_ctx2 [--epochs N]
"""
import argparse, json, math, os, time
os.environ.setdefault('FLASH_ATTENTION_TRITON_AMD_ENABLE', 'FALSE')
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
SPLITS = os.path.join(HERE, 'head_a_ceiling', 'splits.json')
LATENTS = '/home/kim/Projects/latents_sa3'
ROLLS = '/home/kim/Projects/latents_sa3_notegrid88'
RESULTS = os.path.join(HERE, 'z88_probe_results.json')
N_FRAMES, N_KEYS, THR = 4096, 88, 0.1


def load_split():
    d = json.load(open(SPLITS))
    keep = lambda ids: [i for i in ids
                        if os.path.exists(os.path.join(ROLLS, i + '.npy'))
                        and os.path.exists(os.path.join(LATENTS, i + '.npy'))]
    return {k: keep(d[k]) for k in ('train', 'val', 'test')}


def load_arrays(ids):
    X = np.empty((len(ids), 256, N_FRAMES), np.float16)
    A = np.empty((len(ids), N_FRAMES, N_KEYS), np.float16)   # binarised active
    C = np.empty((len(ids), N_FRAMES), np.float16)           # true pitch centroid (key idx)
    ks = np.arange(N_KEYS)
    for i, fid in enumerate(ids):
        z = np.load(os.path.join(LATENTS, fid + '.npy'))
        z = z[0] if z.ndim == 3 else z
        X[i] = z[:, :N_FRAMES]
        r = np.load(os.path.join(ROLLS, fid + '.npy')).astype(np.float32)
        A[i] = (r > THR)
        s = r.sum(1)
        C[i] = np.where(s > 1e-6, (r * ks).sum(1) / np.maximum(s, 1e-6), np.nan)
    return X, A, C


class Readout88(nn.Module):
    def __init__(self, arch, ctx, hidden=512):
        super().__init__()
        self.arch = arch
        k = 2 * ctx + 1
        if arch == 'lin':
            self.head = nn.Conv1d(256, N_KEYS, k, padding=ctx)
        else:
            self.c1 = nn.Conv1d(256, hidden, k, padding=ctx)
            self.c2 = nn.Conv1d(hidden, N_KEYS, 1)

    def forward(self, x):
        if self.arch == 'lin':
            return self.head(x)
        return self.c2(F.gelu(self.c1(x)))


@torch.no_grad()
def evaluate(model, X, A, C, dev, norm, bs=8):
    model.eval()
    ks = torch.arange(N_KEYS, device=dev).float()
    tp = fp = fn = 0.0
    cent_p, cent_t = [], []
    for i in range(0, len(X), bs):
        x = torch.from_numpy(X[i:i+bs].astype(np.float32)).to(dev)
        a = torch.from_numpy(A[i:i+bs].astype(np.float32)).to(dev).permute(0, 2, 1)  # (B,88,T)
        x = (x - norm[0]) / norm[1]
        p = torch.sigmoid(model(x))                       # (B,88,T)
        pred = (p > 0.5).float()
        tp += (pred * a).sum().item(); fp += (pred * (1 - a)).sum().item()
        fn += ((1 - pred) * a).sum().item()
        # pred pitch centroid vs true centroid (movement signal), on frames with true energy
        ct = torch.from_numpy(C[i:i+bs].astype(np.float32)).to(dev)   # (B,T)
        pc = (p * ks[None, :, None]).sum(1) / p.sum(1).clamp_min(1e-6)  # (B,T)
        mask = ~torch.isnan(ct)
        cent_p.append(pc[mask].cpu().numpy()); cent_t.append(ct[mask].cpu().numpy())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    cp, ct = np.concatenate(cent_p), np.concatenate(cent_t)
    cent_corr = float(np.corrcoef(cp, ct)[0, 1]) if len(cp) > 10 else float('nan')
    cent_mae = float(np.abs(cp - ct).mean())
    return dict(frame_f1=round(f1, 4), precision=round(prec, 4), recall=round(rec, 4),
                centroid_corr=round(cent_corr, 4), centroid_mae_keys=round(cent_mae, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='lin_ctx1')
    ap.add_argument('--epochs', type=int, default=25)
    ap.add_argument('--bs', type=int, default=8)
    ap.add_argument('--lr', type=float, default=None)
    ap.add_argument('--hidden', type=int, default=512)
    ap.add_argument('--patience', type=int, default=6)
    args = ap.parse_args()
    arch, ctxs = args.variant.split('_'); ctx = int(ctxs.replace('ctx', ''))
    lr = args.lr or (3e-3 if arch == 'lin' else 1e-3)
    dev = 'cuda'; torch.manual_seed(0); np.random.seed(0)
    sp = load_split()
    print('split sizes:', {k: len(v) for k, v in sp.items()}, flush=True)
    t0 = time.time()
    Xtr, Atr, Ctr = load_arrays(sp['train'])
    Xva, Ava, Cva = load_arrays(sp['val'])
    Xte, Ate, Cte = load_arrays(sp['test'])
    print(f'loaded {Xtr.shape} in {time.time()-t0:.0f}s', flush=True)
    sub = Xtr[::4].astype(np.float32)
    mu = sub.mean((0, 2)); sd = sub.std((0, 2)) + 1e-6
    norm = (torch.tensor(mu, device=dev)[None, :, None], torch.tensor(sd, device=dev)[None, :, None])
    pos = Atr.astype(np.float32).mean()                    # active-key fraction (sparse)
    pw = torch.tensor((1 - pos) / max(pos, 1e-4), device=dev)
    print(f'active-key frac {pos:.4f} -> pos_weight {pw.item():.1f}', flush=True)
    model = Readout88(arch, ctx, args.hidden).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    nb = math.ceil(len(Xtr) / args.bs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs * nb)
    best = dict(f1=-1, ep=-1); bad = 0
    ckpt = os.path.join(HERE, f'z88_readout_{args.variant}.pt')
    for ep in range(args.epochs):
        model.train(); perm = np.random.permutation(len(Xtr)); tl = 0
        for bi in range(nb):
            idx = np.sort(perm[bi*args.bs:(bi+1)*args.bs])
            x = torch.from_numpy(Xtr[idx].astype(np.float32)).to(dev)
            a = torch.from_numpy(Atr[idx].astype(np.float32)).to(dev).permute(0, 2, 1)
            x = (x - norm[0]) / norm[1]
            loss = F.binary_cross_entropy_with_logits(model(x), a, pos_weight=pw)
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sched.step()
            tl += loss.item()
        sc = evaluate(model, Xva, Ava, Cva, dev, norm)
        print(f'ep{ep} loss {tl/nb:.4f} val F1 {sc["frame_f1"]} centcorr {sc["centroid_corr"]}', flush=True)
        if sc['frame_f1'] > best['f1']:
            best = dict(f1=sc['frame_f1'], ep=ep, val=sc); bad = 0
            torch.save(dict(model=model.state_dict(), arch=arch, ctx=ctx,
                            norm_mu=mu.tolist(), norm_sd=sd.tolist()), ckpt)
        else:
            bad += 1
            if bad >= args.patience:
                print(f'early stop ep{ep}', flush=True); break
    model.load_state_dict(torch.load(ckpt, map_location=dev)['model'])
    test = evaluate(model, Xte, Ate, Cte, dev, norm)
    print('TEST', test, flush=True)
    row = dict(variant=args.variant, lr=lr, best_epoch=best['ep'],
               val=best.get('val'), test=test, n=len(sp['train']), time_s=round(time.time()-t0))
    log = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {'runs': []}
    log['runs'].append(row); json.dump(log, open(RESULTS, 'w'), indent=1)
    print('logged ->', RESULTS, flush=True)


if __name__ == '__main__':
    main()
