#!/usr/bin/env python
"""train_readout.py — Head A ceiling: melody-contour readout from SAME z0 of full mixes.

Linear (Conv1d over frames = full-width linear with +-ctx frame context) and small
MLP readouts, per-frame soft-CE with class weights (pedal dominates — spec S0),
ARTIST-disjoint splits (no artist in both train and test). Noise arm: t-conditioned
model on z_t = (1-t) z0 + t eps (RF convention, matches latch/train_latch.py).

Run (SAO venv, GPU, under .gpu.lock):
  .venv/bin/python train_readout.py --variant lin_ctx0|lin_ctx1|lin_ctx2|mlp_ctx1|mlp_ctx2
                                    [--target y8|y14] [--noise] [--epochs N]
Appends one row per run to results.json (experiment log — no silent retries).
"""
import argparse, json, math, os, time
os.environ.setdefault('FLASH_ATTENTION_TRITON_AMD_ENABLE', 'FALSE')
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = os.path.join(HERE, 'targets')
LATENTS = '/home/kim/Projects/latents_sa3'
RESULTS = os.path.join(HERE, 'results.json')
SPLITS = os.path.join(HERE, 'splits.json')
N_FRAMES = 4096
FOLD_NAMES = ['rest', 'pedal', 'm1', 'm2', 'm3', 'm5', 'm7', 'm12']
DIR_NAMES = ['rest', 'pedal', '+1', '-1', '+2', '-2', '+3', '-3',
             '+5', '-5', '+7', '-7', '+12', '-12']


# ------------------------------------------------------------------ splits
def make_splits(ids, seed=0):
    """Artist-disjoint file split ~80/10/10 by file count (greedy largest-first
    into the currently-lightest bucket, respecting target ratios)."""
    import collections
    art = {}
    for fid in ids:
        a = None
        p = os.path.join(LATENTS, fid + '.json')
        if os.path.exists(p):
            try:
                a = json.load(open(p)).get('track_metadata_artist')
            except Exception:
                a = None
        art[fid] = a if a else f'__solo_{fid}'
    groups = collections.defaultdict(list)
    for fid, a in art.items():
        groups[a].append(fid)
    order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    rng = np.random.RandomState(seed)
    order = ([order[0]] + [order[1 + i] for i in rng.permutation(len(order) - 1)]
             ) if len(order) > 1 else order
    tgt = {'train': 0.8, 'val': 0.1, 'test': 0.1}
    buckets = {k: [] for k in tgt}
    for a, fs in order:
        k = min(tgt, key=lambda k: len(buckets[k]) / (tgt[k] * len(ids) + 1e-9))
        buckets[k].extend(fs)
    n_art = {k: len({art[f] for f in v}) for k, v in buckets.items()}
    meta = dict(split_type='artist-disjoint',
                n_artists=len(groups),
                n_files={k: len(v) for k, v in buckets.items()},
                n_artists_per_split=n_art,
                n_missing_artist=sum(1 for a in art.values()
                                     if a.startswith('__solo_')))
    return buckets, meta


def load_split():
    ids = sorted(f[:-4] for f in os.listdir(TARGETS) if f.endswith('.npz'))
    if os.path.exists(SPLITS):
        d = json.load(open(SPLITS))
        return {k: d[k] for k in ('train', 'val', 'test')}, d['meta']
    buckets, meta = make_splits(ids)
    json.dump({**buckets, 'meta': meta}, open(SPLITS, 'w'), indent=1)
    return buckets, meta


# ------------------------------------------------------------------ data
def load_arrays(ids, ykey):
    X = np.empty((len(ids), 256, N_FRAMES), np.float16)
    C = 8 if ykey == 'y8' else 14
    Y = np.empty((len(ids), N_FRAMES, C), np.float16)
    for i, fid in enumerate(ids):
        z = np.load(os.path.join(LATENTS, fid + '.npy'))
        if z.ndim == 3:
            z = z[0]
        X[i] = z[:, :N_FRAMES]
        Y[i] = np.load(os.path.join(TARGETS, fid + '.npz'))[ykey]
    return X, Y


# ------------------------------------------------------------------ model
class TEmbed(nn.Module):
    def __init__(self, dim, hidden):
        super().__init__()
        self.dim = dim
        self.proj = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(),
                                  nn.Linear(hidden, hidden))
    def forward(self, t):                      # t (B,)
        half = self.dim // 2
        freqs = torch.exp(torch.linspace(math.log(1.0), math.log(1000.0), half,
                                         device=t.device))
        ang = t[:, None] * freqs[None, :]
        emb = torch.cat([torch.sin(ang), torch.cos(ang)], dim=1)
        return self.proj(emb)                  # (B, hidden)


class Readout(nn.Module):
    def __init__(self, arch, ctx, n_cls, hidden=512, t_cond=False):
        super().__init__()
        self.arch, self.ctx, self.n_cls, self.t_cond = arch, ctx, n_cls, t_cond
        k = 2 * ctx + 1
        if arch == 'lin':
            self.head = nn.Conv1d(256, n_cls, k, padding=ctx)
            if t_cond:
                self.temb = TEmbed(64, n_cls)
        else:
            self.c1 = nn.Conv1d(256, hidden, k, padding=ctx)
            if arch == 'mlp2':                  # deeper capacity probe
                self.mid = nn.Conv1d(hidden, hidden, 1)
            self.c2 = nn.Conv1d(hidden, n_cls, 1)
            if t_cond:
                self.temb = TEmbed(64, hidden)
    def forward(self, x, t=None):              # x (B,256,T)
        if self.arch == 'lin':
            out = self.head(x)
            if self.t_cond and t is not None:
                out = out + self.temb(t)[:, :, None]
            return out
        h = self.c1(x)
        if self.t_cond and t is not None:
            h = h + self.temb(t)[:, :, None]
        h = F.gelu(h)
        if self.arch == 'mlp2':
            h = F.gelu(self.mid(h))
        return self.c2(h)


# ------------------------------------------------------------------ metrics
def frame_metrics(logits, ysoft, n_cls):
    """Pooled hard-label metrics: label = argmax(soft target)."""
    pred = logits.argmax(1).reshape(-1).cpu().numpy()
    yl = ysoft.argmax(-1).reshape(-1).cpu().numpy()
    conf = (ysoft.max(-1).values.reshape(-1) >= 0.6).cpu().numpy()
    cm = np.zeros((n_cls, n_cls), np.int64)
    np.add.at(cm, (yl, pred), 1)
    return cm, pred[conf], yl[conf]


def scores_from_cm(cm):
    tp = np.diag(cm).astype(float)
    sup = cm.sum(1)
    prd = cm.sum(0)
    rec = np.where(sup > 0, tp / np.maximum(sup, 1), np.nan)
    prec = np.where(prd > 0, tp / np.maximum(prd, 1), 0.0)
    f1 = np.where(np.isnan(rec), np.nan,
                  2 * prec * rec / np.maximum(prec + rec, 1e-9))
    return dict(balanced_acc=float(np.nanmean(rec)),
                macro_f1=float(np.nanmean(f1)),
                per_class_f1=[None if np.isnan(v) else round(float(v), 4) for v in f1],
                per_class_recall=[None if np.isnan(v) else round(float(v), 4) for v in rec],
                support=[int(s) for s in sup])


@torch.no_grad()
def evaluate(model, X, Y, dev, norm, n_cls, t_val=None, bs=16, seed=1234):
    model.eval()
    cm = np.zeros((n_cls, n_cls), np.int64)
    cmc = np.zeros((n_cls, n_cls), np.int64)
    g = torch.Generator(device='cpu').manual_seed(seed)
    for i in range(0, len(X), bs):
        x = torch.from_numpy(X[i:i + bs].astype(np.float32)).to(dev)
        y = torch.from_numpy(Y[i:i + bs].astype(np.float32)).to(dev)
        x = (x - norm[0]) / norm[1]
        t = None
        if t_val is not None:
            eps = torch.randn(x.shape, generator=g).to(dev)
            x = (1 - t_val) * x + t_val * eps
            t = torch.full((x.shape[0],), t_val, device=dev)
        logits = model(x, t)
        pred = logits.argmax(1).reshape(-1).cpu().numpy()
        yl = y.argmax(-1).reshape(-1).cpu().numpy()
        np.add.at(cm, (yl, pred), 1)
        m = (y.max(-1).values.reshape(-1) >= 0.6).cpu().numpy()
        np.add.at(cmc, (yl[m], pred[m]), 1)
    return cm, cmc


# ------------------------------------------------------------------ train
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', required=True)     # lin_ctx0 / mlp_ctx2 ...
    ap.add_argument('--target', default='y8', choices=['y8', 'y14'])
    ap.add_argument('--noise', action='store_true', help='t-conditioned on z_t')
    ap.add_argument('--epochs', type=int, default=40)
    ap.add_argument('--lr', type=float, default=None)
    ap.add_argument('--bs', type=int, default=8)
    ap.add_argument('--patience', type=int, default=8)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--init_from', default=None)
    ap.add_argument('--hidden', type=int, default=512)
    ap.add_argument('--shift', type=int, default=0,
                    help='alignment diagnostic: roll targets by N frames '
                         '(+ = melody targets later vs latent)')
    args = ap.parse_args()
    arch, ctxs = args.variant.split('_')
    ctx = int(ctxs.replace('ctx', ''))
    names = FOLD_NAMES if args.target == 'y8' else DIR_NAMES
    n_cls = len(names)
    lr = args.lr or (3e-3 if arch == 'lin' else 1e-3)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    dev = 'cuda'

    splits, smeta = load_split()
    print('split:', smeta)
    t0 = time.time()
    Xtr, Ytr = load_arrays(splits['train'], args.target)
    Xva, Yva = load_arrays(splits['val'], args.target)
    Xte, Yte = load_arrays(splits['test'], args.target)
    print(f'loaded {Xtr.shape} train in {time.time()-t0:.0f}s')
    if args.shift:
        for Y in (Ytr, Yva, Yte):
            Y[:] = np.roll(Y, args.shift, axis=1)
        print(f'targets rolled by {args.shift} frames')

    # normalization: per-channel mean/std on train (saved into checkpoint)
    sub = Xtr[::4].astype(np.float32)
    mu = sub.mean(axis=(0, 2))
    sd = sub.std(axis=(0, 2)) + 1e-6
    norm = (torch.tensor(mu, device=dev)[None, :, None],
            torch.tensor(sd, device=dev)[None, :, None])

    # class weights: inverse sqrt of train soft-mass
    mass = Ytr.astype(np.float32).sum(axis=(0, 1))
    freq = mass / mass.sum()
    cw = (1.0 / np.maximum(freq, 1e-6)) ** 0.5
    cw = cw / cw.mean()
    print('class freq:', {n: round(float(f), 5) for n, f in zip(names, freq)})
    cw_t = torch.tensor(cw, dtype=torch.float32, device=dev)

    model = Readout(arch, ctx, n_cls, hidden=args.hidden, t_cond=args.noise).to(dev)
    if args.init_from:
        sd0 = torch.load(args.init_from, map_location=dev, weights_only=False)
        missing = model.load_state_dict(sd0['model'], strict=False)
        print('init_from:', args.init_from, missing)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    nb = math.ceil(len(Xtr) / args.bs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs * nb)

    def loss_fn(logits, y, t=None):
        logp = F.log_softmax(logits, dim=1)             # (B,C,T)
        yt = y.permute(0, 2, 1)                         # (B,C,T)
        w = cw_t[None, :, None]
        num = -(w * yt * logp).sum()
        den = (w * yt).sum().clamp_min(1e-6)
        return num / den

    best = dict(val_bacc=-1.0, epoch=-1)
    ckpt_path = os.path.join(HERE, f'readout_{args.variant}_{args.target}'
                             + ('_noise' if args.noise else '')
                             + (f'_shift{args.shift}' if args.shift else '')
                             + '.pt')
    bad = 0
    for ep in range(args.epochs):
        model.train()
        perm = np.random.permutation(len(Xtr))
        tl = 0.0
        for bi in range(nb):
            idx = np.sort(perm[bi * args.bs:(bi + 1) * args.bs])
            x = torch.from_numpy(Xtr[idx].astype(np.float32)).to(dev)
            y = torch.from_numpy(Ytr[idx].astype(np.float32)).to(dev)
            x = (x - norm[0]) / norm[1]
            t = None
            if args.noise:
                t = torch.rand(x.shape[0], device=dev) * 0.93 + 0.02
                x = (1 - t[:, None, None]) * x + t[:, None, None] * torch.randn_like(x)
            logits = model(x, t)
            loss = loss_fn(logits, y, t)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            tl += loss.item()
        tv = 0.35 if args.noise else None       # rep mid-noise point for val sel
        cm, _ = evaluate(model, Xva, Yva, dev, norm, n_cls, t_val=tv)
        sc = scores_from_cm(cm)
        print(f'ep{ep} loss {tl/nb:.4f} val bacc {sc["balanced_acc"]:.4f} '
              f'macroF1 {sc["macro_f1"]:.4f}', flush=True)
        if sc['balanced_acc'] > best['val_bacc']:
            best = dict(val_bacc=sc['balanced_acc'], val_macro_f1=sc['macro_f1'],
                        epoch=ep)
            bad = 0
            torch.save(dict(
                model=model.state_dict(),
                arch=arch, ctx=ctx, n_cls=n_cls, hidden=args.hidden,
                class_names=names,
                target=args.target, t_conditioned=args.noise,
                norm_mu=mu.tolist(), norm_sd=sd.tolist(),
                norm_note='x_norm=(z0-mu)/sd per-channel; train-split stats',
                frame_rate_hz=44100 / 4096, frame_dur_s=4096 / 44100,
                noise_convention='z_t=(1-t)*z0_norm + t*eps  (RF, latch/train_latch.py)',
                class_freq_train={n: float(f) for n, f in zip(names, freq)},
                class_weights=cw.tolist(),
                slider_metadata=dict(
                    note='per-class prob in [0,1]; guidance target = class prob; '
                         'typical operating range from train priors below',
                    class_prior={n: float(f) for n, f in zip(names, freq)},
                    suggested_slider_range=[0.0, 1.0]),
                split_meta=smeta, variant=args.variant, lr=lr, seed=args.seed,
                spec='docs/superpowers/specs/2026-07-22-melodic-latch-film.md S0/S1/S8',
            ), ckpt_path)
        else:
            bad += 1
            if bad >= args.patience:
                print(f'early stop at ep{ep}')
                break

    # reload best, final eval on TEST
    sd0 = torch.load(ckpt_path, map_location=dev, weights_only=False)
    model.load_state_dict(sd0['model'])
    row = dict(variant=args.variant, target=args.target, noise=args.noise,
               lr=lr, seed=args.seed, best_epoch=best['epoch'],
               val_bacc=round(best['val_bacc'], 4), shift=args.shift,
               split=smeta['split_type'], ckpt=os.path.basename(ckpt_path),
               time_s=round(time.time() - t0))
    if args.noise:
        curve = {}
        for tv in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            cm, cmc = evaluate(model, Xte, Yte, dev, norm, n_cls,
                               t_val=(tv if tv > 0 else None))
            sc = scores_from_cm(cm)
            curve[str(tv)] = dict(balanced_acc=round(sc['balanced_acc'], 4),
                                  macro_f1=round(sc['macro_f1'], 4))
            print(f't={tv}: bacc {sc["balanced_acc"]:.4f} F1 {sc["macro_f1"]:.4f}',
                  flush=True)
        row['t_curve'] = curve
    else:
        cm, cmc = evaluate(model, Xte, Yte, dev, norm, n_cls)
        sc = scores_from_cm(cm)
        scc = scores_from_cm(cmc)
        row.update(test_all=sc, test_confident=dict(
                       balanced_acc=round(scc['balanced_acc'], 4),
                       macro_f1=round(scc['macro_f1'], 4)),
                   confusion=cm.tolist(), class_names=names)
        print('TEST bacc', round(sc['balanced_acc'], 4),
              'macroF1', round(sc['macro_f1'], 4))
        print('per-class F1', dict(zip(names, sc['per_class_f1'])))

    log = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {'runs': []}
    log['runs'].append(row)
    json.dump(log, open(RESULTS, 'w'), indent=1)
    print('logged ->', RESULTS)


if __name__ == '__main__':
    main()
