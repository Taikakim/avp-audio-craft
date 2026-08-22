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

THIS MAP HOLDS ONLY THE METADATA CLAUSE. The corpus-level genre string stays where it was, as
goa_caption_task.py's --genre-hint, and the two COMPOSE there ("This track's genre is: goa trance...
According to the actual ID3 metadata... release year: 1995"). Emitting the corpus string as a map
VALUE for un-metadata'd tracks was the first design and it is wrong in a way that hides: a track with
a year but no genre tags would have replaced the genre hint with a bare year, dropping genre
grounding on exactly the tracks that looked best covered. A track absent from this map falls through
to the global hint and is no worse off than today.

KEY = sha1 of the audio path RELATIVE to --archive, matching goa_caption_task.py:65 exactly. Same
keying contract as the shard maker; a mismatch here means the hint silently never reaches the track.

USAGE (local — the .INFOs live beside the source audio):
  python3 eval/build_caption_hint_map.py \
      --archive /run/media/kim/Mantu/ai-music/Goa_Separated \
      --audio-name full_mix.flac \
      --out lumi/goa_src_hint_map.json
Then pass BOTH to the caption job: --genre-hint-map <this> --genre-hint '<corpus genre string>'.
Only stdlib.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path


# Electronic-family substrings a genre tag must contain to be stated. NOT a taxonomy — a wrong-match
# filter. mir fills genres by fuzzy release lookup, and when it matches the wrong release the tag is
# not subtly off, it is "black metal" / "k-rap" / "garage rock" on a goa track (~3.5% of tag
# instances, 2026-08-18). Such a tag directly CONTRADICTS the corpus genre hint it is composed with,
# which is worse than saying nothing: an unstated genre falls back to a correct global hint, a stated
# wrong one overrides it. Legitimate neighbours (ambient, dub, downtempo, idm, space music) are kept
# deliberately — this corpus really does contain them.
GENRE_ALLOW = ("goa", "psy", "trance", "techno", "acid", "ambient", "downtempo", "electronic",
               "dub", "chill", "breakbeat", "edm", "dance", "idm", "house", "tribal", "world",
               "experimental", "drum", "bass", "minimal", "progressive", "forest", "dark",
               "space", "electro", "synth", "new age", "trip hop")

# Goa/psytrance did not exist before roughly 1990 (Goa Gil's parties, the first Dragonfly/Matsuri
# releases). A 1968 or 1979 "release year" on a track in this corpus is a fuzzy-match error, not a
# rarity, and stating it would teach the model that goa is a 1960s genre.
MIN_PLAUSIBLE_YEAR = 1988

AUDIO_EXT = (".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus", ".aiff", ".aif")


def metadata_sentence(info: dict, fields=("year", "genres"), stats=None) -> str:
    """mir's {metadata} substitution, with the tag-genre fallback this corpus needs.

    mir reads existing.get('genres'); Goa_Separated carries its tags in track_metadata_genre on many
    tracks (genres 71% vs track_metadata_genre on others), so taking only the first field would drop
    the genre for a slice of the corpus with no error.
    """
    parts = []
    year = info.get("release_year") or info.get("track_metadata_year")
    if "year" in fields and year:
        try:
            yi = int(str(year)[:4])
        except (TypeError, ValueError):
            yi = None
        if yi and yi >= MIN_PLAUSIBLE_YEAR:
            parts.append(f"release year: {yi}")
        elif stats is not None:
            stats["dropped_year"] = stats.get("dropped_year", 0) + 1
    # LABEL IS OFF BY DEFAULT and that is deliberate. It is the least reliable field here: mir fills
    # it by fuzzy release match, and a wrong match is undetectable downstream -- Ayahuasca's 1994
    # "Digital Alchemy" comes back as "XL Recordings", a UK indie label with no goa catalogue. A
    # wrong label in a training caption is a falsehood the model learns, exactly like the wrong
    # decade this whole pass exists to remove. Year is present on ~100% of tracks and is the field
    # Kim actually asked for; genres are self-consistent where present. Opt label back in with
    # --fields year,genres,label once someone has audited it.
    label = info.get("label")
    if "label" in fields and label:
        parts.append(f"label: {label}")
    tags = info.get("genres") or info.get("track_metadata_genre")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if "genres" in fields and tags:
        keep = [str(x) for x in tags if any(f in str(x).lower() for f in GENRE_ALLOW)]
        if stats is not None and len(keep) < len(tags):
            stats["dropped_tags"] = stats.get("dropped_tags", 0) + (len(tags) - len(keep))
        if keep:
            parts.append(f"genres: {', '.join(keep)}")
    if not parts:
        return ""
    return f"According to its release metadata: {'; '.join(parts)}."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True, type=Path,
                    help="corpus root; keys are sha1 of the audio path RELATIVE to this")
    ap.add_argument("--audio-name", default=None,
                    help="exact audio filename inside each track dir. Pins ONE container format; "
                         "prefer --audio-stem unless you know the corpus is uniform.")
    ap.add_argument("--audio-stem", default="full_mix",
                    help="basename WITHOUT extension of the audio in each track dir (default "
                         "full_mix). Matches any audio extension, which is what this corpus needs: "
                         "Goa_Separated is 71%% flac, 16%% mp3, 11%% ogg, plus m4a/wav/aiff. Keying "
                         "on one extension would build a map covering only that slice, and the "
                         "tracks it missed would fall back to the global hint with no error.")
    ap.add_argument("--info-suffix", default=".INFO")
    ap.add_argument("--fields", default="year,genres",
                    help="which metadata fields to state (year,genres,label). Default omits label "
                         "-- see metadata_sentence() for why.")
    ap.add_argument("--rel-prefix", default="",
                    help="prepended to each path's archive-relative form BEFORE hashing. Needed "
                         "whenever the corpus sits at a different depth remotely than locally: the "
                         "goa_src upload used `rsync -R`, so LUMI's --archive root is "
                         "/scratch/.../goa_src and rel paths there begin "
                         "'run/media/kim/Mantu/ai-music/Goa_Separated/', while locally the same "
                         "track is directly under the Goa_Separated dir. Wrong prefix = every key "
                         "misses = every track silently falls back to the global hint.")
    ap.add_argument("--verify-against", type=Path, default=None,
                    help="dir of existing caption jsons (named <key>.json). Reports how many "
                         "computed keys actually HIT. Run this before trusting a --rel-prefix: a "
                         "keying mismatch produces no error at any later stage, it just produces "
                         "unhinted captions that look fine.")
    ap.add_argument("--from-folders", action="store_true",
                    help="FOLDER-NAME MODE (Kim 2026-08-22, the ai-music corpus): take every audio "
                         "file under --archive and use its TOP-LEVEL folder as the hint — those "
                         "folder names are real curation ('Full-on, Psytrance', 'Proto-trance, New "
                         "Beat, Sunset Moody'), not path noise. Ignores .INFO sidecars entirely, "
                         "since a freshly-rsynced archive has none. "
                         "NOTE THE DISTINCTION THAT MATTERS: this feeds the folder name to Music "
                         "Flamingo as GROUND TRUTH IT SHOULD ASSUME, so it still describes the "
                         "audio it hears. It is NOT a caption derived from a folder name — that is "
                         "exactly what made the bigset's granite tier measure NOT GROUNDED (1.24x "
                         "rare-term recall vs chance).")
    ap.add_argument("--folder-depth", type=int, default=1,
                    help="how many leading path components form the hint (default 1 = top folder)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="top-level folder to skip (repeatable), e.g. 'Goa Dataset'")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    fields = tuple(f.strip() for f in a.fields.split(",") if f.strip())
    out, stats = {}, {"with_meta": 0, "none": 0, "no_info": 0}
    years = {}

    if a.from_folders:
        skip = set(a.exclude)
        per_folder = {}
        for root, _dirs, files in os.walk(a.archive):
            for f in files:
                if os.path.splitext(f)[1].lower() not in AUDIO_EXT:
                    continue
                rel = str((Path(root) / f).relative_to(a.archive))
                parts = Path(rel).parts
                if not parts or parts[0] in skip:
                    continue
                hint = ", ".join(parts[:a.folder_depth])
                key = hashlib.sha1((a.rel_prefix + rel).encode()).hexdigest()
                out[key] = hint
                per_folder[hint] = per_folder.get(hint, 0) + 1
        if not out:
            raise SystemExit(f"[hint-map] FATAL: no audio found under {a.archive}")
        a.out.write_text(json.dumps(out, ensure_ascii=False))
        print(f"[hint-map] {len(out)} tracks from {len(per_folder)} folders -> {a.out}")
        for h, n in sorted(per_folder.items(), key=lambda kv: -kv[1]):
            print(f"  {n:6d}  {h}")
        return

    for root, _dirs, files in os.walk(a.archive):
        if a.audio_name:
            if a.audio_name not in files:
                continue
            name = a.audio_name
        else:
            cand = sorted(f for f in files
                          if os.path.splitext(f)[0] == a.audio_stem
                          and os.path.splitext(f)[1].lower() in AUDIO_EXT)
            if not cand:
                continue
            name = cand[0]
        audio = Path(root) / name
        rel = a.rel_prefix + str(audio.relative_to(a.archive))
        key = hashlib.sha1(rel.encode()).hexdigest()
        infos = [f for f in files if f.endswith(a.info_suffix)]
        info = {}
        if infos:
            try:
                info = json.load(open(Path(root) / infos[0]))
            except Exception:
                info = {}
        else:
            stats["no_info"] += 1
        sent = metadata_sentence(info, fields, stats)
        if sent:
            out[key] = sent
            stats["with_meta"] += 1
            # Count the year we actually STATED, parsed back out of the sentence — not the raw
            # metadata value. Reading the source instead reported 1960s/1970s tracks in the decade
            # spread that the plausibility guard had already dropped, i.e. the summary described the
            # input rather than the artifact. Same class as auditing a stale sidecar.
            m = re.search(r"release year: (\d{4})", sent)
            if m:
                dec = int(m.group(1)) // 10 * 10
                years[dec] = years.get(dec, 0) + 1
        else:
            stats["none"] += 1

    total = sum(stats[k] for k in ("with_meta", "none"))
    print(f"tracks found: {total}")
    print(f"  per-track metadata hint : {stats['with_meta']} ({stats['with_meta']/max(1,total):.1%})")
    print(f"  no metadata (-> global) : {stats['none']}")
    if stats.get("dropped_year") or stats.get("dropped_tags"):
        print(f"  wrong-match guards: dropped {stats.get('dropped_year', 0)} implausible year(s) "
              f"(<{MIN_PLAUSIBLE_YEAR}) and {stats.get('dropped_tags', 0)} off-family genre tag(s)")
    if stats["no_info"]:
        print(f"  (track dirs with no {a.info_suffix}: {stats['no_info']})")
    if years:
        print(f"  decade spread of hinted tracks: {dict(sorted(years.items()))}")
    if a.verify_against:
        have = {os.path.splitext(e.name)[0] for e in os.scandir(a.verify_against)
                if e.name.endswith(".json")}
        hit = len(set(out) & have)
        print(f"\n--verify-against {a.verify_against}: {len(have)} caption json(s) present, "
              f"{hit} of our {len(out)} keys HIT ({hit/max(1,len(out)):.1%})")
        if have and hit == 0:
            print("  ^ ZERO hits. --rel-prefix is wrong (or --archive is). Do NOT ship this map: "
                  "every lookup would miss and every track would fall back to the global hint, "
                  "which is indistinguishable from success in every downstream artifact.")
    a.out.write_text(json.dumps(out, ensure_ascii=False))
    print(f"\nwrote {len(out)} hints -> {a.out}")
    ex = list(out.items())[:2]
    for k, v in ex:
        print(f"  {k[:12]}  {v[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
