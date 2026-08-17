#!/usr/bin/env python3
"""audit_caption_sidecar.py — does a tiered caption sidecar's granite tier actually reflect each
track's own Music Flamingo description, or is it template boilerplate?

WHY (Kim direct, 2026-08-17): "check the big goa set granite reviews for similarity randomly
sampling, to make sure Granite got the correct input." G had found the granite script passed the
FOLDER instead of the MF prompt. A contaminated granite tier is invisible from the outside — the
captions look fine one at a time and are nearly all distinct strings — so it needs a measurement.

THE MEASUREMENT THAT WORKS — directed containment lift:
    contain(t2, t3) = |words(t2) ∩ words(t3)| / |words(t2)|
  computed PAIRED (each tag vs its OWN track's MF prose) and SHUFFLED (vs a random other track's).
  LIFT = mean(paired) − mean(shuffled).
  If granite summarised each track's MF text, paired must beat shuffled clearly. A lift near zero
  means the tag is generated from something OTHER than that track's description.

Two metrics that DON'T work, recorded so nobody repeats them:
  * Symmetric Jaccard(t2, t3) — a 10-word tag against a 100-word paragraph scores ~0.03 whether
    paired or not, because the union is dominated by the prose. Too insensitive to see the effect.
  * Exact-duplicate rate — a contaminated tier still emits nearly all-distinct strings (the goa
    bigset: 23203 distinct of 23231, 0.2% dupes) because the template gets slot-filled with word
    swaps and a BPM. Distinctness is NOT evidence of per-track grounding.

Also reported: within-album vs cross-album similarity (a folder-fed run collapses to ~1.0 within
album), genre-family agreement between the tag and the prose, and the most common tag openings
(templating is the visible symptom).

USAGE
  python3 eval/audit_caption_sidecar.py lumi/goa_bigset_sidecar.json
  python3 eval/audit_caption_sidecar.py <sidecar> --tag-tier t2 --prose-tier t3 -n 600
Only stdlib.
"""
import argparse
import collections
import json
import random
import re
import statistics

STOP = set("a an the and or of with in to is this that track piece bpm featuring for its it as "
           "on at by from".split())
FAM = {"goa": "goa/psy", "psytrance": "goa/psy", "psychedelic": "goa/psy", "psy": "goa/psy",
       "trance": "trance", "house": "house", "techno": "techno", "ambient": "ambient",
       "breakbeat": "breaks", "breaks": "breaks", "dnb": "dnb", "jungle": "dnb",
       "downtempo": "downtempo", "dub": "dub"}


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower())
            if w not in STOP and len(w) > 2}


def contain(short, long):
    S, L = toks(short), toks(long)
    return len(S & L) / len(S) if S else 0.0


def album_of(key):
    p = key.split("/")
    return "/".join(p[:2]) if len(p) >= 2 else p[0]


# ── GENRE CORRECTNESS — the check that GROUNDING CANNOT SEE ─────────────────────────────────────
# Learned 2026-08-18, hours after this tool certified a sidecar it had no business certifying.
# Grounding asks "does the tag reflect ITS OWN track's prose". Correctness asks "is the prose TRUE".
# They are ORTHOGONAL: if Music Flamingo says "Deep House" about a goa track, a perfectly grounded
# granite tag faithfully inherits that error, and this tool's 19.24x said nothing about it.
# The cause was measurable and dull: goa's MF run recorded `genre_hint: None` (the mechanism exists
# and defaults to empty), so MF guessed unanchored -> 1.2% of a goa corpus mentioned goa/psy and
# 70.8% said techno/industrial/house. Suomisoundi, same script WITH a hint, scored 97.4%.
# Ranking measured on the same corpus, which is why a tier's PROVENANCE matters more than its polish:
#     T1 effnet classifier ON THE AUDIO   goa/psy 70.4%
#     T2 granite (revises the MF text)    goa/psy 48.0%   <- inherits the source error
#     T3 Music Flamingo prose             goa/psy  1.2%
# Run BOTH checks. A tier can be perfectly grounded and completely wrong.
GENRE_VOCAB = {
    "goa/psy": ("goa", "psytrance", "psy-trance", "psy trance", "psychedelic trance"),
    "trance": ("trance", "progressive trance", "uplifting trance"),
    "techno": ("techno", "tech house", "industrial"),
    "house": ("house", "deep house", "progressive house"),
    "ambient": ("ambient", "new age", "drone", "downtempo"),
    "breaks/dnb": ("breakbeat", "drum and bass", "jungle", "breaks"),
}


def genre_profile(d, keys, tier, head_chars=200):
    """Mention rate per genre family in the first `head_chars` of a tier.

    Scoped to the head because that is where a caption states its genre; scanning the whole prose
    picks up incidental mentions ("...unlike techno...") and blurs the signal.
    """
    n = 0
    hits = collections.Counter()
    for k in keys:
        txt = (d[k].get(tier) or "")[:head_chars].lower()
        if not txt:
            continue
        n += 1
        for fam, terms in GENRE_VOCAB.items():
            if any(t in txt for t in terms):
                hits[fam] += 1
    return n, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sidecar")
    ap.add_argument("--tag-tier", default="t2", help="the granite/short tag tier (default t2)")
    ap.add_argument("--prose-tier", default="t3", help="the Music Flamingo prose tier (default t3)")
    ap.add_argument("-n", "--sample", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--label", default=None)
    ap.add_argument("--expect-genre", default=None,
                    help="comma-separated terms the corpus SHOULD be labelled with, e.g. "
                         "'goa,psytrance'. Reports the per-tier hit rate — the CORRECTNESS check, "
                         "which grounding cannot see: a tag can faithfully reflect its own track's "
                         "prose while that prose is wrong about the genre. This is what caught the "
                         "goa corpus being captioned with genre_hint=None (1.2%% goa vs "
                         "suomisoundi's 97.4%% WITH a hint).")
    a = ap.parse_args()
    random.seed(a.seed)

    d = json.load(open(a.sidecar))
    keys = [k for k in d if isinstance(d[k], dict)]
    name = a.label or a.sidecar.split("/")[-1]
    print(f"\n===== {name} — {len(keys)} entries =====")

    pop = collections.Counter()
    for k in keys:
        for t in (a.tag_tier, a.prose_tier):
            if d[k].get(t):
                pop[t] += 1
    print(f"populated: {a.tag_tier}={pop[a.tag_tier]}  {a.prose_tier}={pop[a.prose_tier]}")

    usable = [k for k in keys if d[k].get(a.tag_tier) and d[k].get(a.prose_tier)]
    if not usable:
        print("  (no entries carry BOTH tiers — cannot compute the lift)")
        return 0
    s = random.sample(usable, min(a.sample, len(usable)))

    paired = [contain(d[k][a.tag_tier], d[k][a.prose_tier]) for k in s]
    other = [d[k][a.prose_tier] for k in s]
    random.shuffle(other)
    shuf = [contain(d[k][a.tag_tier], o) for k, o in zip(s, other)]
    lift = statistics.mean(paired) - statistics.mean(shuf)
    print(f"\nDIRECTED CONTAINMENT  |{a.tag_tier} ∩ {a.prose_tier}| / |{a.tag_tier}|   (n={len(s)})")
    print(f"  paired (own prose):    mean {statistics.mean(paired):.3f}")
    print(f"  shuffled (other prose): mean {statistics.mean(shuf):.3f}")
    verdict = ("GROUNDED — the tag reflects its own track" if lift >= 0.08 else
               "WEAK — barely better than chance" if lift >= 0.03 else
               "NOT GROUNDED — the tag carries no per-track information from the prose")
    print(f"  LIFT = {lift:+.3f}  -> {verdict}")

    # duplicates: near-zero dupes does NOT clear a tier (see module docstring)
    c = collections.Counter(d[k].get(a.tag_tier, "") for k in keys)
    dup = sum(n for t, n in c.items() if n > 1)
    print(f"\nexact-duplicate {a.tag_tier}: {dup}/{len(keys)} ({dup/max(1,len(keys)):.1%}); "
          f"{len(c)} distinct  (NOT a pass/fail signal on its own)")

    # folder-fed signature
    by = collections.defaultdict(list)
    for k in keys:
        by[album_of(k)].append(k)
    multi = [x for x, v in by.items() if len(v) >= 3]
    if len(multi) >= 2:
        win, cross = [], []
        for alb in random.sample(multi, min(120, len(multi))):
            ks = random.sample(by[alb], min(4, len(by[alb])))
            for i in range(len(ks)):
                for j in range(i + 1, len(ks)):
                    win.append(contain(d[ks[i]].get(a.tag_tier), d[ks[j]].get(a.tag_tier)))
        for _ in range(400):
            x, y = random.sample(multi, 2)
            cross.append(contain(d[random.choice(by[x])].get(a.tag_tier),
                                 d[random.choice(by[y])].get(a.tag_tier)))
        print(f"within-album tag similarity {statistics.mean(win):.3f} vs cross-album "
              f"{statistics.mean(cross):.3f}   (~1.0 within = fed the folder name)")

    ag = both = 0
    for k in s:
        x = {FAM[w] for w in toks(d[k][a.tag_tier]) if w in FAM}
        y = {FAM[w] for w in toks(d[k][a.prose_tier]) if w in FAM}
        if x and y:
            both += 1
            ag += 1 if (x & y) else 0
    if both:
        print(f"genre-family agreement {a.tag_tier} vs {a.prose_tier}: {ag}/{both} ({ag/both:.1%})")

    op = collections.Counter(" ".join(re.findall(r"[a-z0-9]+", (d[k].get(a.tag_tier) or "").lower())[:4])
                             for k in keys)
    print(f"most common {a.tag_tier} openings (4 words) — high share = templated:")
    for t, n in op.most_common(4):
        print(f"  {n:6d} ({n/max(1,len(keys)):5.1%})  {t}")

    # ── the second, ORTHOGONAL check ────────────────────────────────────────────────────────────
    print("\nGENRE PROFILE per tier (first 200 chars) — grounding cannot see this:")
    print(f"  {'tier':5} {'n':>7}  " + "  ".join(f"{f:>10}" for f in GENRE_VOCAB))
    for tier in ("t1", a.tag_tier, a.prose_tier):
        if tier not in {t for k in keys[:50] for t in d[k]}:
            continue
        n, hits = genre_profile(d, keys, tier)
        if not n:
            continue
        print(f"  {tier:5} {n:>7}  " + "  ".join(f"{hits[f]/n:>9.1%}" for f in GENRE_VOCAB))
    if a.expect_genre:
        want = tuple(w.strip().lower() for w in a.expect_genre.split(",") if w.strip())
        print(f"\nEXPECTED-GENRE HIT RATE for {list(want)}:")
        for tier in ("t1", a.tag_tier, a.prose_tier):
            n = hit = 0
            for k in keys:
                txt = (d[k].get(tier) or "")[:200].lower()
                if not txt:
                    continue
                n += 1
                hit += any(w in txt for w in want)
            if n:
                flag = "" if hit / n >= 0.6 else "   <-- LOW: this tier likely mislabels the corpus"
                print(f"  {tier:5} {hit}/{n} = {hit/n:6.1%}{flag}")
        print("  (a corpus legitimately containing other genres will not hit 100%; MF WITH a hint "
              "scored 97.4% on suomisoundi, WITHOUT one scored 1.2% on goa)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
