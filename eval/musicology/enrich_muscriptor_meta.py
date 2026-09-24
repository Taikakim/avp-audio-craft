#!/usr/bin/env python3
"""enrich_muscriptor_meta.py -- back-fill the source track filename onto the muscriptor
full-corpus outputs (Kim 2026-07-24: "add the filenames to the json files ... not sure if
they are retraceable from the IDs" -> they ARE).

The LUMI muscriptor batch (lumi/muscriptor_decode_task.py) writes <id>.mid + <id>.stats.json
keyed ONLY by crop id (e.g. 000000), because the worker never saw the source path -- it read
latents_sa3/<id>.npy. The source path lives in the crop's sibling metadata json,
latents_sa3/<id>.json ("source_path" / "start_sample" / "end_sample" / "source_total_samples"
/ "bpm_madmom"). This joins the two: for every <id>.stats.json it copies those fields in, so
each transcription is traceable to the exact source track + section without the latents dir.

NOTE ~2 crops/track (5400 crops / ~2676 tracks), so `source_track` alone is NOT unique --
`start_sample` disambiguates which section of the track a MIDI came from.

Idempotent: a stats json that already carries "source_path" is left untouched unless --force.
Also writes an index.jsonl (one row per crop: id, source_track, source_path, start/end_sample,
bpm) next to the outputs, for a quick corpus-wide lookup / rename table.

    python eval/musicology/enrich_muscriptor_meta.py \
        --muscriptor-dir /run/media/kim/Kosmos/muscriptor_full \
        [--crop-meta /home/kim/Projects/latents_sa3] [--dry-run] [--force]
"""
import argparse
import json
import os
from pathlib import Path

# fields lifted verbatim from the crop metadata json onto each stats json
SRC_FIELDS = ("source_path", "start_sample", "end_sample",
              "source_total_samples", "bpm_madmom")


def track_of(source_path: str) -> str:
    """The track-folder name, e.g. '/.../Goa_Separated/AZukx - Earth Chakra/full_mix.flac'
    -> 'AZukx - Earth Chakra' (the parent dir, since the leaf is always full_mix.flac)."""
    return os.path.basename(os.path.dirname(source_path)) if source_path else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--muscriptor-dir", required=True,
                    help="dir of <id>.stats.json (+ <id>.mid) pulled from LUMI")
    ap.add_argument("--crop-meta", default="/home/kim/Projects/latents_sa3",
                    help="dir of <id>.json crop metadata carrying source_path (the "
                         "latents_sa3 sidecars)")
    ap.add_argument("--manifest", default=None,
                    help="index jsonl path (default: <muscriptor-dir>/index.jsonl)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="re-enrich even stats jsons that already have source_path")
    a = ap.parse_args()

    mdir = Path(a.muscriptor_dir)
    cmeta = Path(a.crop_meta)
    if not mdir.is_dir():
        raise SystemExit(f"[enrich] FATAL: --muscriptor-dir does not exist: {mdir}")
    if not cmeta.is_dir():
        raise SystemExit(f"[enrich] FATAL: --crop-meta does not exist: {cmeta}")

    stats_files = sorted(mdir.glob("*.stats.json"))
    if not stats_files:
        raise SystemExit(f"[enrich] FATAL: no *.stats.json under {mdir}")

    manifest_path = Path(a.manifest) if a.manifest else (mdir / "index.jsonl")
    enriched = already = missing_meta = bad = 0
    rows = []
    for sf in stats_files:
        cid = sf.name[:-len(".stats.json")]
        try:
            st = json.loads(sf.read_text())
        except Exception as e:
            print(f"[bad-stats] {sf.name}: {e}")
            bad += 1
            continue
        cid = st.get("id", cid)  # trust the recorded id, fall back to filename
        cj = cmeta / f"{cid}.json"
        if not cj.exists():
            print(f"[missing-meta] {cid}: no {cj.name} in crop-meta")
            missing_meta += 1
            continue
        try:
            meta = json.loads(cj.read_text())
        except Exception as e:
            print(f"[bad-meta] {cj.name}: {e}")
            bad += 1
            continue

        src = meta.get("source_path", "")
        row = {"id": cid, "source_track": track_of(src), "source_path": src,
               "start_sample": meta.get("start_sample"),
               "end_sample": meta.get("end_sample"),
               "bpm_madmom": meta.get("bpm_madmom")}
        rows.append(row)

        if "source_path" in st and not a.force:
            already += 1
            continue

        add = {k: meta.get(k) for k in SRC_FIELDS if k in meta}
        add["source_track"] = track_of(src)
        st.update(add)
        if a.dry_run:
            print(f"[would-enrich] {cid} <- {add.get('source_track')!r} "
                  f"@{add.get('start_sample')}")
        else:
            sf.write_text(json.dumps(st))
        enriched += 1

    if not a.dry_run:
        with open(manifest_path, "w") as f:
            for r in sorted(rows, key=lambda r: r["id"]):
                f.write(json.dumps(r) + "\n")

    print(f"\n[enrich] {'DRY-RUN ' if a.dry_run else ''}"
          f"enriched={enriched} already={already} missing-meta={missing_meta} bad={bad} "
          f"| {len(rows)} manifest rows -> {manifest_path}"
          + (" (not written; dry-run)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
