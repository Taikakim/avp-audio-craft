#!/usr/bin/env python3
"""inject_year_into_captions.py — replace guessed DECADE language with the track's ACTUAL release
year in a fraction of caption prompts.

WHY (Kim direct, 2026-08-18): "could we mechanistically pick the actual release year from metadata,
and insert it into some of the prompts? So instead of 90s goa trance there would be '1997' goa
trance also... And don't use 2000s for oldschool, and 90s for neo-goa; there are subtle production
differences even in new goa which the model will learn."

This is not a refinement of a good label, it is the correction of a WRONG one. Measured on the
2026-08-18 hinted sidecar:
  * The goa big-set is **100% 1990s** — all 23232 tracks, 1990-1999, year present in every rel path
    (Goa.PsyTrance.Collection.<YEAR>/...). There is not one 2000s track in the corpus.
  * Granite nonetheless opens **14.2% of captions with the literal "1990s 2000s goa trance"**, plus
    "goa trance 21st century" and "goa trance 2000s hypnotic" — a hedge across both decades,
    contradicted by ground truth we already had on disk.
So a model trained on this learns that 90s goa and 2000s goa sound alike, which is exactly the
distinction Kim wants it to keep. Replacing the hedge with "1997" both removes a falsehood and adds
a finer-grained handle — and sets up the year-as-int conditioner he plans later.

WHY ONLY A FRACTION: prompts at inference will not always carry a year, so the model needs to handle
both. Default 50% keeps the decade-free phrasing available while making the exact year a learnable
signal. Deterministic per track (seeded by key), so a rebuild produces the identical split.

USAGE
  python3 eval/inject_year_into_captions.py \
      --sidecar  .../goa_archive_caption_sidecar_hinted.json \
      --captions .../goa_archive_captions_hinted/json \
      --out      .../goa_archive_caption_sidecar_hinted_year.json \
      --fraction 0.5 --tiers t2
  Add --report-only to see what it would change without writing.
Only stdlib.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

YEAR_RE = re.compile(r"(?:19[6-9]\d|20[0-2]\d)")

# Decade/era language to replace. Ordered longest-first so "1990s 2000s" is consumed before "1990s"
# would match half of it and leave a dangling "2000s" behind.
DECADE_PATTERNS = [
    # ONE general range first: covers "1990s-2000s", "90s-00s", "90s-2000s", "1990s-00s" and the
    # space/slash/ampersand separators. Split two-digit and four-digit range patterns miss the MIXED
    # spellings, which then get half-replaced into nonsense like "90s-1990s".
    r"\b'?(?:19|20)?\d0s\s*(?:[-–/&]|\s)\s*'?(?:19|20)?\d0s\b",
    r"\b(?:early|mid|late)[-\s]?(?:19|20)\d0s\b",
    r"\b(?:early|mid|late)[-\s]?'?\d0s\b",   # "mid 90s", "late-90s"
    r"\b21st[-\s]century\b",
    r"\b20th[-\s]century\b",
    r"\b(?:19|20)\d0s\b",
    r"\b'?\d0s\b",                           # bare "90s", "'90s"
]
DECADE_RE = re.compile("|".join(DECADE_PATTERNS), re.IGNORECASE)


def _tidy(s: str) -> str:
    """Clean up punctuation left behind when a span is deleted mid-list (", ,", ",,", doubled
    spaces). Removing a phrase from a comma-separated tag list otherwise leaves debris that ends up
    in a training prompt."""
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*(?:,\s*)+", ", ", s)
    return s.strip(" ,")


def states_exact_year(text: str, year: int) -> bool:
    """Does the text state this year AS A YEAR, not as part of a decade token?

    `str(year) in text` is wrong and silently so: "1990" is a SUBSTRING of "1990s-2000s", so every
    1990 track looked like it already carried its exact year and was skipped -- 8 captions kept a
    false "1990s-2000s" through a pass whose entire purpose was removing that. Only years ending in
    0 can hit this, which is why it survived every hand-written test case.
    """
    return re.search(rf"\b{year}\b(?!s)", text or "") is not None


def year_for(rel: str):
    m = YEAR_RE.search(rel or "")
    return int(m.group(0)) if m else None


def rewrite(text: str, year: int):
    """Swap decade language for the exact year. Returns (new_text, n_replaced).

    If the text already states this exact year, leave it alone — re-stating it adds nothing and
    doubling it ("1997 1997 goa trance") is worse than the original.
    """
    if not text:
        return text, 0
    if states_exact_year(text, year):
        # already precise; only strip a CONTRADICTORY decade if one is also present
        def _strip(m):
            return "" if not states_exact_year(m.group(0), year) else m.group(0)
        new = DECADE_RE.sub(_strip, text)
        new = _tidy(new)
        return new, (1 if new != text else 0)
    new, n = DECADE_RE.subn(str(year), text)
    if n == 0:
        return text, 0
    # collapse a repeated year produced by two adjacent decade phrases ("1997 1997")
    new = re.sub(rf"\b{year}\b(\s*[-–/&,]?\s*\b{year}\b)+", str(year), new)
    new = _tidy(new)
    return new, n


def correct_decade(text: str, year: int):
    """Replace only CONTRADICTORY decade language with the track's true decade, leaving correct
    decade phrasing alone.

    Why this exists separately from rewrite(): the --fraction is meant to control EXACT YEAR vs
    DECADE phrasing, not CORRECTED vs LEFT WRONG. The first version only touched the selected half,
    which left 7041 tracks still asserting "2000s"/"21st century" about a corpus that is 100% 1990s
    -- i.e. it preserved a falsehood as if it were stylistic variety. A wrong decade is not a
    paraphrase, and Kim's instruction was explicit: do not use 2000s for oldschool or 90s for
    neo-goa, because the model will learn the production differences.
    """
    if not text:
        return text, 0
    true_dec = f"{(year // 10) * 10}s"
    def _fix(m):
        s = m.group(0)
        # A RANGE ("90s-00s", "1990s-2000s") is never kept even when half of it is right: the span
        # asserts the track spans both decades, which is false for every track here. Only a SINGLE
        # correct decade survives -- "mid 90s" on a 1995 track is accurate and more natural than
        # flattening it to "1990s".
        toks = re.findall(r"(?:19|20)?\d0s", s)
        if len(toks) > 1:
            return true_dec
        d2 = str((year // 10) % 10)
        if re.search(rf"(?:19|20)?{d2}0s\b", s):
            return s
        return true_dec

    new = DECADE_RE.sub(_fix, text)
    new = re.sub(rf"\b{true_dec}\b(\s*[-–/&,]?\s*\b{true_dec}\b)+", true_dec, new)
    new = _tidy(new)
    return new, (1 if new != text else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar", required=True, type=Path)
    ap.add_argument("--captions", required=True, type=Path,
                    help="dir of MF caption jsons; their 'rel' field carries the year")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fraction", type=float, default=0.5,
                    help="share of tracks to rewrite (default 0.5). Deterministic per track, so the "
                         "same tracks are chosen on every rebuild.")
    ap.add_argument("--tiers", default="t2",
                    help="comma-separated tiers to rewrite (default t2 — the short-tag tier that "
                         "matches how the model is actually prompted)")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if not a.report_only and not a.out:
        ap.error("--out required unless --report-only")

    side = json.loads(a.sidecar.read_text())
    tiers = [t.strip() for t in a.tiers.split(",") if t.strip()]

    # key -> year, from the caption jsons' own rel field
    years = {}
    for e in os.scandir(a.captions):
        if not e.name.endswith(".json"):
            continue
        try:
            d = json.load(open(e.path))
        except Exception:
            continue
        y = year_for(d.get("rel", ""))
        if y:
            years[d.get("rel") or os.path.splitext(e.name)[0]] = y
            years[os.path.splitext(e.name)[0]] = y

    chosen = changed = no_year = untouched = 0
    dist = {}
    for key, entry in side.items():
        if not isinstance(entry, dict):
            continue
        y = years.get(key)
        if y is None:
            no_year += 1
            continue
        # deterministic selection: hash the key, not RNG state, so rebuilds match
        h = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        exact = h < a.fraction
        if exact:
            chosen += 1
        hit = False
        for t in tiers:
            old = entry.get(t)
            # selected -> exact year; NOT selected -> still fix a contradictory decade, because a
            # wrong decade is a falsehood rather than a phrasing variant.
            new, n = rewrite(old, y) if exact else correct_decade(old, y)
            if n:
                hit = True
                if not a.report_only:
                    entry[t] = new
                if changed < 5:
                    # show the TRANSFORMATION. Printing entry[t] here showed the untouched original
                    # under --report-only (where nothing is assigned), i.e. the dry run displayed
                    # exactly what it was not going to do.
                    print(f"  [{t}] {y}")
                    print(f"        - {str(old)[:96]}")
                    print(f"        + {str(new)[:96]}")
        if hit:
            changed += 1
            if exact:
                dist[y] = dist.get(y, 0) + 1
        else:
            untouched += 1

    n = len(side)
    print(f"\nentries: {n}   with a known year: {n - no_year}   no year: {no_year}")
    print(f"selected for EXACT YEAR (fraction={a.fraction}): {chosen}; the rest keep decade "
          f"phrasing but have CONTRADICTORY decades corrected")
    print(f"  entries changed: {changed}    already consistent: {untouched}")
    if dist:
        print("  years touched:", dict(sorted(dist.items())))
    if a.report_only:
        print("\n--report-only: nothing written")
        return 0
    a.out.write_text(json.dumps(side))
    print(f"\nwrote -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
