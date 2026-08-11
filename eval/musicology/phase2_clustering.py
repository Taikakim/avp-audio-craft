#!/usr/bin/env python
"""Phase 2: style clustering of the muscriptor corpus from phase-1 features.

Reads features.jsonl; standardizes a musical feature vector; PCA; KMeans with k
chosen by silhouette over 3..12; also reports density structure (PCA scatter
grid occupancy + a lightweight DBSCAN sweep as HDBSCAN stand-in).

Outputs: clusters.json (assignments + per-cluster profiles + exemplars),
         cluster_summary.md, pca_scatter.txt (ASCII density view).
Run: /home/kim/Projects/mir/mir/bin/python phase2_clustering.py
"""
import json, os
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score

OUT = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open(os.path.join(OUT, 'features.jsonl'))]

FEATS = ['bpm','notes_per_sec','drum_density','kick_rate','kick_on_beat','syncopation',
         'bass_rate','bass_offbeat16','bass_occupancy','bass_repeat_ratio','bass_root_ratio',
         'bass_pitch_std',
         'lead_rate','lead_range','lead_pitch_med','lead_offbeat16','lead_phrase_len_med',
         'lead_phrase_sec_med','lead_chromaticism','lead_step_ratio','lead_leap_ratio',
         'lead_repeat_ratio','lead_octave_ratio','lead_turning_rate','lead_b2','lead_raised7']
IS_MINOR = lambda r: 1.0 if r['mode'] == 'minor' else 0.0

use = [r for r in rows if r['has_bass'] and r['has_lead']]
X = np.array([[r.get(f) if r.get(f) is not None else 0.0 for f in FEATS] + [IS_MINOR(r)]
              for r in use])
names = FEATS + ['is_minor']
ids = [r['id'] for r in use]
print(f'clustering {len(use)} files with lead+bass ({len(rows)} kept total)')

Xs = StandardScaler().fit_transform(X)
pca = PCA(n_components=10, random_state=0)
Z = pca.fit_transform(Xs)
print('PCA evr:', pca.explained_variance_ratio_[:6].round(3), 'cum10=%.3f' % pca.explained_variance_ratio_.sum())

best = None
sil_by_k = {}
for k in range(3, 13):
    km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(Z)
    s = silhouette_score(Z, km.labels_)
    sil_by_k[k] = round(float(s), 4)
    if best is None or s > best[1]: best = (k, s, km)
print('silhouette by k:', sil_by_k)
k, sil, km = best
labels = km.labels_
print(f'chosen k={k} sil={sil:.3f}')

# density structure: DBSCAN sweep on first 5 PCs (HDBSCAN stand-in)
Z5 = Z[:, :5]
dens_notes = []
from sklearn.neighbors import NearestNeighbors
d5 = NearestNeighbors(n_neighbors=6).fit(Z5).kneighbors(Z5)[0][:, -1]
for eps in [np.percentile(d5, p) for p in (25, 50, 75)]:
    db = DBSCAN(eps=eps, min_samples=8).fit(Z5)
    nclu = len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)
    noise = float(np.mean(db.labels_ == -1))
    dens_notes.append(dict(eps=round(float(eps), 3), n_clusters=nclu, noise_frac=round(noise, 3)))
print('DBSCAN sweep:', dens_notes)

# ASCII density scatter of PC1/PC2
H, W = 20, 64
x, y = Z[:, 0], Z[:, 1]
gx = np.clip(((x - x.min()) / (x.ptp() + 1e-9) * (W - 1)).astype(int), 0, W - 1)
gy = np.clip(((y - y.min()) / (y.ptp() + 1e-9) * (H - 1)).astype(int), 0, H - 1)
grid = np.zeros((H, W), int)
for a, b in zip(gy, gx): grid[a, b] += 1
chars = ' .:-=+*#%@'
lines = [''.join(chars[min(9, int(np.sqrt(v) * 2))] for v in row) for row in grid[::-1]]
open(os.path.join(OUT, 'pca_scatter.txt'), 'w').write('\n'.join(lines) + '\n')

KEYS = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B']
profiles = []
for c in range(k):
    m = labels == c
    sub = [use[i] for i in np.where(m)[0]]
    med = {f: float(np.median(X[m, j])) for j, f in enumerate(names)}
    # z-score of cluster median vs global for distinguishing feats
    gmu, gsd = Xs.mean(0), 1.0
    zmed = {names[j]: float(np.median(Xs[m, j])) for j in range(len(names))}
    top = sorted(zmed.items(), key=lambda kv: -abs(kv[1]))[:7]
    keys = {}
    for r in sub: keys[KEYS[r['tonic']] + ('m' if r['mode'] == 'minor' else '')] = \
        keys.get(KEYS[r['tonic']] + ('m' if r['mode'] == 'minor' else ''), 0) + 1
    genres = {}
    for r in sub:
        g = r.get('genre') or 'unknown'
        genres[g] = genres.get(g, 0) + 1
    yrs = [r['year'] for r in sub if r.get('year')]
    # exemplars: nearest to centroid
    dists = np.linalg.norm(Z[m] - km.cluster_centers_[c], axis=1)
    ex_idx = np.where(m)[0][np.argsort(dists)[:5]]
    exemplars = [dict(id=use[i]['id'], artist=use[i].get('artist'), title=use[i].get('title')) for i in ex_idx]
    profiles.append(dict(cluster=int(c), n=int(m.sum()), median_features={f: round(v, 3) for f, v in med.items()},
                         distinguishing=[(f, round(v, 2)) for f, v in top],
                         top_keys=sorted(keys.items(), key=lambda kv: -kv[1])[:5],
                         top_genres=sorted(genres.items(), key=lambda kv: -kv[1])[:4],
                         year_med=float(np.median(yrs)) if yrs else None,
                         exemplars=exemplars))

json.dump(dict(k=k, silhouette=round(float(sil), 4), sil_by_k=sil_by_k,
               dbscan_sweep=dens_notes, feature_names=names,
               pca_evr=[round(float(v), 4) for v in pca.explained_variance_ratio_],
               assignments={i: int(l) for i, l in zip(ids, labels)},
               profiles=profiles),
          open(os.path.join(OUT, 'clusters.json'), 'w'), indent=1)

with open(os.path.join(OUT, 'cluster_summary.md'), 'w') as f:
    f.write(f'# Phase 2 clusters (k={k}, silhouette={sil:.3f})\n\n')
    f.write(f'sil by k: {sil_by_k}\nDBSCAN sweep: {dens_notes}\n\n')
    for p in profiles:
        f.write(f"## Cluster {p['cluster']} (n={p['n']}, median year {p['year_med']})\n")
        f.write(f"distinguishing (z of median): {p['distinguishing']}\n")
        mf = p['median_features']
        f.write(f"bpm {mf['bpm']:.0f} | minor {mf['is_minor']:.0f} | bass rate {mf['bass_rate']:.1f}/s "
                f"offbeat {mf['bass_offbeat16']:.2f} occ {mf['bass_occupancy']:.2f} root {mf['bass_root_ratio']:.2f} | "
                f"lead rate {mf['lead_rate']:.1f}/s range {mf['lead_range']:.0f} chrom {mf['lead_chromaticism']:.2f} "
                f"phrase {mf['lead_phrase_len_med']:.0f}n b2 {mf['lead_b2']:.2f}\n")
        f.write(f"keys: {p['top_keys']}  genres: {p['top_genres']}\n")
        f.write("exemplars: " + ', '.join(f"{e['id']} ({e['artist']} - {e['title']})" for e in p['exemplars']) + '\n\n')
print('wrote clusters.json / cluster_summary.md')
