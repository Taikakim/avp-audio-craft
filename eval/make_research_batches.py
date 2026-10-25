#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-25)
"""make_research_batches.py -- split the ai-music track lists into JSON files of 50 tracks for an external research agent
(web search) to fill in genre / year / label / album, as a correction pass over the Flamingo + Granite captions.

One entry per TRACK (not per caption): artist / title / album / year / genre as tagged in the source file, our measured
tempo, and the genre tags our captioners currently give it, plus an empty `research` block for the agent. Tracks are
sorted by set, artist and album so one file tends to hold whole releases. The merge-back reads `research` by `id`
(= "<set>/<track folder name>", the same key as the analysed track folder).

  mir/mir/bin/python eval/make_research_batches.py --out /run/media/kim/Kosmos/captions/aimusic_captions/research_batches
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from granite_local_pass import grid_bpm  # noqa: E402

ROOT = "/run/media/kim/Mantu/ai-music"
SETS = ["Chill Dataset", "organic dance", "Prog & Psytechno Dataset", "Progressive Trance & Melodic Techno"]
CAPS = "/run/media/kim/Kosmos/captions/aimusic_captions"

INSTRUCTIONS = (
    "For each track, look up the released recording (artist + title, album if given) and fill its `research` block. "
    "Use reliable sources (Discogs, Bandcamp, Beatport, the label's own page, MusicBrainz). Genre: the style the "
    "release is filed under, as specific as the sources allow (e.g. 'progressive psytrance', 'psychill', "
    "'melodic techno'), not a generic 'electronic'. year = original release year of this version (a remix has its own "
    "year). Leave a field null when you cannot verify it; do not guess. confidence: high / medium / low for the block "
    "as a whole. sources: the URLs you used. If the tagged artist/title looks wrong for the release, say so in notes. "
    "Do not change any field outside `research`."
)
RESEARCH = {"genre": None, "subgenres": [], "year": None, "label": None, "album": None, "remix_of": None,
            "artist_country": None, "notes": None, "sources": [], "confidence": None}


def tags(path):
    import mutagen
    try:
        m = mutagen.File(path, easy=True)
        t = dict(m.tags) if m is not None and m.tags else {}
    except Exception:
        t = {}
    return {k: str((t.get(k) or [""])[0]) for k in ("artist", "title", "album", "date", "genre", "albumartist")}


def caption_genres():
    """{(set, track): {"genre_hint": str, "granite": [short_genremood...]}} over both captions of a track."""
    out = {}
    for p in glob.glob(os.path.join(CAPS, "json", "*.json")):
        d = json.load(open(p))
        top, rest = d["rel"].split("/", 1)
        if top not in SETS:
            continue
        name = os.path.dirname(rest) if os.path.basename(rest).startswith("full_mix.") else os.path.splitext(rest)[0]
        e = out.setdefault((top, name), {"genre_hint": None, "granite": []})
        e["genre_hint"] = e["genre_hint"] or d.get("genre_hint")
        g = os.path.join(CAPS, "granite", os.path.basename(p))
        if os.path.exists(g):
            for v in json.load(open(g)).get("short_genremood", []):
                if v not in e["granite"]:
                    e["granite"].append(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=50)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    caps = caption_genres()
    tracks = []
    for s in SETS:
        for tdir in sorted(glob.glob(os.path.join(glob.escape(os.path.join(ROOT, s)), "*", ""))):
            name = os.path.basename(tdir.rstrip("/"))
            src = [p for p in glob.glob(os.path.join(glob.escape(os.path.join(ROOT, s, name)) + ".*"))
                   if not p.endswith((".INFO", ".lock"))]
            t = tags(src[0]) if src else {}
            artist, title = t.get("artist", ""), t.get("title", "")
            if not (artist and title) and " - " in name:   # fall back to the "NNN. Artist - Title" folder name
                artist, title = name.split(". ", 1)[-1].split(" - ", 1)
            c = caps.get((s, name), {})
            bpm = grid_bpm(tdir.rstrip("/"))
            tracks.append({"id": f"{s}/{name}", "set": s, "artist": artist, "title": title,
                           "album": t.get("album") or None, "albumartist": t.get("albumartist") or None,
                           "tagged_year": t.get("date") or None, "tagged_genre": t.get("genre") or None,
                           "measured_bpm": round(bpm) if bpm else None,
                           "current_genre_hint": c.get("genre_hint"), "current_caption_genres": c.get("granite", [])[:4],
                           "research": dict(RESEARCH)})
    tracks.sort(key=lambda r: (r["set"], (r["albumartist"] or r["artist"]).lower(), r["album"] or "", r["id"]))
    n = 0
    for i in range(0, len(tracks), a.size):
        n += 1
        part = tracks[i:i + a.size]
        with open(os.path.join(a.out, f"research_batch_{n:03d}.json"), "w") as f:
            json.dump({"batch": n, "instructions": INSTRUCTIONS, "tracks": part}, f, ensure_ascii=False, indent=1)
    print(f"{len(tracks)} tracks -> {n} files in {a.out}; with album {sum(bool(t['album']) for t in tracks)}, "
          f"with tagged year {sum(bool(t['tagged_year']) for t in tracks)}")


if __name__ == "__main__":
    sys.exit(main())
