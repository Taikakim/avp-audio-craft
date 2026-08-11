#!/usr/bin/env python
"""train_readout_act.py — melody-contour readout from DiT ACTIVATIONS, one
(layer, t) cell per invocation; trains linear + small-MLP (same family as
head_a_ceiling/train_readout.py — its loss / class-weight / metric code is
IMPORTED, not re-implemented, so numbers are directly comparable).

Input: memmap packs written by extract_acts.py (N,1024,1536) fp16 at fixed
noise level t (activations already carry the noise — no augmentation here,
no t-conditioning needed).

Run (SAO venv, GPU, under .gpu.lock):
  .venv/bin/python train_readout_act.py --t 0.5 --layer 12 [--target y8]
Appends one row per arch to results.json.
"""
import argparse, json, math, os, sys, time
os.environ.setdefault('FLASH_ATTENTION_TRITON_AMD_ENABLE', 'FALSE')
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
CEIL = os.path.join(os.path.dirname(HERE), 'head_a_ceiling')
sys.path.insert(0, CEIL)
from train_readout import scores_from_cm, FOLD_NAMES, DIR_NAMES  # noqa: E402

ACTS = os.environ.get('HEADA2_ACTS_DIR',
                      '/run/media/kim/Mantu/sa3_lora_runs/head_a_ceiling_act')
RESULTS = os.environ.get('HEADA2_RESULTS', os.path.join(HERE, 'results.json'))
D = 1536
WIN = 1024


def tkey(t):
    return f"t{int(round(t * 100)):03d}"


class ReadoutAct(nn.Module):
    """Same shapes as head_a_ceiling Readout (lin: full-width conv; mlp:
    conv->GELU->1x1), input width 1536 instead of 256, ctx=1 (k=3)."""
    def __init__(self, arch, n_cls, ctx=1, hidden=512):
        super().__init__()
        self.arch, self.ctx, self.n_cls = arch, ctx, n_cls
        k = 2 * ctx + 1
        if arch == 'lin':
            self.head = nn.Conv1d(D, n_cls, k, padding=ctx)
        else:
            self.c1 = nn.Conv1d(D, hidden, k, padding=ctx)
            self.c2 = nn.Conv1d(hidden, n_cls, 1)

    def forward(self, x):                      # x (B,1536,T)
        if self.arch == 'lin':
            return self.head(x)
        return self.c2(F.gelu(self.c1(x)))


def load_cell(t, layer, ykey):
    cj = json.load(open(os.path.join(ACTS, 'crops.json')))
    crops = cj['crops']
    X = np.asarray(np.lib.format.open_memmap(
        os.path.join(ACTS, f'acts_{tkey(t)}_L{layer:02d}.npy'), mode='r'))
    Y = np.load(os.path.join(ACTS, 'y_windows.npz'))[ykey]
    idx = {s: [c['idx'] for c in crops if c['split'] == s]
           for s in ('train', 'val', 'test')}
    return {s: (X[i], Y[i]) for s, i in idx.items()}, cj


@torch.no_grad()
def evaluate(model, X, Y, dev, norm, n_cls, bs=16):
    model.eval()
    cm = np.zeros((n_cls, n_cls), np.int64)
    cmc = np.zeros((n_cls, n_cls), np.int64)
    for i in range(0, len(X), bs):
        x = torch.from_numpy(X[i:i + bs].astype(np.float32)).to(dev)
        x = x.permute(0, 2, 1)                       # (B,1536,T)
        x = (x - norm[0]) / norm[1]
        y = torch.from_numpy(Y[i:i + bs].astype(np.float32)).to(dev)
        pred = model(x).argmax(1).reshape(-1).cpu().numpy()
        yl = y.argmax(-1).reshape(-1).cpu().numpy()
        np.add.at(cm, (yl, pred), 1)
        m = (y.max(-1).values.reshape(-1) >= 0.6).cpu().numpy()
        np.add.at(cmc, (yl[m], pred[m]), 1)
    return cm, cmc


def train_arch(arch, data, names, args, dev):
    n_cls = len(names)
    (Xtr, Ytr), (Xva, Yva), (Xte, Yte) = data['train'], data['val'], data['test']
    lr = 3e-3 if arch == 'lin' else 1e-3
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    sub = Xtr[::8].astype(np.float32)                # (n,1024,1536)
    mu = sub.mean(axis=(0, 1))
    sd = sub.std(axis=(0, 1)) + 1e-6
    norm = (torch.tensor(mu, device=dev)[None, :, None],
            torch.tensor(sd, device=dev)[None, :, None])

    mass = Ytr.astype(np.float32).sum(axis=(0, 1))   # same formula as latent study
    freq = mass / mass.sum()
    cw = (1.0 / np.maximum(freq, 1e-6)) ** 0.5
    cw = cw / cw.mean()
    cw_t = torch.tensor(cw, dtype=torch.float32, device=dev)

    model = ReadoutAct(arch, n_cls).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    nb = math.ceil(len(Xtr) / args.bs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs * nb)

    def loss_fn(logits, y):
        logp = F.log_softmax(logits, dim=1)
        yt = y.permute(0, 2, 1)
        w = cw_t[None, :, None]
        num = -(w * yt * logp).sum()
        den = (w * yt).sum().clamp_min(1e-6)
        return num / den

    best = dict(val_bacc=-1.0, epoch=-1)
    os.makedirs(os.path.join(ACTS, 'ckpts'), exist_ok=True)
    ck = os.path.join(ACTS, 'ckpts',
                      f'act_{arch}_{tkey(args.t)}_L{args.layer:02d}_{args.target}.pt')
    bad = 0
    t0 = time.time()
    for ep in range(args.epochs):
        model.train()
        perm = np.random.permutation(len(Xtr))
        tl = 0.0
        for bi in range(nb):
            idx = np.sort(perm[bi * args.bs:(bi + 1) * args.bs])
            x = torch.from_numpy(Xtr[idx].astype(np.float32)).to(dev)
            x = x.permute(0, 2, 1)
            x = (x - norm[0]) / norm[1]
            y = torch.from_numpy(Ytr[idx].astype(np.float32)).to(dev)
            loss = loss_fn(model(x), y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            tl += loss.item()
        cm, _ = evaluate(model, Xva, Yva, dev, norm, n_cls)
        sc = scores_from_cm(cm)
        print(f'{arch} t={args.t} L{args.layer} ep{ep} loss {tl/nb:.4f} '
              f'val bacc {sc["balanced_acc"]:.4f} F1 {sc["macro_f1"]:.4f}',
              flush=True)
        if sc['balanced_acc'] > best['val_bacc']:
            best = dict(val_bacc=sc['balanced_acc'], val_macro_f1=sc['macro_f1'],
                        epoch=ep)
            bad = 0
            torch.save(dict(
                model=model.state_dict(), arch=arch, ctx=1, n_cls=n_cls,
                class_names=names, target=args.target,
                layer=args.layer, t=args.t, d_model=D,
                tap='DiT block output (post-block residual stream), '
                    'ContinuousTransformer.layers[layer], memory tokens dropped',
                norm_mu=mu.tolist(), norm_sd=sd.tolist(),
                norm_note='x_norm=(act-mu)/sd per-channel; train-split stats',
                frame_rate_hz=44100 / 4096, frame_dur_s=4096 / 44100,
                noise_convention='acts extracted at fixed t: '
                                 'x_t=(1-t)*z0_raw+t*eps, eps_seed=7',
                class_freq_train={n: float(f) for n, f in zip(names, freq)},
                class_weights=cw.tolist(),
                split_meta='head_a_ceiling/splits.json artist-disjoint, '
                           'subsampled (see crops.json)',
                spec='docs/superpowers/specs/2026-07-22-melodic-latch-film.md '
                     'Head A (activation-tap ceiling)',
            ), ck)
        else:
            bad += 1
            if bad >= args.patience:
                break

    sd0 = torch.load(ck, map_location=dev, weights_only=False)
    model.load_state_dict(sd0['model'])
    cm, cmc = evaluate(model, Xte, Yte, dev, norm, n_cls)
    sc = scores_from_cm(cm)
    scc = scores_from_cm(cmc)
    row = dict(kind='act', arch=arch, layer=args.layer, t=args.t,
               target=args.target, lr=lr, seed=args.seed,
               best_epoch=best['epoch'], val_bacc=round(best['val_bacc'], 4),
               test_all=sc,
               test_confident=dict(balanced_acc=round(scc['balanced_acc'], 4),
                                   macro_f1=round(scc['macro_f1'], 4)),
               confusion=cm.tolist(), class_names=names,
               ckpt=os.path.relpath(ck, ACTS), time_s=round(time.time() - t0))
    print(f'TEST {arch} t={args.t} L{args.layer}: '
          f'bacc {sc["balanced_acc"]:.4f} F1 {sc["macro_f1"]:.4f}')
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--t', type=float, required=True)
    ap.add_argument('--layer', type=int, required=True)
    ap.add_argument('--target', default='y8', choices=['y8', 'y14'])
    ap.add_argument('--archs', default='lin,mlp')
    ap.add_argument('--epochs', type=int, default=15)
    ap.add_argument('--patience', type=int, default=4)
    ap.add_argument('--bs', type=int, default=8)
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    dev = 'cuda'
    names = FOLD_NAMES if args.target == 'y8' else DIR_NAMES

    t0 = time.time()
    data, cj = load_cell(args.t, args.layer, args.target)
    print(f'cell t={args.t} L{args.layer}: '
          f'{ {s: v[0].shape for s, v in data.items()} } '
          f'loaded in {time.time()-t0:.0f}s', flush=True)

    rows = [train_arch(a, data, names, args, dev)
            for a in args.archs.split(',')]
    log = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {'runs': []}
    log['runs'].extend(rows)
    json.dump(log, open(RESULTS, 'w'), indent=1)
    print('logged ->', RESULTS)


if __name__ == '__main__':
    main()
    sys.stdout.flush()
    os._exit(0)      # skip ROCm/torch teardown (heap-corruption abort)
