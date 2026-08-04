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
import json
import glob
import os
import sys

sys.path.insert(0, "/home/kim/Projects/mir/src")

AVP_ROOT = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed"
LATENTS = "/home/kim/Projects/latents_avp"
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


def main():
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
        if not full:
            skipped += 1
            continue
        if info.get("granite_t2"):
            track_t2[track] = info["granite_t2"]
            track_t3[track] = gm or full
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
        track_t3[track] = gm or full
        done += 1
        if done % 20 == 0:
            print(f"[granite] {done} tracks", flush=True)
    reviser.close()
    print(f"[granite] compressed {done}, cached {len(track_t2) - done}, no-caption {skipped}")

    # sidecar keyed by latent stem; ONLY original crops (augs get bpm-suffixed later)
    table = {}
    for j in glob.glob(f"{LATENTS}/*.json"):
        meta = json.load(open(j))
        v = meta.get("variant_name") or meta.get("variant")
        track = meta.get("source_track") or ""
        stem = os.path.splitext(os.path.basename(j))[0]
        t2 = track_t2.get(track)
        t3 = track_t3.get(track)
        entry = {"t1": style_t1(track),
                 "t2": (f"{t2}, aavepyörä style" if t2 else None),
                 "t3": t3}
        if v and v != "ORIGINAL":
            bpm = meta.get("bpm_essentia")
            if bpm:
                for k in ("t1", "t2"):
                    if entry[k]:
                        entry[k] = f"{entry[k]}, {round(float(bpm))} bpm"
        table[stem] = entry
    json.dump(table, open(OUT_SIDECAR, "w"), indent=1, ensure_ascii=False)
    n3 = sum(1 for e in table.values() if e["t3"])
    print(f"[sidecar] {len(table)} entries ({n3} with t3) -> {OUT_SIDECAR}")


if __name__ == "__main__":
    main()
