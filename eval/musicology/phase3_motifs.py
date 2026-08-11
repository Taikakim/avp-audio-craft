#!/usr/bin/env python
"""Phase 3: lead-melody codification — corpus-wide motif mining.

Reads melodies.jsonl (per-file 16th-grid skyline lead from phase 1).
Representation: within-phrase n-grams (n=4..8) of successive pitch intervals in
semitones (key-invariant), clipped to +/-12. Two-pass mining:
  pass 1: global occurrence counts, prune to grams seen >= MIN_TOTAL times
  pass 2: cross-file support, within-file repetition (hook-ness), exemplars
Family dedupe: a gram contained in a higher-ranked kept gram (as a contiguous
subsequence, either direction) with <=1.35x its file support is folded in.

Outputs: motif_catalog.json (top families, full stats + exemplars),
         memorability.json (per-file hookness + corpus correlates),
         motif_summary.md.
Run: /home/kim/Projects/mir/mir/bin/python phase3_motifs.py
"""
import json, os, sys
from collections import Counter, defaultdict
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OUT)
# Reusable core lives in hook_metric.py (also drives eval/hook_eval_renders.py
# on our own renders); the gram/classify functions there are the verbatim
# originals from this script.
import hook_metric as _hm
from hook_metric import classify, DEGNAMES_MIN  # noqa: F401

MIN_TOTAL = 40          # global prune after pass 1
TOP_FAMILIES = 60       # candidates before dedupe (report top ~20-30)
NS = range(4, 9)

def load_melodies():
    mel = []
    for line in open(os.path.join(OUT, 'melodies.jsonl')):
        m = json.loads(line)
        mel.append(m)
    return mel

def phrase_iter(m):
    sl, pi, bd = m['slots'], m['pitches'], m['phrase_bounds']
    for i in range(len(bd) - 1):
        a, b = bd[i], bd[i+1]
        if b - a >= 3:
            yield sl[a:b], pi[a:b]

def grams_of(pitches):
    return _hm.grams_of(pitches, ns=NS)

def contour_grams_of(pitches):
    """n-grams over NONZERO intervals only (zero-runs collapsed): the melodic
    skeleton, invariant to how many same-note 16th repeats sit between moves."""
    return _hm.contour_grams_of(pitches, ns=NS)

def mine(mel, gram_fn, min_total=MIN_TOTAL, min_files=25):
    """Two-pass mining over a gram generator. Returns (families, per_file_hook)."""
    cnt = Counter()
    for m in mel:
        for _, pitches in phrase_iter(m):
            for g, _ in gram_fn(pitches):
                cnt[g] += 1
    keep = {g for g, c in cnt.items() if c >= min_total}
    print(f'pass1[{gram_fn.__name__}]: {len(cnt)} distinct; {len(keep)} kept')
    del cnt

    file_support = Counter()
    within = defaultdict(list)
    exemplars = defaultdict(list)
    per_file = {}
    for m in mel:
        local = Counter(); local_all46 = Counter(); tot46 = 0
        first_seen = {}
        step = m['step']; tonic = m['tonic']
        n_notes = len(m['pitches'])
        for slots, pitches in phrase_iter(m):
            for g, j in gram_fn(pitches):
                if g in keep:
                    local[g] += 1
                    if g not in first_seen:
                        first_seen[g] = (slots[j]*step, pitches[j],
                                         [(p - tonic) % 12 for p in pitches[j:j+len(g)+1]])
                if 4 <= len(g) <= 6:
                    local_all46[g] += 1; tot46 += 1
        for g, c in local.items():
            file_support[g] += 1
            within[g].append(c)
            if len(exemplars[g]) < 40:
                t, sp, dseq = first_seen[g]
                exemplars[g].append((m['id'], round(t, 2), sp, dseq))
        if tot46 >= 20:
            best_g, best_c = max(local_all46.items(), key=lambda kv: kv[1])
            per_file[m['id']] = dict(
                n_lead=n_notes, hook_count=int(best_c),
                hook_ratio=round(best_c * (len(best_g)+1) / max(1, n_notes), 4),
                hook_gram=list(best_g),
                distinct46_ratio=round(len(local_all46) / tot46, 4))

    ranked = sorted(keep, key=lambda g: (-file_support[g],
                                         -int(np.median(within[g]) if within[g] else 0)))
    families = []
    for g in ranked:
        if file_support[g] < min_files: continue
        sub = False
        for f in families:
            fg = f['gram']
            if len(g) <= len(fg):
                for off in range(len(fg)-len(g)+1):
                    if tuple(fg[off:off+len(g)]) == g and file_support[g] <= 1.35 * f['support_files']:
                        sub = True; break
            if sub: break
        if sub: continue
        w = within[g]
        families.append(dict(
            gram=list(g), n=len(g), klass=classify(g),
            support_files=int(file_support[g]),
            support_frac=round(file_support[g] / len(mel), 4),
            within_file_med=float(np.median(w)), within_file_p90=float(np.percentile(w, 90)),
            exemplars=exemplars[g][:6]))
        if len(families) >= TOP_FAMILIES: break

    for f in families:
        degs = [tuple(e[3]) for e in f['exemplars']]
        if degs:
            common = Counter(degs).most_common(1)[0][0]
            f['degree_seq_typical'] = '-'.join(DEGNAMES_MIN[d] for d in common)
        f['description'] = f"{f['klass']}: intervals {f['gram']} (typ. {f.get('degree_seq_typical','?')})"
    return families, per_file

def main():
    mel = load_melodies()
    print(f'{len(mel)} melodies')

    # Tier 1: 16th-grid grams (surface, incl. pedal/rolling-16th texture)
    families, per_file = mine(mel, grams_of)
    # Tier 2: contour grams (zero-runs collapsed -> melodic skeleton)
    families_c, per_file_c = mine(mel, contour_grams_of)
    # fold melodic hookness into per_file
    for fid, d in per_file.items():
        c = per_file_c.get(fid)
        d['hook_melodic_count'] = c['hook_count'] if c else 0
        d['hook_melodic_ratio'] = c['hook_ratio'] if c else 0.0
        d['hook_melodic_gram'] = c['hook_gram'] if c else None
        d['distinct46_contour_ratio'] = c['distinct46_ratio'] if c else None

    # memorability correlates: top vs bottom decile of MELODIC hookness
    ids_pf = [i for i in per_file if per_file[i]['hook_melodic_ratio'] is not None]
    hr = np.array([per_file[i]['hook_melodic_ratio'] for i in ids_pf])
    feats = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(OUT, 'features.jsonl'))}
    hi_cut, lo_cut = np.percentile(hr, 90), np.percentile(hr, 10)
    def agg(sel):
        rows = [feats[i] for i in sel if i in feats]
        pf = [per_file[i] for i in sel]
        def med(k, src): return round(float(np.median([r[k] for r in src if r.get(k) is not None])), 3)
        return dict(n=len(sel),
                    hook_melodic_ratio=med('hook_melodic_ratio', pf),
                    hook_melodic_count=med('hook_melodic_count', pf),
                    hook_pedal_count=med('hook_count', pf),
                    distinct46_contour_ratio=med('distinct46_contour_ratio', pf),
                    lead_phrase_len_med=med('lead_phrase_len_med', rows),
                    lead_range=med('lead_range', rows), lead_rate=med('lead_rate', rows),
                    lead_chromaticism=med('lead_chromaticism', rows),
                    lead_turning_rate=med('lead_turning_rate', rows),
                    lead_n=med('lead_n', rows),
                    bpm=med('bpm', rows))
    hi = [i for i in ids_pf if per_file[i]['hook_melodic_ratio'] >= hi_cut]
    lo = [i for i in ids_pf if per_file[i]['hook_melodic_ratio'] <= lo_cut]
    memo = dict(n_files=len(per_file),
                hook_melodic_ratio_pct={p: round(float(np.percentile(hr, p)), 4) for p in (10, 25, 50, 75, 90)},
                top_decile=agg(hi), bottom_decile=agg(lo),
                top_decile_ids=sorted(hi, key=lambda i: -per_file[i]['hook_melodic_ratio'])[:25],
                per_file=per_file)

    json.dump(dict(min_total=MIN_TOTAL, n_melodies=len(mel),
                   families_grid=families, families_contour=families_c),
              open(os.path.join(OUT, 'motif_catalog.json'), 'w'), indent=1)
    json.dump(memo, open(os.path.join(OUT, 'memorability.json'), 'w'), indent=1)

    with open(os.path.join(OUT, 'motif_summary.md'), 'w') as f:
        f.write(f'# Motif families ({len(mel)} melodies mined)\n\n')
        for name, fams in (('Grid (surface, 16th-grid)', families),
                           ('Contour (melodic skeleton, zero-runs collapsed)', families_c)):
            f.write(f'## {name}\n')
            for i, fam in enumerate(fams[:30]):
                f.write(f"{i+1}. **{fam['description']}** — files {fam['support_files']} "
                        f"({fam['support_frac']*100:.0f}%), within-file med {fam['within_file_med']:.0f} "
                        f"/ p90 {fam['within_file_p90']:.0f}; ex: "
                        + '; '.join(f"{e[0]}@{e[1]}s" for e in fam['exemplars'][:3]) + '\n')
            f.write('\n')
        f.write('\n## Memorability correlates (melodic hookness deciles)\n')
        f.write(json.dumps({k: v for k, v in memo.items() if k not in ('per_file',)}, indent=1))
    print('wrote motif_catalog.json / memorability.json / motif_summary.md')

if __name__ == '__main__':
    main()
