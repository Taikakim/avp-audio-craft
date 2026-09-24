#!/usr/bin/env python
"""caption_corpus_sample.py — QA the big-set caption corpus (CONTINUITY 2026-08-04). Joins, per track,
the Granite T2 variant pool + the Music-Flamingo T3 caption via curated.jsonl (hash->track path), and
prints a random sample side-by-side so you can eyeball genre-correctness + tier coherence against the
REAL track (artist/title/year live in the path). Both caption tiers are keyed by the same sha1 hash =
the curated.jsonl key, so the join is direct. This is also the exact join G's sidecar builder needs.

Usage:
  python eval/caption_corpus_sample.py -n 12
  python eval/caption_corpus_sample.py -n 8 --grep goa --seed 7      # only tracks whose path matches
"""
import os, json, glob, argparse, random, re, textwrap

DRIVE = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d"
CUR = f"{DRIVE}/goa_archive_features/curated.jsonl"
JSON_DIR = "/run/media/kim/Kosmos/goa_archive_captions/json"
GRANITE_DIR = "/run/media/kim/Kosmos/goa_archive_captions/granite"


def load_curated(path):
    m = {}
    for ln in open(path):
        try:
            o = json.loads(ln); m[o["key"]] = o
        except Exception:
            pass
    return m


def read_mf(d):
    for k in ("full", "music_flamingo_full", "caption", "prompt", "text", "description"):
        v = d.get(k)
        if isinstance(v, str) and len(v) > 40:
            return v
    cands = [v for v in d.values() if isinstance(v, str)]
    return max(cands, key=len) if cands else ""


def wrap(s, w=100, indent="      "):
    return ("\n").join(textwrap.wrap(s, w, initial_indent=indent, subsequent_indent=indent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument("--grep", default=None, help="only tracks whose rel-path matches this (case-insensitive)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json-dir", default=JSON_DIR)
    ap.add_argument("--granite-dir", default=GRANITE_DIR)
    ap.add_argument("--curated", default=CUR)
    a = ap.parse_args()

    if not os.path.isdir(a.granite_dir):
        print(f"[qa] granite dir missing: {a.granite_dir} — pull the prompts first."); return
    cur = load_curated(a.curated)
    gfiles = glob.glob(os.path.join(a.granite_dir, "*.json"))
    # keep only tracks that have BOTH a granite + MF json AND a curated entry (a full join)
    keys = []
    for g in gfiles:
        h = os.path.splitext(os.path.basename(g))[0]
        if h in cur and os.path.exists(os.path.join(a.json_dir, h + ".json")):
            if a.grep and a.grep.lower() not in (cur[h].get("rel", "").lower()):
                continue
            keys.append(h)
    n_join = len(keys)
    print(f"[qa] {len(gfiles)} granite files; {n_join} fully joined (granite∩MF∩curated"
          f"{', grep='+a.grep if a.grep else ''}).")
    if not keys:
        print("[qa] nothing to sample — check the key alignment (granite basename == curated 'key' hash?)."); return
    rng = random.Random(a.seed)
    for h in rng.sample(keys, min(a.n, len(keys))):
        c = cur[h]
        rel = c.get("rel", "?")
        try:
            mf = read_mf(json.load(open(os.path.join(a.json_dir, h + ".json"))))
        except Exception:
            mf = "(MF unreadable)"
        try:
            gr = json.load(open(os.path.join(a.granite_dir, h + ".json")))
        except Exception:
            gr = {}
        print("\n" + "=" * 108)
        print(f"TRACK: {rel}")
        print(f"       role={c.get('role')} tier={c.get('tier')} dur={c.get('dur_s')}s  hash={h[:12]}")
        print("  -- T2 Granite (genre-corrected variant pool) --")
        for tag in ("short_genremood", "short_technical", "short_mood"):
            for v in (gr.get(tag) or []):
                print(f"     [{tag}] {v}")
        if gr.get("medium_review"):
            print(wrap("[medium] " + gr["medium_review"], indent="     "))
        print("  -- T3 Music Flamingo (full) --")
        print(wrap(mf))
    print("\n" + "=" * 108)
    print(f"[qa] sampled {min(a.n, len(keys))} of {n_join} fully-joined tracks. "
          f"Eyeball: does T2 genre match the track's real style (from the path)? are the variants diverse + coherent?")


if __name__ == "__main__":
    main()
