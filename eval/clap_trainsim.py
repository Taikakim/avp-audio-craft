#!/usr/bin/env python
"""Training-set SIMILARITY as a candidate feature for the 4-vs-5 blind band.

Every feature in eval/clip_metrics.db is ABSOLUTE -- a property of the clip alone. The
enjoyment data says none of them separates a 4 from a 5: every 4->5 Cohen's d sits inside its
own CI, and the 5 bucket is NARROWER than the 4 bucket (so it is not two routes cancelling in
the mean). A RELATIONAL measure -- how close the clip sits to the training distribution -- is
not constrained to correlate with any absolute feature, which is why it is one of the few
candidates that could live in that blind band at all.

Note this is NOT the existing `clap` column. That one scores clip-vs-its-text-prompt. This
scores clip-vs-the-goa-training-corpus in CLAP AUDIO embedding space.

Falsifiable prediction that separates the hypothesis from "5s are simply better": proximity to
the training distribution should be NON-MONOTONIC at the top. A clip very close to training
audio is a near-copy and should read as boilerplate, so 5s should occupy a BAND, not the
maximum. A plain quality feature would rise monotonically instead.

Embeddings are PERSISTED (eval/clap_score.py computes and discards them, so every question of
this kind has paid to recompute them from scratch).

Run with sat-venv -- laion_clap lives there and nowhere else:
  stable-audio-tools/sat-venv/bin/python eval/clap_trainsim.py --n-ref 400 --device cuda
"""
import argparse, json, os, random, subprocess, sys, sqlite3
from pathlib import Path
import numpy as np

CLIPS = Path('/run/media/kim/Mantu/sa3_lora_runs/model_matrix')
GOA   = Path('/run/media/kim/Mantu/ai-music/Goa_Separated')
CACHE = Path.home() / '.cache/clap_emb'
SR    = 48000   # laion CLAP's native rate

def decode(path, seconds=20.0, offset=None):
    """ffmpeg -> mono float32 @48k. Used for BOTH .m4a and .ogg so no torchaudio/soundfile
    backend difference can silently change the embedding distribution between the two arms."""
    cmd = ['ffmpeg', '-v', 'quiet', '-nostdin']
    if offset: cmd += ['-ss', str(offset)]
    cmd += ['-i', str(path), '-t', str(seconds), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=120).stdout
    except Exception:
        return None
    a = np.frombuffer(raw, dtype=np.float32)
    if a.size < SR * 2: return None
    need = int(SR * seconds)
    return np.pad(a, (0, max(0, need - a.size)))[:need].copy()

def duration(path):
    try:
        out = subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration',
                              '-of','csv=p=0',str(path)], capture_output=True, timeout=60).stdout
        return float(out.strip())
    except Exception:
        return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-ref', type=int, default=400, help='training tracks to sample')
    ap.add_argument('--crops-per-track', type=int, default=2)
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--seconds', type=float, default=20.0, help='must match the rated clips')
    ap.add_argument('--ratings', default='eval/ratings_export_2026-09-07.jsonl')
    ap.add_argument('--out', default=str(CACHE))
    a = ap.parse_args()
    random.seed(11)
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)

    rated = {}
    for line in open(a.ratings):
        d = json.loads(line)
        if d.get('type') == 'enjoyment' and (CLIPS / d['file']).exists():
            rated.setdefault(d['file'], []).append(int(d['rating']))
    rated = {k: float(np.mean(v)) for k, v in rated.items()}
    print(f'rated clips present on disk: {len(rated)}', flush=True)

    mixes = sorted(GOA.glob('*/full_mix.ogg'))
    random.shuffle(mixes)
    mixes = mixes[:a.n_ref]
    print(f'reference tracks: {len(mixes)}', flush=True)

    argv = sys.argv; sys.argv = sys.argv[:1]      # laion_clap parses argv at import
    import torch, laion_clap
    sys.argv = argv
    model = laion_clap.CLAP_Module(enable_fusion=False, device=a.device)
    # Both patches are lifted verbatim in intent from eval/clap_score.py -- this checkpoint
    # cannot be loaded on this stack without them, and rediscovering that costs a run each time:
    #  - torch 2.6+ flipped weights_only to True; the official laion release carries a numpy
    #    scalar global the safe unpickler blocks.
    #  - newer transformers dropped the `text_branch.embeddings.position_ids` buffer the
    #    checkpoint still ships, so a strict load_state_dict rejects it. Both are benign buffers.
    _load = torch.load
    torch.load = lambda *A, **K: _load(*A, **{**K, 'weights_only': False})
    _lsd = model.model.load_state_dict
    model.model.load_state_dict = lambda sd, strict=True: _lsd(sd, strict=False)
    try:
        model.load_ckpt(model_id=1)
    finally:
        torch.load = _load
        model.model.load_state_dict = _lsd
    model.eval()

    def embed(batch):
        with torch.no_grad():
            x = torch.from_numpy(np.stack(batch)).float()
            if a.device != 'cpu': x = x.to(a.device)
            e = model.get_audio_embedding_from_data(x=x, use_tensor=True)
        e = e.detach().cpu().numpy() if hasattr(e, 'detach') else np.asarray(e)
        return e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)

    def run(items, loader, tag, bs=16):
        keys, vecs, buf, bk = [], [], [], []
        for i, it in enumerate(items):
            w = loader(it)
            if w is None: continue
            buf.append(w); bk.append(it)
            if len(buf) == bs:
                vecs.append(embed(buf)); keys += bk; buf, bk = [], []
                if len(keys) % 320 == 0: print(f'  {tag} {len(keys)}/{len(items)}', flush=True)
        if buf: vecs.append(embed(buf)); keys += bk
        return keys, (np.concatenate(vecs) if vecs else np.zeros((0, 512), np.float32))

    ref_items = []
    for m in mixes:
        dur = duration(m)
        for _ in range(a.crops_per_track):
            off = random.uniform(0, max(0.0, dur - a.seconds)) if dur > a.seconds + 1 else 0.0
            ref_items.append((m, off))
    rk, R = run(ref_items, lambda t: decode(t[0], a.seconds, t[1]), 'ref')
    print(f'reference embeddings: {R.shape}', flush=True)
    np.savez_compressed(outdir / 'ref_goa.npz', emb=R,
                        keys=np.array([f'{p}@{o:.1f}' for p, o in rk]))

    files = sorted(rated)
    ck, C = run(files, lambda f: decode(CLIPS / f, a.seconds, None), 'clip')
    print(f'clip embeddings: {C.shape}', flush=True)
    np.savez_compressed(outdir / 'clips_rated.npz', emb=C, keys=np.array(ck),
                        rating=np.array([rated[f] for f in ck], dtype=np.float32))

    S = C @ R.T                                   # cosine, both L2-normalised
    cent = R.mean(0); cent /= np.linalg.norm(cent) + 1e-9
    out = {'file': ck, 'rating': [rated[f] for f in ck],
           'knn10': np.sort(S, axis=1)[:, -10:].mean(1).tolist(),
           'knn1':  S.max(1).tolist(),
           'centroid': (C @ cent).tolist()}
    json.dump(out, open('eval/clap_trainsim_2026-09-07.json', 'w'))
    print('wrote eval/clap_trainsim_2026-09-07.json', flush=True)
    print('SCAN_DONE', flush=True)

if __name__ == '__main__':
    main()
