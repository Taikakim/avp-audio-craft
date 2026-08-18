#!/usr/bin/env python3
"""build_caption_hint_map.py — per-track caption hints from real ID3/release metadata.

WHY (Kim direct, 2026-08-18): "we have the very fine system for hints in the MIR project, let's use
that?" — mir's pipeline.py::_interpolate_genres() substitutes {metadata} with the track's actual
release year, label and tag genres. `lumi/goa_caption_task.py` never had access to it: it accepts
ONE global --genre-hint string per corpus run, so every track in a corpus gets the same anchor.

That single-string limitation is what produced today's mess from both directions:
  * goa big-set: no hint at all -> Music Flamingo guessed, 1.2% of a goa corpus mentioned goa.
  * A global hint fixes genre but asserts one era for everyone. Fine for the big-set (uniformly
    1990s), WRONG for Goa_Separated, which spans 1980s-2020s: 48% 90s, 26% 2000s, 26% 2010s+.
Per-track metadata solves both at once, and puts the year INTO the captioner rather than patching it
into the captions afterwards (eval/inject_year_into_captions.py, which exists because the bigset had
no better option).

Real examples of what this emits instead of one global string:
    Prana - Dervish (Spiral mix)      release year: 1995; genres: Ambient, Downtempo, Dub, Goa Trance
    Galaktik Wizdom - Mushroom Lem.   release year: 2024
    Shpongle - Nothing Lasts...       release year: 2005; genres: Ambient, Downtempo, Psybient
A global "goa trance" hint would have told Music Flamingo the wrong thing about two of those three.

FALLBACK CHAIN, because coverage is partial: per-track metadata -> --default-hint (the corpus-level
string) -> nothing. A track with no metadata is no worse off than it is today.

KEY = sha1 of the audio path RELATIVE to --archive, matching goa_caption_task.py:65 exactly. Same
keying contract as the shard maker; a mismatch here means the hint silently never reaches the track.

USAGE (local — the .INFOs live beside the source audio):
  python3 eval/build_caption_hint_map.py \
      --archive /run/media/kim/Mantu/ai-music/Goa_Separated \
      --audio-name full_mix.flac \
      --out lumi/goa_src_hint_map.json \
      --default-hint 'goa trance and psytrance, psychedelic electronic dance music'
Only stdlib.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


def metadata_sentence(info: dict) -> str:
    """mir's {metadata} substitution, with the tag-genre fallback this corpus needs.

    mir reads existing.get('genres'); Goa_Separated carries its tags in track_metadata_genre on many
    tracks (genres 71% vs track_metadata_genre on others), so taking only the first field would drop
    the genre for a slice of the corpus with no error.
    """
    parts = []
    year = info.get("release_year") or info.get("track_metadata_year")
    if year:
        parts.append(f"release year: {str(year)[:4]}")
    label = info.get("label")
    if label:
        parts.append(f"label: {label}")
    tags = info.get("genres") or info.get("track_metadata_genre")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if tags:
        parts.append(f"genres: {', '.join(str(t) for t in tags)}")
    if not parts:
        return ""
    return ("According to the actual ID3 metadata, this is the release year, label and genres of "
            f"the track: {'; '.join(parts)}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True, type=Path,
                    help="corpus root; keys are sha1 of the audio path RELATIVE to this")
    ap.add_argument("--audio-name", default="full_mix.flac",
                    help="the audio file inside each track dir (default full_mix.flac)")
    ap.add_argument("--info-suffix", default=".INFO")
    ap.add_argument("--default-hint", default=None,
                    help="corpus-level fallback for tracks with no usable metadata")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    out, stats = {}, {"with_meta": 0, "fallback": 0, "none": 0, "no_info": 0}
    years = {}
    for root, _dirs, files in os.walk(a.archive):
        if a.audio_name not in files:
            continue
        audio = Path(root) / a.audio_name
        key = hashlib.sha1(str(audio.relative_to(a.archive)).encode()).hexdigest()
        infos = [f for f in files if f.endswith(a.info_suffix)]
        info = {}
        if infos:
            try:
                info = json.load(open(Path(root) / infos[0]))
            except Exception:
                info = {}
        else:
            stats["no_info"] += 1
        sent = metadata_sentence(info)
        if sent:
            out[key] = sent
            stats["with_meta"] += 1
            y = info.get("release_year") or info.get("track_metadata_year")
            if y:
                try:
                    years[int(str(y)[:4]) // 10 * 10] = years.get(int(str(y)[:4]) // 10 * 10, 0) + 1
                except Exception:
                    pass
        elif a.default_hint:
            out[key] = a.default_hint
            stats["fallback"] += 1
        else:
            stats["none"] += 1

    total = sum(stats[k] for k in ("with_meta", "fallback", "none"))
    print(f"tracks found: {total}")
    print(f"  per-track metadata hint : {stats['with_meta']} ({stats['with_meta']/max(1,total):.1%})")
    print(f"  corpus-level fallback   : {stats['fallback']}")
    print(f"  no hint at all          : {stats['none']}")
    if stats["no_info"]:
        print(f"  (track dirs with no {a.info_suffix}: {stats['no_info']})")
    if years:
        print(f"  decade spread of hinted tracks: {dict(sorted(years.items()))}")
    a.out.write_text(json.dumps(out, ensure_ascii=False))
    print(f"\nwrote {len(out)} hints -> {a.out}")
    ex = list(out.items())[:2]
    for k, v in ex:
        print(f"  {k[:12]}  {v[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
