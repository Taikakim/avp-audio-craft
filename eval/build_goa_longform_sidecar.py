#!/usr/bin/env python3
"""Build a caption sidecar mapping latents_sa3 stems -> kimlong longform prompts.

The goa latents' stored .json prompts are terse ("earth chakra, 1996, 123");
Kim's fp32/T=4096 comparison campaign (2026-07-14) trains on the LONGFORM
prompts instead. Source pool: eval/kimlong_pool.json (2642 per-track detailed
prompts keyed by artist/title). Output: caption_tools.make_caption_sampler
sidecar {stem: {"t1": prompt}} — only t1 is populated, so any --caption_probs
lands on the longform text via the t1 fallback.

Match key: casefolded, punctuation-stripped (artist, title) from the latent
json's track_metadata_* fields. Unmatched stems are omitted (sampler returns
{} -> dataset keeps its stored prompt); the match rate is printed so a low
rate is visible before the sidecar ships to LUMI.

Usage:
  python3 eval/build_goa_longform_sidecar.py \
    --latents /home/kim/Projects/latents_sa3 \
    --pool eval/kimlong_pool.json \
    --out lumi/goa_kimlong_sidecar.json
"""
import argparse
import glob
import json
import os
import re
import unicodedata


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.casefold()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pool = json.load(open(args.pool))
    by_key = {}
    by_track = {}
    by_title = {}          # title -> [(artist, prompt)] for relaxed matching
    for e in pool:
        a, t = norm(e.get("artist")), norm(e.get("title"))
        by_key[(a, t)] = e["prompt"]
        by_track[norm(e.get("track"))] = e["prompt"]
        by_title.setdefault(t, []).append((a, e["prompt"]))
        t_bare = norm(re.sub(r"\([^)]*\)", "", e.get("title") or ""))
        if t_bare and t_bare != t:
            by_key.setdefault((a, t_bare), e["prompt"])
            by_title.setdefault(t_bare, []).append((a, e["prompt"]))

    def relaxed(artist: str, title: str):
        """Tiered fallbacks: bare title, artist containment, unique title-only."""
        t_bare = norm(re.sub(r"\([^)]*\)", "", title)) if title else ""
        for t in (title and norm(title), t_bare):
            if not t:
                continue
            hit = by_key.get((artist, t))
            if hit:
                return hit
            cands = by_title.get(t, [])
            # artist containment either way ("bigitam, mystic" vs "bigitam")
            contained = [p for a, p in cands
                         if a and artist and (a in artist or artist in a)]
            if len(set(contained)) == 1:
                return contained[0]
            if len({p for _, p in cands}) == 1 and cands:
                return cands[0][1]      # title unique across the whole pool
        return None

    sidecar, missed = {}, []
    jsons = sorted(
        f for f in glob.glob(os.path.join(args.latents, "*.json"))
        if not f.endswith(".TIMBRAL.json") and not f.endswith(".json.lock")
    )
    for f in jsons:
        d = json.load(open(f))
        stem = os.path.splitext(os.path.basename(f))[0]
        artist = norm(d.get("track_metadata_artist"))
        title = norm(d.get("track_metadata_title"))
        prompt = (by_key.get((artist, title))
                  or by_track.get(f"{artist} {title}")
                  or relaxed(artist, d.get("track_metadata_title") or ""))
        if prompt:
            sidecar[stem] = {"t1": prompt}
        else:
            missed.append((stem, d.get("track_metadata_artist"),
                           d.get("track_metadata_title")))

    json.dump(sidecar, open(args.out, "w"), ensure_ascii=False, indent=0)
    n = len(jsons)
    print(f"[sidecar] {len(sidecar)}/{n} stems matched "
          f"({100 * len(sidecar) / max(n, 1):.1f}%) -> {args.out}")
    if missed:
        print(f"[sidecar] {len(missed)} unmatched (keep stored prompt), first 10:")
        for stem, a, t in missed[:10]:
            print(f"   {stem}: {a} - {t}")


if __name__ == "__main__":
    main()
