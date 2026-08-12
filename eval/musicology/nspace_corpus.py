#!/usr/bin/env python
"""nspace_corpus.py — run the per-stem negative-space (gate-rhythm) metric over the
whole Stems catalogue (Kim's own tracks, UUID drive — Mantu-free). Emergent-intentionality
at scale: aggregate space_score by the (unverified) auto-classification CATEGORY so we can
see whether rhythmic roles (bass/drums/leads-arp) self-select high and sustained roles low.

Run: /home/kim/Projects/mir/mir/bin/python nspace_corpus.py [--root DIR] [--out JSON]
Writes per-stem rows + per-category aggregate to JSON, prints the category summary.
"""
import argparse, glob, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nspace import nspace_metrics, rms_env, SR, FPS

ROOT = '/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/Stems'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--out', default=os.path.join(HERE, 'nspace_corpus.json'))
    ap.add_argument('--sr', type=int, default=SR)
    ap.add_argument('--fps', type=int, default=FPS)
    args = ap.parse_args()
    tracks = sorted(d for d in glob.glob(os.path.join(args.root, '*')) if os.path.isdir(d))
    print(f'{len(tracks)} tracks under {args.root}', flush=True)
    rows = []
    t0 = time.time()
    for ti, tdir in enumerate(tracks):
        cj = os.path.join(tdir, '_classification.json')
        cats = {}
        if os.path.exists(cj):
            try:
                cats = {k: v.get('category', '?') for k, v in json.load(open(cj)).get('stems', {}).items()}
            except Exception:
                pass
        stems = sorted(f for f in glob.glob(os.path.join(tdir, '*.flac'))
                       if 'full mix' not in os.path.basename(f).lower())
        for p in stems:
            b = os.path.basename(p)
            try:
                m = nspace_metrics(rms_env(p, args.sr, args.fps), args.fps)
            except Exception as e:
                rows.append(dict(track=os.path.basename(tdir), stem=b, cat=cats.get(b, '?'),
                                 error=str(e)[:60]))
                continue
            m['space_score'] = max(0.0, m['space_score'])   # clamp anti-corr to 0 (no rhythm)
            rows.append(dict(track=os.path.basename(tdir), stem=b, cat=cats.get(b, '?'), **m))
        print(f'  [{ti+1}/{len(tracks)}] {os.path.basename(tdir)[:44]}: '
              f'{len(stems)} stems ({time.time()-t0:.0f}s)', flush=True)
    # per-category aggregate
    ok = [r for r in rows if 'space_score' in r]
    cats = sorted({r['cat'] for r in ok})
    agg = {}
    for c in cats:
        ss = np.array([r['space_score'] for r in ok if r['cat'] == c])
        agg[c] = dict(n=int(len(ss)), space_mean=round(float(ss.mean()), 4),
                      space_p90=round(float(np.percentile(ss, 90)), 4),
                      frac_gated=round(float((ss > 0.15).mean()), 3))  # frac with real gate rhythm
    out = dict(built=time.strftime('%Y-%m-%d %H:%M:%S'), n_tracks=len(tracks),
               n_stems=len(rows), n_ok=len(ok), sr=args.sr, fps=args.fps,
               by_category=agg, rows=rows)
    json.dump(out, open(args.out, 'w'), indent=1)
    print(f'\n=== by category (space_score: silence x gate-periodicity) ===', flush=True)
    print(f'{"cat":<12} {"n":>4} {"mean":>7} {"p90":>7} {"frac>0.15":>9}')
    for c in sorted(agg, key=lambda c: -agg[c]['space_mean']):
        a = agg[c]
        print(f'{c:<12} {a["n"]:>4} {a["space_mean"]:>7.3f} {a["space_p90"]:>7.3f} {a["frac_gated"]:>9.3f}')
    print(f'\nwrote {len(rows)} rows -> {args.out}', flush=True)


if __name__ == '__main__':
    main()
