#!/usr/bin/env python
"""extract_acts.py — GPU half of the Head A ACTIVATION ceiling study.

Adaptation of latch/extract_layer_activations.py (night-shift task #25 infra —
reused, not reinvented): same conditioning assembly, same inpaint-zeros
convention, same RF noising x_t=(1-t)*z0 + t*eps with fixed eps_seed=7, same
post-block residual-stream hook sites (ContinuousTransformer .layers).

Differences vs the 2026-07-08 run:
  * crops come from head_a_ceiling's artist-disjoint splits.json (VERBATIM
    reuse — sampled within buckets, so train/val/test membership is preserved);
  * per crop ONE contiguous 1024-frame window (not a sparse 96-frame grid) —
    enables ctx convs, the GRU fallback and acceptance decode;
  * taps = 12 layers {0,2,...,22} (not all 24), t in {0.2,0.5,0.8};
  * output = per-(t,layer) memmap packs (N,1024,1536) fp16 + the y8/y14 target
    windows, so readout training never touches the DiT again.

Forward is over the FULL 4096-frame latent (crop's real context, as the prior
extractor did); only the window rows are kept.

Run (SAO venv, GPU, under .gpu.lock):
  .venv/bin/python extract_acts.py [--n-train 400 --n-val 50 --n-test 50]
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import argparse, json, sys, time
from pathlib import Path

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
CEIL = os.path.join(os.path.dirname(HERE), 'head_a_ceiling')
LATENTS = '/home/kim/Projects/latents_sa3'
OUT = Path(os.environ.get('HEADA2_ACTS_DIR',
                          '/run/media/kim/Mantu/sa3_lora_runs/head_a_ceiling_act'))

TAPS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
TS = [0.2, 0.5, 0.8]
WIN = 1024
T_FULL = 4096
D = 1536
EPS_SEED = 7


def tkey(t):
    return f"t{int(round(t * 100)):03d}"


def get_blocks(model):
    dit = model.dit
    for name, mod in dit.named_modules():
        if name.endswith("transformer") and hasattr(mod, "layers"):
            return list(mod.layers)
    raise RuntimeError("could not locate ContinuousTransformer with .layers")


def pick_crops(n_train, n_val, n_test, seed=42):
    """Sample within head_a_ceiling's artist-disjoint buckets (split reuse
    VERBATIM: membership comes from splits.json, never recomputed)."""
    sp = json.load(open(os.path.join(CEIL, 'splits.json')))
    rng = np.random.default_rng(seed)
    picked = {}
    for split, n in (('train', n_train), ('val', n_val), ('test', n_test)):
        ids = [f for f in sp[split]
               if os.path.exists(os.path.join(CEIL, 'targets', f + '.npz'))
               and os.path.exists(os.path.join(LATENTS, f + '.npy'))]
        sel = rng.choice(len(ids), size=min(n, len(ids)), replace=False)
        picked[split] = sorted(ids[i] for i in sel)
    order = picked['train'] + picked['val'] + picked['test']
    starts = rng.integers(0, T_FULL - WIN + 1, size=len(order))
    # clamp window to actual latent length (header-only mmap read)
    for i, fid in enumerate(order):
        z = np.load(os.path.join(LATENTS, fid + '.npy'), mmap_mode='r')
        T = z.shape[-1]
        starts[i] = min(int(starts[i]), max(0, min(T, T_FULL) - WIN))
    crops = [dict(idx=i, id=fid, start=int(starts[i]),
                  split=('train' if i < len(picked['train'])
                         else 'val' if i < len(picked['train']) + len(picked['val'])
                         else 'test'))
             for i, fid in enumerate(order)]
    return crops, {k: len(v) for k, v in picked.items()}


def extract_one(model, cdm, blocks, z, prompt, seconds_total, start):
    """One crop: 3 forwards (one per t), capture 12 taps x window frames."""
    device = next(model.model.model.parameters()).device
    mdtype = next(model.model.model.parameters()).dtype

    conditioning = [{"prompt": prompt, "seconds_total": seconds_total}]
    tensors = cdm.conditioner(conditioning, str(device))
    T = z.shape[-1]
    tensors["inpaint_mask"] = [torch.zeros((1, 1, T), device=device)]
    tensors["inpaint_masked_input"] = [torch.zeros_like(z, device=device)]
    cond_inputs = cdm.get_conditioning_inputs(tensors)
    cond_inputs = {k: (v.type(mdtype) if torch.is_tensor(v) else v)
                   for k, v in cond_inputs.items()}

    grabbed = {}
    hooks = []
    tapset = set(TAPS)

    def mk(i):
        def hook(_m, _inp, out):
            o = out[0] if isinstance(out, tuple) else out
            o = o[0, -T:, :]                       # drop prepended memory tokens
            grabbed[i] = o[start:start + WIN].detach().to(torch.float16).cpu()
        return hook

    for i, b in enumerate(blocks):
        if i in tapset:
            hooks.append(b.register_forward_hook(mk(i)))

    out = {}
    try:
        g = torch.Generator(device="cpu").manual_seed(EPS_SEED)
        eps = torch.randn(z.shape, generator=g).to(device, mdtype)
        zd = z.to(device, mdtype)
        for t in TS:
            x_t = (1 - t) * zd + t * eps
            tt = torch.full((1,), float(t), device=device, dtype=mdtype)
            grabbed.clear()
            with torch.no_grad():
                cdm.model(x_t, tt, **cond_inputs)
            out[t] = {L: grabbed[L].numpy() for L in TAPS}
    finally:
        for h in hooks:
            h.remove()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-train', type=int, default=400)
    ap.add_argument('--n-val', type=int, default=50)
    ap.add_argument('--n-test', type=int, default=50)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    crops_path = OUT / 'crops.json'
    if crops_path.exists():
        cj = json.load(open(crops_path))
        crops = cj['crops']
        print(f'[resume] crops.json exists: {len(crops)} crops')
    else:
        crops, counts = pick_crops(args.n_train, args.n_val, args.n_test)
        cj = dict(crops=crops, counts=counts, taps=TAPS, ts=TS, win=WIN,
                  d_model=D, eps_seed=EPS_SEED,
                  model='medium-base (no adapter)',
                  noise='x_t=(1-t)*z0_raw + t*eps (RF, raw-latent scale, '
                        'latch/extract_layer_activations.py convention)',
                  split_source='head_a_ceiling/splits.json (artist-disjoint, '
                               'sampled within buckets)')
        json.dump(cj, open(crops_path, 'w'), indent=1)
    N = len(crops)

    # target windows (idempotent, cheap)
    ywin_path = OUT / 'y_windows.npz'
    if not ywin_path.exists():
        Y8 = np.empty((N, WIN, 8), np.float16)
        Y14 = np.empty((N, WIN, 14), np.float16)
        for c in crops:
            d = np.load(os.path.join(CEIL, 'targets', c['id'] + '.npz'))
            s = c['start']
            Y8[c['idx']] = d['y8'][s:s + WIN]
            Y14[c['idx']] = d['y14'][s:s + WIN]
        np.savez(ywin_path, y8=Y8, y14=Y14)
        print('[targets] y_windows.npz written')

    # memmaps
    mm = {}
    for t in TS:
        for L in TAPS:
            p = OUT / f'acts_{tkey(t)}_L{L:02d}.npy'
            if p.exists():
                mm[(t, L)] = np.lib.format.open_memmap(p, mode='r+')
            else:
                mm[(t, L)] = np.lib.format.open_memmap(
                    p, mode='w+', dtype=np.float16, shape=(N, WIN, D))

    prog_path = OUT / 'progress.json'
    done = set(json.load(open(prog_path))['done']) if prog_path.exists() else set()
    todo = [c for c in crops if c['idx'] not in done]
    print(f'[extract] {len(todo)}/{N} crops to do')
    if not todo:
        print('[extract] nothing to do')
        return

    from stable_audio_3 import StableAudioModel
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    blocks = get_blocks(model)
    assert len(blocks) == 24, f'expected 24 blocks, got {len(blocks)}'

    t_all = time.time()
    for k, c in enumerate(todo):
        z = torch.tensor(np.load(os.path.join(LATENTS, c['id'] + '.npy'))).float()
        if z.dim() == 2:
            z = z.unsqueeze(0)
        meta = json.load(open(os.path.join(LATENTS, c['id'] + '.json')))
        t0 = time.time()
        acts = extract_one(model, cdm, blocks, z, meta.get('prompt', ''),
                           float(meta.get('seconds_total',
                                          z.shape[-1] / 10.7666)), c['start'])
        for t in TS:
            for L in TAPS:
                mm[(t, L)][c['idx']] = acts[t][L]
        done.add(c['idx'])
        if k % 5 == 0 or k == len(todo) - 1:
            json.dump({'done': sorted(done)}, open(prog_path, 'w'))
            el = time.time() - t_all
            print(f'[{k+1}/{len(todo)}] {c["id"]} {time.time()-t0:.1f}s '
                  f'(elapsed {el/60:.1f}m, eta {el/(k+1)*(len(todo)-k-1)/60:.0f}m)',
                  flush=True)
    for v in mm.values():
        v.flush()
    json.dump({'done': sorted(done)}, open(prog_path, 'w'))
    print(f'[done] {len(todo)} crops in {(time.time()-t_all)/60:.1f} min -> {OUT}',
          flush=True)


if __name__ == '__main__':
    main()
    # ROCm/torch teardown aborts with heap corruption after successful runs
    # (smoke 2026-07-23: 'corrupted double-linked list' AFTER [done]; data
    # verified intact). All outputs are flushed above — skip teardown.
    sys.stdout.flush()
    os._exit(0)
