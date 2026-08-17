#!/usr/bin/env python3
"""build_suomisoundi_sidecar.py -- T1/T2/T3 caption sidecar for the Suomisoundi pre-encoded
latent set (GHOST-NOTE 2026-08-17, Kim direct), sibling of eval/build_goa_archive_sidecar.py.

Differs from the goa sidecar in one load-bearing way: goa's is keyed by 'rel' (the AUDIO
relpath) because it feeds train_lora.py's --data_dir LIVE-ENCODE path, which passes a custom
key_fn=lambda info: info["relpath"] (see make_data_dir_caption_fn). Suomisoundi was
PRE-ENCODED (--encoded_dir), and that path calls make_caption_sampler with NO custom key_fn
(train_lora.py's --encoded_dir branch), so make_caption_sampler's DEFAULT key resolution
applies -- it tries info["latent_filename"] FIRST (stripped to basename-stem). Pre-encoded
latent filenames are an opaque shard-prefixed id (pre_encode_dataset.py:156,
f"{shard_i:02d}{nb:06d}{i:04d}"), NOT the original audio filename -- so THIS sidecar must be
keyed by that latent-id stem, recovered by reading each latent's own .json sidecar (which DOES
carry the original 'relpath', written by pre_encode_dataset.py's own metadata dict) and hashing
it the same way goa_caption_task.py's key() does: sha1(relpath) -> Flamingo/Granite json lookup.

T1 = the corpus-wide genre-hint text used for both the Flamingo and Granite passes (ground
     truth, not classifier-inferred -- no effnet features exist for this corpus, and we don't
     need them: we KNOW the genre, unlike goa where T1 comes from effnet_genre400/moodtheme).
T2 = one random variant from each of granite/<key>.json's short_genremood / short_technical /
     short_mood lists, comma-joined SA3-prompt-style. Seeded by key for reproducible builds.
T3 = json/<key>.json's captions.full, trimmed to the last complete sentence (same
     generation-length-cap mid-sentence truncation issue as goa; reuses the same fix).

Run (mir venv, no torch needed): mir/bin/python eval/build_suomisoundi_sidecar.py
"""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

GENRE_HINT = "suomisoundi, an eclectic Finnish sub-genre of psychedelic goa trance"

LATENTS = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/suomisoundi_latents")
CAPTIONS = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/suomisoundi_captions")


def _last_complete_sentence(text):
    """Same fix as build_goa_archive_sidecar.py -- Flamingo generation is length-capped, so
    the raw text routinely ends mid-clause; trim to the last real sentence boundary."""
    if not text:
        return text
    ends = [m.end() for m in re.finditer(r"[.!?](?:\"|')?(?:\s|$)", text)]
    if not ends:
        return text.strip()
    return text[:ends[-1]].strip()


def _t2_from_granite(entry, rng):
    parts = []
    for field in ("short_genremood", "short_technical", "short_mood"):
        variants = entry.get(field) or []
        if variants:
            parts.append(rng.choice(variants))
    return ", ".join(parts) if parts else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap tracks (smoke test)")
    ap.add_argument("--out", type=Path,
                    default=LATENTS.parent / "suomisoundi_caption_sidecar.json")
    args = ap.parse_args()

    latent_jsons = sorted(p for p in LATENTS.glob("*.json"))
    if args.limit:
        latent_jsons = latent_jsons[: args.limit]
    print(f"[sidecar] {len(latent_jsons)} pre-encoded latents")

    table = {}
    n_t2 = n_t3 = n_no_source = 0
    for i, lj in enumerate(latent_jsons):
        latent_id = lj.stem  # matches info["latent_filename"]'s basename-stem at train time
        meta = json.loads(lj.read_text())
        rel = meta.get("relpath")
        if not rel:
            n_no_source += 1
            continue
        key = hashlib.sha1(rel.encode()).hexdigest()

        t1 = GENRE_HINT

        t2 = None
        granite_path = CAPTIONS / "granite" / f"{key}.json"
        if granite_path.exists():
            rng = random.Random(key)  # deterministic per-track, varied across the corpus
            t2 = _t2_from_granite(json.loads(granite_path.read_text()), rng)
            if t2:
                n_t2 += 1

        t3 = None
        flamingo_path = CAPTIONS / "json" / f"{key}.json"
        if flamingo_path.exists():
            fentry = json.loads(flamingo_path.read_text())
            raw_t3 = (fentry.get("captions") or {}).get("full")
            t3 = _last_complete_sentence(raw_t3) if raw_t3 else None
            if t3:
                n_t3 += 1

        table[latent_id] = {"t1": t1, "t2": t2, "t3": t3}

        if (i + 1) % 500 == 0:
            print(f"[sidecar] {i + 1}/{len(latent_jsons)}  t2={n_t2} t3={n_t3}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(table, indent=1))
    print(f"[sidecar] DONE: {len(table)} tracks -> {args.out}")
    print(f"[sidecar] coverage: t1={len(table)} (fixed genre-hint) t2={n_t2} t3={n_t3} "
          f"(no source relpath for {n_no_source} latents)")


if __name__ == "__main__":
    main()
