#!/usr/bin/env python3
"""granite_avp_pass.py — genre-anchored Granite T2 compression for the avp corpus.

Kim 2026-07-09: use the MIR-pipeline method where the reviser is 'encouraged about
the correct genre, since they will hallucinate EDM otherwise' (pipeline.py
_interpolate_genres does this via essentia_genre — absent from avp .INFOs, so the
anchor is supplied per-alias here):
  Summamutikka  -> "oldschool goa trance"
  Aavepyörä/other -> "suomisoundi (Finnish freeform psychedelic electronic)"
    (Kim: "I'd hate to say 'suomisoundi' but that's probably fair.")

Reads music_flamingo_* from each track .INFO, writes granite_t2 back into the .INFO
and builds the tiered caption sidecar for train_lora --caption_sidecar:
  t1 = Kim's style caption + trigger   t2 = Granite 6-10 word tag + trigger
  t3 = Flamingo genre_mood (raw)       (keyed by latent stem, crops share track caption)

Run (mir venv, CPU-only — Granite-tiny is 130MB):
  /home/kim/Projects/mir/mir/bin/python eval/granite_avp_pass.py
"""
import argparse
import json
import glob
import os
import sys
import unicodedata

sys.path.insert(0, "/home/kim/Projects/mir/src")

AVP_ROOT = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed"
LATENTS = "/run/media/kim/Kosmos/latents_avp"
OUT_SIDECAR = os.path.join(LATENTS, "captions_tiered.json")
GRANITE = ("/home/kim/Projects/mir/models/LMM/granite-4.0-h-tiny-GGUF/"
           "granite-4.0-h-tiny-Q8_0.gguf")


def anchor_for(track: str) -> str:
    if "summamutikka" in track.lower():
        return "oldschool goa trance"
    return "suomisoundi (Finnish freeform psychedelic electronic music)"


def style_t1(track: str) -> str:
    if "summamutikka" in track.lower():
        return "oldschool goa trance, aavepyörä style"
    return "upbeat dance music, aavepyörä style"


# --- parent-track resolution: THE BUG THAT CAPPED COVERAGE AT 284/2394 (fixed 2026-08-17) -------
# `track_t2`/`track_t3` are keyed by the .INFO's TRACK DIRECTORY name, but a latent's
# `source_track` is `"<track>/<variant>"` for every augmented crop (e.g.
# "Aavepyörä - Huedragon (deepest india mix)/tempo+5"). The old lookup used the raw
# `source_track`, so it matched ONLY un-augmented crops -> 284 of 2394 latents got a granite
# caption and the other 2110 silently fell back to t1 (the style+trigger boilerplate). Since the
# bungee ×8 augmentation is most of the corpus, "train AVP on granite prompts" was quietly
# training ~88% of it on the trigger phrase instead.
def parent_track(source_track: str) -> str:
    """Track name with any augmentation-variant path segment stripped."""
    return (source_track or "").split("/")[0]


def _fold(s: str) -> str:
    """Accent/case-insensitive key. The corpus mixes 'Aavepyörä' and 'Aavepyora' spellings, so an
    exact dict hit is not something to rely on -- fold to a canonical form for the fallback."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


def resolve_track(source_track: str, table: dict):
    """Look up a per-track caption for a latent's source_track: exact parent, then accent-folded."""
    tr = parent_track(source_track)
    if tr in table:
        return table[tr]
    folded = {_fold(k): v for k, v in table.items()}
    return folded.get(_fold(tr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar-only", action="store_true",
                    help="Skip the Granite LLM entirely and rebuild the sidecar from the granite_t2 "
                         "ALREADY cached in the .INFOs (167/170 tracks have one). Pure stdlib -- no "
                         "mir venv, no GGUF, no GPU. This is what you want after a keying fix.")
    ap.add_argument("--mf-tier", choices=("full", "genre_mood"), default="full",
                    help="Which Music Flamingo field becomes t3. Kim 2026-08-17 asked for the FULL "
                         "prompts ('we have the full music flamingo prompts, we could use them too "
                         "10%% of the time'), so 'full' is the default; the old behaviour preferred "
                         "genre_mood.")
    ap.add_argument("--no-trigger-on-mf", action="store_true",
                    help="Leave t3 (the Music Flamingo prose) WITHOUT the aavepyörä trigger. Default "
                         "is to append it: the whole point of the AVP corpus is binding that token, "
                         "and a caption that describes the music accurately WITHOUT the trigger "
                         "teaches the model to make this music untriggered -- working against the "
                         "objective. Pass this if you'd rather have 10%% trigger-free captions as a "
                         "regulariser.")
    ap.add_argument("--out", default=OUT_SIDECAR, help=f"sidecar path (default {OUT_SIDECAR})")
    a = ap.parse_args()

    reviser = None
    if not a.sidecar_only:
        from classification.granite_revision import GraniteReviser
        reviser = GraniteReviser(GRANITE)
    track_t2, track_t3 = {}, {}
    infos = sorted(glob.glob(f"{AVP_ROOT}/*/*.INFO"))
    done = skipped = 0
    for ip in infos:
        info = json.load(open(ip))
        track = os.path.basename(os.path.dirname(ip))
        full = info.get("music_flamingo_full")
        gm = info.get("music_flamingo_genre_mood")
        mf = full if a.mf_tier == "full" else (gm or full)
        if not full:
            skipped += 1
            continue
        if info.get("granite_t2"):
            track_t2[track] = info["granite_t2"]
            track_t3[track] = mf
            continue
        if a.sidecar_only:
            # no cached granite for this track and we're not allowed to call the LLM -- record the
            # MF tier anyway so t3 coverage isn't lost, and let the coverage report show the gap.
            track_t3[track] = mf
            skipped += 1
            continue
        anchor = anchor_for(track)
        spec = {"granite_t2": (
            f"A compact 6-10 word music-style tag for an AI music prompt. "
            f"The artist's genre is {anchor} — if the description suggests a "
            f"conflicting generic genre (EDM, house, pop), prefer terms from the "
            f"{anchor} family. Include tempo/mood words from the description. "
            f"Output ONLY the tag, no quotes.")}
        try:
            rev = reviser.revise({"music_flamingo_full": full}, spec)
            t2 = (rev.get("granite_t2") or "").strip().strip('"')
        except Exception as e:
            print(f"[warn] {track}: {e}")
            continue
        if not t2:
            continue
        info["granite_t2"] = t2
        json.dump(info, open(ip, "w"), indent=2)
        track_t2[track] = t2
        track_t3[track] = mf
        done += 1
        if done % 20 == 0:
            print(f"[granite] {done} tracks", flush=True)
    if reviser is not None:
        reviser.close()
    print(f"[granite] compressed {done}, cached {len(track_t2) - done}, no-caption {skipped}")
    print(f"[granite] per-track captions: t2={len(track_t2)} t3={len(track_t3)} of {len(infos)} tracks")

    # sidecar keyed by latent stem. Every crop -- INCLUDING the bungee augs -- resolves its caption
    # through its PARENT track (see parent_track()); the old code keyed on the raw source_track and
    # so covered originals only.
    table = {}
    miss_t2 = miss_t3 = 0
    unresolved = set()
    for j in glob.glob(f"{LATENTS}/*.json"):
        meta = json.load(open(j))
        v = meta.get("variant_name") or meta.get("variant")
        src = meta.get("source_track") or ""
        track = parent_track(src)
        stem = os.path.splitext(os.path.basename(j))[0]
        t2 = resolve_track(src, track_t2)
        t3 = resolve_track(src, track_t3)
        if not t2:
            miss_t2 += 1
            unresolved.add(track)
        if not t3:
            miss_t3 += 1
        trig = "aavepyörä style"
        entry = {"t1": style_t1(track),
                 "t2": (f"{t2}, {trig}" if t2 else None),
                 "t3": (t3 if (not t3 or a.no_trigger_on_mf) else f"{t3.rstrip()} ({trig})")}
        if v and v != "ORIGINAL":
            bpm = meta.get("bpm_essentia")
            if bpm:
                for k in ("t1", "t2"):
                    if entry[k]:
                        entry[k] = f"{entry[k]}, {round(float(bpm))} bpm"
        table[stem] = entry
    json.dump(table, open(a.out, "w"), indent=1, ensure_ascii=False)
    n2 = sum(1 for e in table.values() if e["t2"])
    n3 = sum(1 for e in table.values() if e["t3"])
    n = len(table)
    print(f"[sidecar] {n} entries -> {a.out}")
    print(f"[sidecar] COVERAGE  t2/granite {n2}/{n} ({n2/max(1,n):.1%})   t3/MF {n3}/{n} ({n3/max(1,n):.1%})")
    # A tier that is missing falls back to t1 in make_caption_sampler -- i.e. silently to the
    # style+trigger boilerplate. So partial coverage does not error, it just quietly trains on the
    # wrong captions. Say so loudly.
    if miss_t2 or miss_t3:
        print(f"[sidecar] WARNING: {miss_t2} crops have NO granite caption and {miss_t3} no MF "
              f"caption -- make_caption_sampler falls those back to t1 (style+trigger), so they "
              f"would train on boilerplate, NOT on what you asked for.")
        for t in sorted(unresolved)[:8]:
            print(f"           unresolved track: {t!r}")


if __name__ == "__main__":
    main()
