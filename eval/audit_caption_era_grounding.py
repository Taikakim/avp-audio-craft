#!/usr/bin/env python3
"""audit_caption_era_grounding.py — did the per-track YEAR hint actually steer the captioner?

WHY THIS IS A SEPARATE CHECK. We already verify that a hint was LOADED (the job log prints the map
size) and that it was ATTACHED (every caption json carries genre_hint / genre_hint_source). Neither
proves it was USED. Music Flamingo can read "release year: 2020" and still emit the reflexive "90s
goa trance" framing, and the artifact would look perfect: right hint, right source field, fluent
caption, wrong era. That is the same failure shape as the whole 2026-08-18 caption episode — the
number looks clean while the content is wrong — so it gets its own instrument.

THE TEST: bucket captions by the decade stated in their OWN hint, then measure how often era words
appear in the caption prose per bucket. If the hint is steering, MODERN words concentrate in the
2010s/2020s buckets and VINTAGE words in the 1990s. If the hint is being ignored, the two vocabularies
are distributed evenly across decades — a flat table is the null result, and it is the interesting one.

Reports a LIFT per bucket: P(modern words | bucket) / P(modern words | corpus). Lift ~1.0 everywhere
means no steering. Same convention as audit_caption_sidecar.py's grounding lift, deliberately, so the
two read the same way.

USAGE (LUMI login node, stdlib only, no GPU/container):
  python3 eval/audit_caption_era_grounding.py --captions /scratch/project_465003186/goa_src_captions/json
  (add --examples 3 to print sample captions from the extreme buckets)
"""
import argparse
import collections
import json
import os
import re

MODERN = ("modern", "contemporary", "current", "up-to-date", "recent", "today's", "polished",
          "hi-fi", "high-fidelity", "crisp", "loud", "full-range", "sidechain")
VINTAGE = ("90s", "1990s", "classic", "vintage", "retro", "old-school", "oldschool", "early",
           "analog", "analogue", "raw", "lo-fi", "tape", "hardware")

YEAR_IN_HINT = re.compile(r"release year: (\d{4})")


def _rate(texts, words):
    """Share of captions containing ANY of `words`. Presence, not frequency: one caption that says
    'modern' six times is one vote, otherwise a single verbose caption dominates its bucket."""
    if not texts:
        return 0.0
    hit = sum(1 for t in texts if any(w in t for w in words))
    return hit / len(texts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captions", required=True, help="dir of caption jsons")
    ap.add_argument("--tier", default=None,
                    help="caption key to read (default: the first one present)")
    ap.add_argument("--examples", type=int, default=0,
                    help="print N sample captions from the oldest and newest buckets")
    a = ap.parse_args()

    buckets = collections.defaultdict(list)
    n_total = n_nohint = n_noyear = 0
    for e in os.scandir(a.captions):
        if not e.name.endswith(".json"):
            continue
        n_total += 1
        try:
            d = json.load(open(e.path))
        except Exception:
            continue
        hint = d.get("genre_hint") or ""
        if not hint:
            n_nohint += 1
            continue
        m = YEAR_IN_HINT.search(hint)
        if not m:
            n_noyear += 1
            continue
        caps = d.get("captions") or {}
        text = (caps.get(a.tier) if a.tier else next(iter(caps.values()), "")) or ""
        buckets[int(m.group(1)) // 10 * 10].append(text.lower())

    scored = sum(len(v) for v in buckets.values())
    print(f"captions: {n_total}   no hint: {n_nohint}   hint without a year: {n_noyear}   "
          f"scored: {scored}")
    if not scored:
        print("\nNothing to score. Either these captions predate the per-track hint map, or the map "
              "never hit — check genre_hint_source in one of them before reading anything into this.")
        return 1

    base_m = _rate([t for v in buckets.values() for t in v], MODERN)
    base_v = _rate([t for v in buckets.values() for t in v], VINTAGE)
    print(f"corpus baseline: modern-words {base_m:.1%}   vintage-words {base_v:.1%}\n")
    print(f"{'decade':>8} {'n':>6} {'modern':>8} {'lift':>6} {'vintage':>8} {'lift':>6}")
    for dec in sorted(buckets):
        ts = buckets[dec]
        rm, rv = _rate(ts, MODERN), _rate(ts, VINTAGE)
        print(f"{dec:>8} {len(ts):>6} {rm:>8.1%} {rm/base_m if base_m else 0:>6.2f} "
              f"{rv:>8.1%} {rv/base_v if base_v else 0:>6.2f}")

    old, new = min(buckets), max(buckets)
    if old != new:
        d_old = _rate(buckets[old], VINTAGE) - _rate(buckets[old], MODERN)
        d_new = _rate(buckets[new], VINTAGE) - _rate(buckets[new], MODERN)
        sep = d_old - d_new
        print(f"\nseparation (vintage-minus-modern, {old}s bucket vs {new}s bucket): {sep:+.3f}")
        print("  > 0 means older tracks read as more vintage than newer ones — the hint is steering.")
        print("  ~ 0 means the captioner ignored the year and described every era the same way,")
        print("      which is the result that matters: the hint would be attached but inert, and")
        print("      every downstream artifact would still look correct.")

    if a.examples:
        for label, dec in (("OLDEST", old), ("NEWEST", new)):
            print(f"\n--- {label} bucket ({dec}s), {a.examples} sample(s):")
            for t in buckets[dec][:a.examples]:
                print(f"    {t[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
