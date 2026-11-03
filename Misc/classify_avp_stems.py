#!/usr/bin/env python3
"""classify_avp_stems.py -- classify AVP stem .flac files into 9 instrument-role
categories by FILENAME HEURISTICS ONLY (Kim task via WINTERMUTE, 2026-07-06).
Feeds WINTERMUTE's later stem-chroma phase (bass/pads/keys/synth chromas).

For each track folder under --stems-dir (top-level .flac files only -- a few
folders carry stray subdirs like "peaks"/"Demo mix"/"Nr"/"44.1k", which are DAW
scratch/alt-render artifacts, not stems, and are skipped by not recursing):
  - classify each stem into exactly one of: kick, drums, bass, acid, leads,
    arp_keys, pads, sfx, speech
  - EXCLUDE files whose name starts with "full mix" (reference downmixes)
  - write <track>/_classification.json (stem -> category + ambiguous flag +
    candidate alternates + which keywords fired, for Kim's review)
  - create <track>/<category>/ subfolders of SYMLINKS to the stems (non-destructive
    -- originals are never moved/modified)
  - render <track>/<category>/<CATEGORY>_downmix.flac (sum, peak-normalized DOWN
    only so the sum never clips -- the [-1,1] writer rule)

Genuinely ambiguous stems (multiple category keywords fire) are still assigned
a single best-guess category (by PRIORITY below) but flagged `ambiguous: true`
with the runner-up candidates listed, rather than silently forcing a confident
answer -- Kim reviews the manifest and can just re-point a symlink if needed.

Run (mir venv -- has soundfile/numpy, no GPU, CPU/name-based per WINTERMUTE):
    /home/kim/Projects/mir/mir/bin/python Misc/classify_avp_stems.py \
        --stems-dir /run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-stems
"""
import argparse
import json
import os
import re
from pathlib import Path

import numpy as np
import soundfile as sf

CATEGORIES = ["kick", "drums", "bass", "acid", "leads", "arp_keys", "pads", "sfx", "speech"]
CATEGORY_LABELS = {
    "kick": "kick",
    "drums": "drums (non-kick percussion: snare/hats/perc/shaker)",
    "bass": "bass",
    "acid": "acid",
    "leads": "leads (sustained synths)",
    "arp_keys": "arp+keys (snappy/short-decay synths)",
    "pads": "pads+strings+atmospheres",
    "sfx": "sfx",
    "speech": "speech",
}


def _wb(*words):
    """Case-insensitive alternation. A word ending in '+' matches as a PREFIX
    only (no trailing \\b): kick+ -> kick/kickbass/kickdrum, perc+ -> percussion.
    A word starting with '~' matches as a bare SUBSTRING, no boundary at all
    (for tokens that show up glued to other words: ~kick also catches
    laserkick/lazerkick/ekick, ~bass also catches subbass, ~hihat also catches
    openhihat/hihat135). Multi-word phrases (e.g. "jaw harp") work too --
    re.escape keeps the space literal and \\b anchors the whole phrase."""
    parts = []
    for w in words:
        if w.startswith("~"):
            parts.append(re.escape(w[1:]))
        elif w.endswith("+"):
            parts.append(r"\b" + re.escape(w[:-1]))
        else:
            parts.append(r"\b" + re.escape(w) + r"\b")
    return re.compile("(?:" + "|".join(parts) + ")", re.IGNORECASE)


def _pair(a_words, b_words):
    """Compile a checker: True if ANY of a_words AND ANY of b_words appear
    anywhere in the name (not necessarily adjacent) -- for envelope descriptors
    split by an intervening word, e.g. "fast amplitude release"."""
    ra = re.compile("(?:" + "|".join(r"\b" + re.escape(w) + r"\b" for w in a_words) + ")", re.IGNORECASE)
    rb = re.compile("(?:" + "|".join(r"\b" + re.escape(w) + r"\b" for w in b_words) + ")", re.IGNORECASE)
    return lambda name: bool(ra.search(name) and rb.search(name))


# Scan order doesn't matter here -- every rule is evaluated and ALL hits are
# collected (see classify()); PRIORITY below decides which wins when several fire.
RULES = [
    ("kick", _wb("kick+", "~kick")),
    ("drums", _wb("drum", "drums", "snare", "hihat", "hihats", "hi hat", "~hihat", "hat",
                  "cymbal", "clap", "shaker", "tambourine", "cowbell", "perc+", "ride",
                  "tom", "toms", "crash", "breakbeat", "break", "djembe", "darbouka",
                  "cajon", "bongo", "bongos", "conga", "congas", "tabla", "claves", "guiro")),
    ("acid", _wb("acid")),
    ("bass", _wb("bass+", "~bass")),
    ("leads", _wb("lead", "leads", "sustain", "sustained", "legato", "portamento", "riff",
                  "hoover", "horn", "flute", "flutes", "oboe", "clarinet", "trumpet",
                  "trombone", "didgeridoo", "duduk", "ocarina", "harmonica", "sitar",
                  "jaw harp", "erhu", "er hu", "xinghu", "bowed")),
    ("arp_keys", _wb("arp", "arpeggio", "arpeggiated", "pluck", "plucks", "plucked",
                      "stab", "stabs", "staccato", "snappy", "damped", "keys", "piano",
                      "bell", "bells", "mallet", "marimba", "xylophone", "ostinato",
                      "mbira", "kalimba", "kantele")),
    ("pads", _wb("pad", "pads", "atmosphere", "atmospheric", "atmospheres", "drone",
                 "drones", "string", "strings", "ambient", "choir", "chord", "chords",
                 "swelling", "swell", "swells", "cluster", "clusters")),
    ("sfx", _wb("sfx", "fx", "noise", "sweep", "sweeps", "riser", "risers", "whoosh",
                "impact", "transition", "field recording", "sound effect",
                "sound effects", "footstep", "footsteps")),
    ("speech", _wb("vocal", "vocals", "vox", "voice", "voices", "speech", "spoken",
                    "vocoder", "narration", "throat singing")),
]
# Envelope-character heuristics: Kim's leads (sustained) vs arp_keys (snappy/
# short-decay) split often shows up as an amplitude-envelope descriptor rather
# than an instrument noun -- "slow attack" / "fast decay|release" etc. These
# never OVERRIDE a direct instrument-noun hit above; they only fill in when
# nothing else fired (see classify()), and "delay" is deliberately excluded
# from the decay/release word set since "short/long delay" is an FX time
# parameter, not the synth's amplitude envelope.
ENVELOPE_ARP = _pair(("fast", "short", "quick"), ("decay", "release"))
ENVELOPE_LEAD = _pair(("slow",), ("attack",))
# Which category wins when multiple rules fire on the same filename. Named
# ambiguities Kim flagged (acid-vs-lead, bass-vs-lead-melody, arp-vs-lead) all
# fall out of this ordering + the ambiguous flag below, rather than needing
# special-cased pairs.
PRIORITY = ["speech", "kick", "drums", "acid", "bass", "leads", "arp_keys", "pads", "sfx"]

EXCLUDE_PREFIX = re.compile(r"^\s*full\s*mix", re.IGNORECASE)


def classify(name: str) -> dict:
    """-> {category, ambiguous, candidates, matched: {cat: [keywords]}}"""
    # `\b` doesn't fire between two \w chars, and '_' IS a \w char -- so
    # "Nation_drums.flac" would never match \bdrums\b. Normalize '_'/'-' to
    # spaces before matching so DAW-style underscore/hyphen separators behave
    # like the word breaks they visually are (matching is done on this
    # normalized copy only; the original `name` is preserved everywhere else
    # for exclusion-prefix checks, symlink targets, and manifest keys).
    norm = name.replace("_", " ").replace("-", " ")
    hits = {}
    for cat, rx in RULES:
        found = sorted(set(m.group(0).lower() for m in rx.finditer(norm)))
        if found:
            hits[cat] = found
    if not hits:
        # No instrument noun at all -- fall back to an envelope-character cue
        # (e.g. "boomstar analog synth ... short delay" has no noun but the
        # amplitude envelope still says which bucket it's closer to). This is
        # a weaker signal than a direct noun hit, so it's always flagged
        # ambiguous when it's the ONLY thing found.
        if ENVELOPE_ARP(norm) and not ENVELOPE_LEAD(norm):
            return {"category": "arp_keys", "ambiguous": True, "candidates": ["leads"],
                    "matched": {"arp_keys": ["<fast/short decay-release>"]}}
        if ENVELOPE_LEAD(norm) and not ENVELOPE_ARP(norm):
            return {"category": "leads", "ambiguous": True, "candidates": ["arp_keys"],
                    "matched": {"leads": ["<slow attack>"]}}
        return {"category": None, "ambiguous": True, "candidates": [], "matched": {}}
    # "synth choir" (a pad preset name) is far more common in this genre/catalogue
    # than a literal recorded vocal choir stem -- prefer pads when choir is the
    # ONLY speech-family hit and pads also fired, but keep it flagged ambiguous
    # either way so Kim can correct it.
    if hits.get("speech") == ["choir"] and "pads" in hits:
        picked = "pads"
    else:
        picked = next(c for c in PRIORITY if c in hits)
    ambiguous = len(hits) > 1
    candidates = [c for c in PRIORITY if c in hits and c != picked]
    return {"category": picked, "ambiguous": ambiguous, "candidates": candidates, "matched": hits}


def process_track(track_dir: Path, dry_run: bool):
    stems = sorted(p for p in track_dir.iterdir()
                   if p.is_file() and p.suffix.lower() == ".flac")
    manifest = {"track": track_dir.name, "stems": {}, "excluded": []}
    by_category = {c: [] for c in CATEGORIES}
    unclassified = []

    for stem in stems:
        if EXCLUDE_PREFIX.match(stem.name):
            manifest["excluded"].append(stem.name)
            continue
        result = classify(stem.name)
        cat = result["category"]
        manifest["stems"][stem.name] = {
            "category": cat, "category_label": CATEGORY_LABELS.get(cat),
            "ambiguous": result["ambiguous"], "candidates": result["candidates"],
            "matched_keywords": result["matched"],
        }
        if cat is None:
            unclassified.append(stem.name)
        else:
            by_category[cat].append(stem)

    manifest["unclassified"] = unclassified
    manifest["counts"] = {c: len(v) for c, v in by_category.items() if v}
    manifest["n_ambiguous"] = sum(1 for e in manifest["stems"].values() if e["ambiguous"])

    if dry_run:
        return manifest, by_category

    (track_dir / "_classification.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    for cat, files in by_category.items():
        if not files:
            continue
        cat_dir = track_dir / cat
        cat_dir.mkdir(exist_ok=True)
        for f in files:
            link = cat_dir / f.name
            if link.exists() or link.is_symlink():
                continue
            os.symlink(os.path.relpath(f, cat_dir), link)
        render_downmix(cat_dir, files, cat)

    return manifest, by_category


def render_downmix(cat_dir: Path, files: list, cat: str):
    out = cat_dir / f"{cat.upper()}_downmix.flac"
    if out.exists():
        return
    signals, sr, max_len = [], None, 0
    for f in files:
        try:
            y, this_sr = sf.read(f, always_2d=True, dtype="float32")
        except Exception as e:
            print(f"    [skip downmix input] {f.name}: {e}")
            continue
        if sr is None:
            sr = this_sr
        elif this_sr != sr:
            # no resampling here -- summing mismatched rates would silently warp
            # pitch/tempo, so mismatched stems are left out of the downmix
            # (still symlinked into the category folder, just not summed)
            print(f"    [skip downmix input] {f.name}: sr {this_sr} != {sr}")
            continue
        signals.append(y)
        max_len = max(max_len, y.shape[0])
    if not signals or sr is None:
        return
    n_ch = max(y.shape[1] for y in signals)
    mix = np.zeros((max_len, n_ch), dtype=np.float64)
    for y in signals:
        yy = y if y.shape[1] == n_ch else np.repeat(y, n_ch, axis=1)
        mix[: yy.shape[0], :] += yy
    peak = np.max(np.abs(mix))
    if peak > 1e-9:
        mix = mix / peak  # peak-normalize DOWN only -- a stem sum routinely exceeds [-1,1]
    sf.write(out, mix.astype(np.float32), sr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems-dir", required=True)
    ap.add_argument("--dry-run", action="store_true", help="classify + print stats only, write nothing")
    args = ap.parse_args()
    root = Path(args.stems_dir)
    tracks = sorted(p for p in root.iterdir() if p.is_dir())

    totals = {c: 0 for c in CATEGORIES}
    total_ambiguous = total_unclassified = total_excluded = 0
    fighting = []  # tracks whose filenames don't fit the descriptive convention well

    for track_dir in tracks:
        manifest, by_category = process_track(track_dir, args.dry_run)
        n_stems = len(manifest["stems"])
        print(f"{track_dir.name}: {n_stems} stems, "
              f"{manifest['n_ambiguous']} ambiguous, {len(manifest['unclassified'])} unclassified, "
              f"{len(manifest['excluded'])} excluded (full mix)")
        for c, n in manifest["counts"].items():
            totals[c] += n
        total_ambiguous += manifest["n_ambiguous"]
        total_unclassified += len(manifest["unclassified"])
        total_excluded += len(manifest["excluded"])
        if n_stems and len(manifest["unclassified"]) / n_stems > 0.3:
            fighting.append(track_dir.name)

    print("\n=== totals ===")
    for c in CATEGORIES:
        print(f"  {c:10s} {totals[c]}")
    print(f"  ambiguous    {total_ambiguous}")
    print(f"  unclassified {total_unclassified}")
    print(f"  excluded     {total_excluded} (full mix)")
    if fighting:
        print("\n[!] tracks where >30% of stems got no category keyword (naming convention doesn't fit):")
        for t in fighting:
            print(f"    - {t}")


if __name__ == "__main__":
    main()
