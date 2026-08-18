#!/usr/bin/env python3
"""audit_caption_era_grounding.py — did the per-track YEAR hint actually steer the captioner?

WHY THIS IS A SEPARATE CHECK. We already verify that a hint was LOADED (the job log prints the map
size) and that it was ATTACHED (every caption json carries genre_hint / genre_hint_source). Neither
proves it was USED. Music Flamingo can read "release year: 2020" and still emit the reflexive "90s
goa trance" framing, and the artifact would look perfect: right hint, right source field, fluent
caption, wrong era. That is the same failure shape as the whole 2026-08-18 caption episode — the
number looks clean while the content is wrong — so it gets its own instrument.

THE TEST — explicit era CLAIMS, agreement vs contradiction. For each caption we extract every year
and decade token the prose actually states ("1997", "mid 90s", "2000s", "21st century") and compare
it against the year the hint gave that same track:
    AGREE      the stated era matches the metadata decade  -> the hint steered the output
    CONTRADICT the caption states a DIFFERENT era           -> actively wrong, the thing to hunt
    SILENT     the caption states no era at all             -> neither, and harmless
CONTRADICT is the number that matters. It is Kim's constraint made measurable (2026-08-18: "don't use
2000s for oldschool, and 90s for neo-goa; there are subtle production differences even in new goa
which the model will learn") — a contradicting caption teaches the model that a 2020 track sounds
like 1994.

WHY NOT AN ERA-VOCABULARY LIFT. That was this tool's first design and it was worthless: MF's stock
phrasing is "blends classic X with modern Y", so "modern" appeared in 99.4% of captions and "classic"
in 92.6%. At a 99% base rate there is no headroom to detect anything, and the flat lift table it
produced was an artifact of the measure, not a finding about the hint. Kept as a secondary panel only
because a saturated baseline is itself worth seeing; do not draw conclusions from its lifts.

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

# Explicit era claims IN THE CAPTION PROSE. Related to but NOT shared with
# eval/inject_year_into_captions.py: that module REWRITES decade spans in place, this one
# RESOLVES them to a comparable decade int ('90s' -> 1990), which it has no need to do.
BARE_YEAR = re.compile(r"\b(19[6-9]\d|20[0-2]\d)\b(?!s)")

def stated_decades(text: str):
    """Every decade the caption explicitly claims, as ints (1990, 2000, ...).

    Two-digit tokens are ambiguous by construction: "90s" is 1990s, "00s"/"10s"/"20s" are 2000s/
    2010s/2020s. Resolved by the convention this corpus actually uses rather than by century math,
    because '20s' here never means 1920s.
    """
    out = set()
    for m in BARE_YEAR.finditer(text or ""):
        out.add(int(m.group(0)) // 10 * 10)
    for m in re.finditer(r"\b'?((?:19|20)?\d)0s\b", text or "", re.IGNORECASE):
        tok = m.group(1)
        if len(tok) >= 3:
            out.add(int(tok) * 10)
        else:
            d = int(tok)
            out.add(1990 if d == 9 else 1980 if d == 8 else 1970 if d == 7 else 2000 + d * 10)
    if re.search(r"\b21st[-\s]century\b", text or "", re.IGNORECASE):
        out.add(2000)
    return out


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

    # ---- PRIMARY: explicit era claims, agreement vs contradiction -------------------------------
    print(f"{'decade':>8} {'n':>6} {'agree':>8} {'CONTRADICT':>11} {'silent':>8}")
    tot = collections.Counter()
    contra_examples = []
    for dec in sorted(buckets):
        c = collections.Counter()
        for txt in buckets[dec]:
            st = stated_decades(txt)
            if not st:
                c["silent"] += 1
            elif dec in st:
                c["agree"] += 1
            else:
                c["contra"] += 1
                if len(contra_examples) < 6:
                    contra_examples.append((dec, sorted(st), txt[:150]))
        n = max(1, sum(c.values()))
        tot.update(c)
        print(f"{dec:>8} {sum(c.values()):>6} {c['agree']/n:>8.1%} {c['contra']/n:>11.1%} "
              f"{c['silent']/n:>8.1%}")
    N = max(1, sum(tot.values()))
    print(f"\n  TOTAL   agree {tot['agree']/N:.1%}   CONTRADICT {tot['contra']/N:.1%}   "
          f"silent {tot['silent']/N:.1%}")
    print("  CONTRADICT is the actionable number: those captions state an era the metadata says is")
    print("  wrong, and teach the model that eras sound alike. Fix with eval/inject_year_into_captions.py")
    print("  (which needs the hint map as its year source on this corpus -- paths carry no year).")
    if contra_examples:
        print("\n  contradiction examples (metadata decade -> stated):")
        for dec, st, txt in contra_examples:
            print(f"    {dec}s -> {st}  {txt}")

    # ---- SECONDARY: era-vocabulary lift. Saturated; see module docstring. -----------------------
    print("\n--- secondary: era-vocabulary lift (saturated measure, read with care) ---")
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
