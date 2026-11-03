#!/usr/bin/env python3
"""caption_sidecar_audit.py -- read a T1/T2/T3 caption sidecar and report whether it is fit to
train on, BEFORE the node-hours are spent.

WHY THIS EXISTS (2026-08-17/18, WINTERMUTE). Two separate caption faults reached training this
month, neither of them visible from anything the training job prints:

  1. WRONG GENRE, upstream of Granite. Kim: "MF prompts often mislabel the genres, despite giving
     the hint. That's why Granite needs a new hint in the revision stage." Measured on our own
     sidecars, scanning where MF states the genre (first 200 chars of t3):

        goa_bigset   (23231)   1.2% say goa/psy   |  58% techno, 46% industrial/hard
        goa_longform  (5400)  60.5% say goa/psy   |  31% techno/industrial
        suomisoundi   (1260)  97.4% say goa/psy   |   2% other

     So MF without an effective hint mislabels a goa corpus almost completely, and with a working
     hint it is clean. CRITICAL COROLLARY: t2 (Granite + hint) is the genre-corrected tier, t3 is
     MF's raw text. **Re-running Granite fixes t2 and does NOTHING for t3.** A "fixed" corpus that
     only re-ran the revision stage still carries the mislabels in t3 -- and the scripts that pass
     `--caption_probs 0,0,1` train on t3 ALONE, so for those the fix buys exactly nothing.

  2. A DEFAULT THAT MEANT SOMETHING ELSE. train_lora's `--caption_probs 0.6,0.3,0.1` was tuned for
     goa, where t1 is built PER TRACK from effnet genre400/moodtheme. On Suomisoundi t1 is ONE
     corpus-wide string, so the same numbers would have handed 60% of every epoch an identical
     prompt. String-uniqueness does not catch this either: goa's t2 is 23203/23231 unique but has
     only 345 distinct 3-word openings, an 898-word vocabulary, and the word "intricate" in 93% of
     captions -- unique strings, one template, near-identical conditioning.

So this reports three things a `len(sidecar)` check cannot: how many DISTINCT prompts a tier really
carries, whether the tiers AGREE about the same track (tempo is the cheap tell), and what genre the
text actually claims.

USAGE
    python3 eval/caption_sidecar_audit.py <sidecar.json> [--expect-genre goa]
    python3 eval/caption_sidecar_audit.py <sidecar.json> --probs 0.25,0.45,0.30

Exit code is 0 always -- this informs a judgement call, it does not gate. Read the output.
"""
import argparse
import collections
import json
import re
import statistics
import sys

GENRE_FAMILIES = {
    "goa/psy": ["goa", "psytrance", "psy-trance", "psychedelic trance", "suomisoundi"],
    "techno/industrial/hard": ["techno", "industrial", "hardstyle", "hardcore", "gabber"],
    "house": ["deep house", "progressive house", "tech house", " house"],
    "ambient/downtempo": ["ambient", "downtempo", "dub techno"],
    "dnb/breaks": ["drum and bass", "drum & bass", "breakbeat", "jungle"],
}
TIERS = ("t1", "t2", "t3")


def bpm_of(text):
    """The tempo a caption claims, if any. Two tiers describing the SAME track should broadly
    agree; systematic disagreement means they are not describing the same audio (or one is
    inventing numbers). Rounding shows up as small deltas -- read the distribution, not a
    pass/fail, which is the trap the first version of this check fell into."""
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*bpm", (text or "").lower())
    return float(m.group(1)) if m else None


def audit(path, expect_genre=None, probs=None):
    table = json.load(open(path))
    n = len(table)
    vals = list(table.values())
    print(f"=== {path}\n{n} entries\n")

    print("TIER DIVERSITY  (unique strings is the weak measure; distinct openings is the real one)")
    tier_stats = {}
    for tier in TIERS:
        col = [(v.get(tier) or "") for v in vals]
        nonempty = [x for x in col if x.strip()]
        if not nonempty:
            print(f"  {tier}: EMPTY on every entry")
            tier_stats[tier] = None
            continue
        uniq = len(set(nonempty))
        avg_len_probe = sum(map(len, nonempty)) // len(nonempty)
        # Opening-window length must scale with the tier. Tag tiers (~150 chars) differentiate
        # within 3 words; PROSE tiers do not -- every t3 starts "This track is a", so a 3-word
        # window reports "4 distinct openings, top 100%" and reads as catastrophic uniformity
        # when it is just an English sentence opener. 10 words clears the boilerplate.
        win = 10 if avg_len_probe > 400 else 3
        openings = collections.Counter(" ".join(x.split()[:win]).lower() for x in nonempty)
        top_share = openings.most_common(1)[0][1] / len(nonempty)
        vocab = collections.Counter(w for x in nonempty for w in re.findall(r"[a-z]+", x.lower()))
        avg_len = sum(map(len, nonempty)) // len(nonempty)
        tier_stats[tier] = dict(uniq=uniq, n=len(nonempty), openings=len(openings),
                                top_share=top_share, vocab=len(vocab), avg_len=avg_len)
        print(f"  {tier}: {uniq:6d}/{len(nonempty)} unique | {len(openings):5d} distinct {win}-word "
              f"openings (top = {top_share:5.1%}) | vocab {len(vocab):5d} words | avg {avg_len} chars"
              + ("   <-- ONE STRING FOR THE WHOLE CORPUS" if uniq == 1 else ""))
        if col and len(col) != len(nonempty):
            print(f"        ({len(col) - len(nonempty)} entries have no {tier})")

    print("\nTIER AGREEMENT  (do t2 and t3 describe the same track? tempo is the cheap tell)")
    deltas = [abs(a - b) for a, b in
              ((bpm_of(v.get("t2")), bpm_of(v.get("t3"))) for v in vals) if a and b]
    if deltas:
        buckets = collections.Counter()
        for d in deltas:
            buckets["<1" if d < 1 else "1-5" if d < 5 else "5-20" if d < 20 else "20+"] += 1
        print(f"  {len(deltas)} tracks state a BPM in both tiers | median |delta| = "
              f"{statistics.median(deltas):.1f}")
        for k in ("<1", "1-5", "5-20", "20+"):
            print(f"      |delta bpm| {k:>4}: {buckets[k]:6d}  {buckets[k]/len(deltas):6.1%}")
        print("  NOTE: rounding produces small deltas; a fat tail past 20 means the tiers are not "
              "describing\n        the same audio. Neither pattern alone is a verdict -- it says "
              "where to look.")
    else:
        print("  (no track states a BPM in both tiers -- cannot check)")

    print("\nGENRE CLAIMED BY THE TEXT  (first 200 chars, where the genre is stated)")
    for tier in TIERS:
        col = [(v.get(tier) or "").lower()[:200] for v in vals]
        if not any(col):
            continue
        hits = {fam: sum(any(t in h for t in terms) for h in col)
                for fam, terms in GENRE_FAMILIES.items()}
        top = sorted(hits.items(), key=lambda kv: -kv[1])[:3]
        print(f"  {tier}: " + "  ".join(f"{fam} {c/n:.1%}" for fam, c in top if c))
        if expect_genre:
            want = GENRE_FAMILIES.get(expect_genre)
            if want:
                got = sum(any(t in h for t in want) for h in col) / n
                flag = "" if got >= 0.8 else ("   <-- MISLABELED TIER" if got < 0.3 else "   <-- weak")
                print(f"        expected '{expect_genre}': {got:.1%}{flag}")

    if probs:
        p = [float(x) for x in probs.split(",")]
        print(f"\nWHAT --caption_probs {probs} ACTUALLY BUYS")
        for tier, share in zip(TIERS, p):
            st = tier_stats.get(tier)
            if not st or share == 0:
                print(f"  {tier}: {share:.0%} of samples" + ("  (unused)" if share == 0 else ""))
                continue
            eff = "one identical prompt" if st["uniq"] == 1 else f"{st['openings']} distinct openings"
            print(f"  {tier}: {share:.0%} of samples -> {eff}")
        if p[2] > 0.5:
            print("  WARNING: t3-heavy. t3 is MF's RAW text -- the tier that carries the genre "
                  "mislabels.\n           t2 is the Granite-with-hint tier and is the "
                  "genre-corrected one.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sidecar")
    ap.add_argument("--expect-genre", choices=sorted(GENRE_FAMILIES),
                    help="flag tiers whose text does not claim this genre")
    ap.add_argument("--probs", help="a --caption_probs value to interpret, e.g. 0.25,0.45,0.30")
    a = ap.parse_args()
    audit(a.sidecar, a.expect_genre, a.probs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
