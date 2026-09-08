#!/usr/bin/env python
"""Essentia-TensorFlow classifier/mood heads over the rated eval clips.

Motivation: the 4-vs-5 band is empty. All 14 clip_metrics features are flat there (every
4->5 Cohen's d inside its CI), and so is CLAP training-set similarity. Every one of those is
a LOW-LEVEL or global-embedding statistic. The essentia zoo carries heads trained on human
labels -- mood, emotion, and in particular the approachability/engagement regressions -- which
is a different kind of measurement and the obvious untried family.

Design: two backbones are computed ONCE per clip (discogs-effnet 1280-d, audioset-vggish
128-d) and every downstream head is a cheap 2D predict on top. The head list is not hardcoded
-- it is discovered from the .json metadata beside each .pb, which self-describes input name,
output name, input dim (1280 -> effnet, 128 -> vggish) and class labels. Adding a model to
models/essentia/ is therefore enough to include it.

mir venv only (essentia + TF live there, and mir/bin/python is the ffmpeg8-wrapping one):
  /home/kim/Projects/mir/mir/bin/python eval/essentia_heads.py
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np

CLIPS = Path('/run/media/kim/Mantu/sa3_lora_runs/model_matrix')
MROOT = Path('/home/kim/Projects/mir/models/essentia')
BACKBONE = {1280: 'effnet', 128: 'vggish'}
SKIP = {'audioset-vggish-3', 'discogs-effnet-bs64-1', 'discogs-effnet-bsdynamic-1'}

def decode(path, seconds, sr=16000):
    cmd = ['ffmpeg', '-v', 'quiet', '-nostdin', '-i', str(path), '-t', str(seconds),
           '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=120).stdout
    except Exception:
        return None
    a = np.frombuffer(raw, dtype=np.float32)
    return a.copy() if a.size >= sr * 2 else None

def discover():
    """Head list from the .json metadata, so this never drifts from what is on disk."""
    heads = []
    for j in sorted(MROOT.glob('*.json')):
        if j.stem in SKIP: continue
        pb = j.with_suffix('.pb')
        if not pb.exists(): continue
        try: m = json.load(open(j))
        except Exception: continue
        s = m.get('schema', {})
        ins, outs = s.get('inputs', []), s.get('outputs', [])
        if not ins or not outs: continue
        dim = (ins[0].get('shape') or [None])[-1]
        if dim not in BACKBONE: continue
        pred = next((o for o in outs if o.get('output_purpose') == 'predictions'), outs[0])
        heads.append({'name': j.stem, 'pb': str(pb), 'backbone': BACKBONE[dim],
                      'input': ins[0]['name'], 'output': pred['name'],
                      'classes': m.get('classes') or ['out']})
    return heads

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ratings', default='eval/ratings_export_2026-09-07.jsonl')
    ap.add_argument('--seconds', type=float, default=20.0)
    ap.add_argument('--out', default='eval/essentia_heads_2026-09-08.json')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    files = []
    seen = set()
    for line in open(a.ratings):
        d = json.loads(line)
        f = d.get('file')
        if not f or f in seen: continue
        if d.get('type') == 'enjoyment' and (CLIPS / f).exists():
            seen.add(f); files.append(f)
    if a.limit: files = files[:a.limit]
    print(f'clips: {len(files)}', flush=True)

    heads = discover()
    print(f'heads discovered: {len(heads)}', flush=True)
    for h in heads: print(f'  {h["name"]:44s} {h["backbone"]:7s} {len(h["classes"])} class(es)', flush=True)

    import essentia.standard as es
    emb = {
        'effnet': es.TensorflowPredictEffnetDiscogs(
            graphFilename=str(MROOT / 'discogs-effnet-bs64-1.pb'), output='PartitionedCall:1'),
        'vggish': es.TensorflowPredictVGGish(
            graphFilename=str(MROOT / 'audioset-vggish-3.pb'), output='model/vggish/embeddings'),
    }
    algs = {h['name']: es.TensorflowPredict2D(graphFilename=h['pb'], input=h['input'],
                                              output=h['output']) for h in heads}
    cols = [f'{h["name"]}::{c}' for h in heads for c in h['classes']]
    rows, kept, failed = [], [], 0
    for i, f in enumerate(files):
        w = decode(CLIPS / f, a.seconds)
        if w is None: failed += 1; continue
        try:
            E = {k: v(w) for k, v in emb.items()}
            vec = []
            for h in heads:
                p = np.asarray(algs[h['name']](E[h['backbone']]))
                if p.ndim == 1: p = p[None, :]
                m = p.mean(0)
                # A head whose width disagrees with its own declared class list is a metadata
                # error, not something to silently pad -- record NaN so it shows up as absent.
                vec += (list(m[:len(h['classes'])]) if m.shape[0] >= len(h['classes'])
                        else [float('nan')] * len(h['classes']))
            rows.append([float(x) for x in vec]); kept.append(f)
        except Exception as e:
            failed += 1
            if failed <= 3: print(f'  FAIL {f}: {e}', flush=True)
        if (i + 1) % 100 == 0: print(f'  {i+1}/{len(files)}  kept={len(kept)} failed={failed}', flush=True)
    print(f'done: kept {len(kept)}, failed {failed}', flush=True)
    json.dump({'files': kept, 'columns': cols, 'values': rows}, open(a.out, 'w'))
    print(f'wrote {a.out}', flush=True)
    print('SCAN_DONE', flush=True)

if __name__ == '__main__':
    main()
