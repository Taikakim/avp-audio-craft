#!/usr/bin/env python
"""seq_readout.py — temporal-integration check (design step 3): if the
per-frame ceiling is near-chance, test whether contour is present but needs
temporal integration: 2-layer bidirectional GRU over the best cell's
activations, same splits / loss / metrics as train_readout_act.py.

Run (SAO venv, GPU, under .gpu.lock):
  .venv/bin/python seq_readout.py --t 0.5 --layer 12 [--target y8]
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
sys.path.insert(0, HERE)
from train_readout import scores_from_cm, FOLD_NAMES, DIR_NAMES  # noqa: E402
from train_readout_act import load_cell, evaluate as _eval_frame  # noqa: E402

ACTS = os.environ.get('HEADA2_ACTS_DIR',
                      '/run/media/kim/Mantu/sa3_lora_runs/head_a_ceiling_act')
RESULTS = os.environ.get('HEADA2_RESULTS', os.path.join(HERE, 'results.json'))
D = 1536


class SeqReadout(nn.Module):
    def __init__(self, n_cls, hidden=256, proj=256):
        super().__init__()
        self.inp = nn.Linear(D, proj)
        self.gru = nn.GRU(proj, hidden, num_layers=2, batch_first=True,
                          bidirectional=True)
        self.head = nn.Linear(2 * hidden, n_cls)

    def forward(self, x):                    # x (B,1536,T) for interface parity
        h = self.inp(x.permute(0, 2, 1))     # (B,T,proj)
        h, _ = self.gru(h)
        return self.head(h).permute(0, 2, 1)  # (B,C,T)


@torch.no_grad()
def evaluate(model, X, Y, dev, norm, n_cls, bs=8):
    model.eval()
    cm = np.zeros((n_cls, n_cls), np.int64)
    for i in range(0, len(X), bs):
        x = torch.from_numpy(X[i:i + bs].astype(np.float32)).to(dev)
        x = (x.permute(0, 2, 1) - norm[0]) / norm[1]
        y = torch.from_numpy(Y[i:i + bs].astype(np.float32)).to(dev)
        pred = model(x).argmax(1).reshape(-1).cpu().numpy()
        yl = y.argmax(-1).reshape(-1).cpu().numpy()
        np.add.at(cm, (yl, pred), 1)
    return cm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--t', type=float, required=True)
    ap.add_argument('--layer', type=int, required=True)
    ap.add_argument('--target', default='y8', choices=['y8', 'y14'])
    ap.add_argument('--epochs', type=int, default=25)
    ap.add_argument('--patience', type=int, default=6)
    ap.add_argument('--bs', type=int, default=8)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    dev = 'cuda'
    names = FOLD_NAMES if args.target == 'y8' else DIR_NAMES
    n_cls = len(names)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    data, cj = load_cell(args.t, args.layer, args.target)
    (Xtr, Ytr), (Xva, Yva), (Xte, Yte) = data['train'], data['val'], data['test']

    sub = Xtr[::8].astype(np.float32)
    mu = sub.mean(axis=(0, 1))
    sd = sub.std(axis=(0, 1)) + 1e-6
    norm = (torch.tensor(mu, device=dev)[None, :, None],
            torch.tensor(sd, device=dev)[None, :, None])
    mass = Ytr.astype(np.float32).sum(axis=(0, 1))
    freq = mass / mass.sum()
    cw = (1.0 / np.maximum(freq, 1e-6)) ** 0.5
    cw = cw / cw.mean()
    cw_t = torch.tensor(cw, dtype=torch.float32, device=dev)

    model = SeqReadout(n_cls).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    nb = math.ceil(len(Xtr) / args.bs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs * nb)

    def loss_fn(logits, y):
        logp = F.log_softmax(logits, dim=1)
        yt = y.permute(0, 2, 1)
        w = cw_t[None, :, None]
        return -(w * yt * logp).sum() / (w * yt).sum().clamp_min(1e-6)

    os.makedirs(os.path.join(ACTS, 'ckpts'), exist_ok=True)
    ck = os.path.join(ACTS, 'ckpts',
                      f'act_gru_t{int(round(args.t*100)):03d}'
                      f'_L{args.layer:02d}_{args.target}.pt')
    best = dict(val_bacc=-1.0, epoch=-1)
    bad = 0
    t0 = time.time()
    for ep in range(args.epochs):
        model.train()
        perm = np.random.permutation(len(Xtr))
        tl = 0.0
        for bi in range(nb):
            idx = np.sort(perm[bi * args.bs:(bi + 1) * args.bs])
            x = torch.from_numpy(Xtr[idx].astype(np.float32)).to(dev)
            x = (x.permute(0, 2, 1) - norm[0]) / norm[1]
            y = torch.from_numpy(Ytr[idx].astype(np.float32)).to(dev)
            loss = loss_fn(model(x), y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            tl += loss.item()
        sc = scores_from_cm(evaluate(model, Xva, Yva, dev, norm, n_cls))
        print(f'gru ep{ep} loss {tl/nb:.4f} val bacc {sc["balanced_acc"]:.4f} '
              f'F1 {sc["macro_f1"]:.4f}', flush=True)
        if sc['balanced_acc'] > best['val_bacc']:
            best = dict(val_bacc=sc['balanced_acc'], epoch=ep)
            bad = 0
            torch.save(dict(model=model.state_dict(), arch='gru2_bidir',
                            n_cls=n_cls, class_names=names, target=args.target,
                            layer=args.layer, t=args.t, d_model=D,
                            norm_mu=mu.tolist(), norm_sd=sd.tolist(),
                            hidden=256, proj=256,
                            spec='2026-07-22-melodic-latch-film.md Head A '
                                 '(activation ceiling, sequence readout)'), ck)
        else:
            bad += 1
            if bad >= args.patience:
                break

    sd0 = torch.load(ck, map_location=dev, weights_only=False)
    model.load_state_dict(sd0['model'])
    sc = scores_from_cm(evaluate(model, Xte, Yte, dev, norm, n_cls))
    row = dict(kind='act_seq', arch='gru2_bidir', layer=args.layer, t=args.t,
               target=args.target, lr=args.lr, seed=args.seed,
               best_epoch=best['epoch'], val_bacc=round(best['val_bacc'], 4),
               test_all=sc, class_names=names,
               ckpt=os.path.relpath(ck, ACTS), time_s=round(time.time() - t0))
    log = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {'runs': []}
    log['runs'].append(row)
    json.dump(log, open(RESULTS, 'w'), indent=1)
    print(f'TEST gru t={args.t} L{args.layer}: bacc {sc["balanced_acc"]:.4f} '
          f'F1 {sc["macro_f1"]:.4f} -> logged')


if __name__ == '__main__':
    main()
    sys.stdout.flush()
    os._exit(0)      # skip ROCm/torch teardown (heap-corruption abort)
