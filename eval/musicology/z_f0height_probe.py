#!/usr/bin/env python
"""z_f0height_probe.py — is LEAD PITCH-HEIGHT (Melodia f0) decodable from SAME z0? (D3 go/no-go)

The lightweight-first de-risk for the melody-control head (CONTINUITY 2026-08-13, Kim GO). The
native SAME chroma is octave-FOLDED (register-blind) and the same_chroma LatCH head already reads
it linearly; the open question for a pitch/MELODY head is whether REGISTER (which octave / where the
line sits) survives in z. z88_probe answered this against the MuScriptor 88-key roll (centroid corr
~0.52) but that target carried voice-attribution noise. Now latents_sa3 companions carry the clean
Melodia f0 (f0_other_ts, region-verified, F-audited), so this probes z -> f0-height DIRECTLY.

Target: f0_other_ts (lead) -> semitones (69 + 12*log2(f/440)); weight = f0_other_voiced_ts (pooled
voicing = the honest per-frame loss weight, per Kim's 32-draw ensemble: instability lives in voicing,
not pitch). Weighted MSE. Metric = correlation(pred, true) over voiced frames + MAE in semitones,
LINEAR (register linearly present?) vs MLP (nonlinear/entangled?). Artist-disjoint split.

Run (SAO venv, GPU, mirrors /tmp/gpu.lock):
  .venv/bin/python z_f0height_probe.py --variant lin_ctx1|mlp_ctx2
"""
import argparse, glob, json, os, time
os.environ.setdefault('FLASH_ATTENTION_TRITON_AMD_ENABLE', 'FALSE')
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

LAT = '/home/kim/Projects/latents_sa3'
NF = 4096
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'z_f0height_probe_results.json')


def hz_to_semitone(f):
    return np.where(f > 0, 69.0 + 12.0 * np.log2(np.maximum(f, 1e-6) / 440.0), 0.0).astype(np.float32)


def gather(max_tracks_val=60, cap_train=1600, cap_val=320, seed=0):
    """Artist-disjoint split over f0-backed crops. Returns (train_ids, val_ids)."""
    rng = np.random.default_rng(seed)
    by_artist = {}
    for jp in sorted(glob.glob(LAT + '/*.json')):
        idx = os.path.basename(jp)[:-5]
        if not idx.isdigit():
            continue
        npz = os.path.join(LAT, idx + '.TIMESERIES.npz')
        if not os.path.exists(npz) or not os.path.exists(os.path.join(LAT, idx + '.npy')):
            continue
        info = json.load(open(jp))
        tn = info.get('source_track', '')
        artist = tn.split(' - ')[0].strip().lower() if ' - ' in tn else tn.lower()
        by_artist.setdefault(artist, []).append(idx)
    artists = sorted(by_artist)
    rng.shuffle(artists)
    val_artists = set(artists[:max_tracks_val])
    train, val = [], []
    for a in artists:
        (val if a in val_artists else train).extend(by_artist[a])
    rng.shuffle(train); rng.shuffle(val)
    return train[:cap_train], val[:cap_val]


def load(ids):
    keep = []
    Xs, Ys, Ws = [], [], []
    for fid in ids:
        try:
            z = np.load(os.path.join(LAT, fid + '.npy'))
            z = z[0] if z.ndim == 3 else z
            d = np.load(os.path.join(LAT, fid + '.TIMESERIES.npz'))
            if 'f0_other_ts' not in d.files:
                continue
            f0 = d['f0_other_ts'][:NF].astype(np.float32)
            w = (d['f0_other_voiced_ts'][:NF].astype(np.float32) if 'f0_other_voiced_ts' in d.files
                 else (f0 > 0).astype(np.float32))
        except Exception:
            continue
        if z.shape[-1] < NF or (w > 0).mean() < 0.05:      # skip near-silent-lead crops
            continue
        Xs.append(z[:, :NF].astype(np.float16))
        Ys.append(hz_to_semitone(f0))
        Ws.append(w)
        keep.append(fid)
    return (np.stack(Xs), np.stack(Ys), np.stack(Ws), keep)


class Readout(nn.Module):
    def __init__(self, arch, ctx, hidden=512):
        super().__init__()
        self.arch = arch; k = 2 * ctx + 1
        if arch == 'lin':
            self.head = nn.Conv1d(256, 1, k, padding=ctx)
        else:
            self.c1 = nn.Conv1d(256, hidden, k, padding=ctx); self.c2 = nn.Conv1d(hidden, 1, 1)

    def forward(self, x):
        return self.head(x) if self.arch == 'lin' else self.c2(F.gelu(self.c1(x)))


@torch.no_grad()
def evaluate(model, X, Y, W, dev, norm, ynorm, bs=8):
    model.eval(); P, T, M = [], [], []
    ym, ys = ynorm
    for i in range(0, len(X), bs):
        x = torch.from_numpy(X[i:i+bs].astype(np.float32)).to(dev)
        x = (x - norm[0]) / norm[1]
        p = model(x).squeeze(1) * ys + ym                 # un-standardize -> raw semitones
        y = torch.from_numpy(Y[i:i+bs]).to(dev); w = torch.from_numpy(W[i:i+bs]).to(dev)
        m = w > 0.5
        P.append(p[m].cpu().numpy()); T.append(y[m].cpu().numpy()); M.append(w[m].cpu().numpy())
    p, t = np.concatenate(P), np.concatenate(T)
    corr = float(np.corrcoef(p, t)[0, 1]) if len(p) > 10 else float('nan')
    mae = float(np.abs(p - t).mean())
    # octave-agnostic (pitch-class) corr, to separate "right note" from "right register"
    pcp, pct = p % 12, t % 12
    pc_mae = float(np.minimum(np.abs(pcp - pct), 12 - np.abs(pcp - pct)).mean())
    return dict(height_corr=round(corr, 4), height_mae_st=round(mae, 3),
                pitchclass_mae_st=round(pc_mae, 3), n_voiced_frames=len(p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='lin_ctx1')
    ap.add_argument('--epochs', type=int, default=20)
    ap.add_argument('--bs', type=int, default=8)
    ap.add_argument('--patience', type=int, default=5)
    args = ap.parse_args()
    arch, ctxs = args.variant.split('_'); ctx = int(ctxs.replace('ctx', ''))
    lr = 3e-3 if arch == 'lin' else 1e-3
    dev = 'cuda'; torch.manual_seed(0); np.random.seed(0)

    lock = '/tmp/gpu.lock'
    open(lock, 'w').write(f'CONTINUITY z_f0height_probe {os.getpid()}\n')
    try:
        tr_ids, va_ids = gather()
        print(f'artist-disjoint split: {len(tr_ids)} train / {len(va_ids)} val crops', flush=True)
        t0 = time.time()
        Xtr, Ytr, Wtr, _ = load(tr_ids)
        Xva, Yva, Wva, _ = load(va_ids)
        print(f'loaded train {Xtr.shape} val {Xva.shape} in {time.time()-t0:.0f}s', flush=True)
        sub = Xtr[::4].astype(np.float32)
        norm = (torch.tensor(sub.mean((0, 2), keepdims=True)).to(dev),
                torch.tensor(sub.std((0, 2), keepdims=True).clip(1e-3)).to(dev))
        # TARGET standardisation (C, 2026-08-28 — this was MISSING and the script was
        # internally inconsistent: the loop trained on RAW semitones while evaluate()
        # un-standardised with p*ys+ym, and `ynorm` was never constructed at all, so
        # evaluate() raised TypeError for every variant. The stored lin_ctx1 result
        # (height_mae_st 66.1 ~ 5.5 octaves) is what you get when the head outputs ~0
        # against targets in the 60-84 semitone range, i.e. it is not a trustworthy
        # number. Standardising the target also just conditions the fit properly:
        # a head regressing a mean-70 quantity from scratch wastes its capacity on the
        # offset. Stats come from VOICED train frames only, since unvoiced frames carry
        # no pitch and are already zero-weighted in the loss.
        _voiced = Wtr > 0
        _ym = float(Ytr[_voiced].mean()) if _voiced.any() else 0.0
        _ys = float(Ytr[_voiced].std()) or 1.0
        ynorm = (_ym, _ys)
        print(f'target standardisation: mean {_ym:.2f} st, sd {_ys:.2f} st', flush=True)
        model = Readout(arch, ctx).to(dev)
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        best = {'height_corr': -1}; best_state = None; bad = 0
        for ep in range(args.epochs):
            model.train(); order = np.random.permutation(len(Xtr))
            for i in range(0, len(order), args.bs):
                idx = order[i:i+args.bs]
                x = torch.from_numpy(Xtr[idx].astype(np.float32)).to(dev)
                x = (x - norm[0]) / norm[1]
                y = (torch.from_numpy(Ytr[idx]).to(dev) - _ym) / _ys
                w = torch.from_numpy(Wtr[idx]).to(dev)
                p = model(x).squeeze(1)
                loss = (w * (p - y) ** 2).sum() / w.sum().clamp_min(1e-6)   # voicing-weighted MSE
                opt.zero_grad(); loss.backward(); opt.step()
            m = evaluate(model, Xva, Yva, Wva, dev, norm, ynorm)
            print(f'  ep{ep:02d} val {m}', flush=True)
            if m['height_corr'] > best['height_corr']:
                best = m; best_state = {k: v.cpu() for k, v in model.state_dict().items()}; bad = 0
            else:
                bad += 1
                if bad >= args.patience:
                    break
        out = {'variant': args.variant, 'arch': arch, 'ctx': ctx, **best,
               'n_train': len(Xtr), 'n_val': len(Xva)}
        allr = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {}
        allr[args.variant] = out
        json.dump(allr, open(RESULTS, 'w'), indent=2)
        print('BEST', json.dumps(out), flush=True)
    finally:
        if open(lock).read().startswith('CONTINUITY z_f0height'):
            os.remove(lock)


if __name__ == '__main__':
    main()
