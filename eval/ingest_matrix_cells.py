#!/usr/bin/env python3
"""
ingest_matrix_cells.py -- LOCAL ingest for LUMI's general model_matrix render batches
(lumi/render_matrix_cells.py, per CONTINUITY's 2026-07-24 fix note: the LUMI eval-render
tail that self-adds control/ to sys.path). Sibling to ingest_native_cells.py, same design,
different source layout:

  LUMI job writes /renders/matrix_cells/, per cell:
    <clip>.wav + <clip>.z0.npy + <clip>.mmline.json  -- ONE manifest-schema JSON object
    per clip (not one combined file), same fields append_manifest() expects
    (model/ckpt/cfg/strength/prompt_id/prompt_text/seed/steps/duration/file).
  Kim rsyncs that dir home, then runs THIS to fold the cells onto the board.

Per .mmline.json sidecar, this ingest:
  1. transcodes the sibling .wav -> .m4a DIRECTLY into STAGING (the served model_matrix
     dir the pages read from -- not just RENDER_DIR; skips the render-to-staging sync
     gap documented in WORKLOG 2026-07-29/30 by writing straight to the served path);
     skips if the .m4a already exists.
  2. archives the .wav + .z0.npy to Mantu RENDER_DIR (where local originals live).
  3. dedup-appends the manifest line by manifest_key (skips a cell already on the board).
Then, with --rebuild, regenerates the board (build_model_matrix.py) so the cells light.

Reuse: STAGING / MANIFEST / RENDER_DIR / manifest_key / load_existing_keys /
append_manifest / transcode via model_matrix_gen (imported as `mmg`), same as
ingest_native_cells.py -- one source of truth for paths/dedup/transcode.

Run:  eval/ingest_matrix_cells.py --src <pulled_matrix_cells_dir> [--only-prefix adamw_]
                                   [--dry-run] [--no-archive] [--rebuild]
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_matrix_gen as mmg  # noqa: E402  (torch is lazy inside mmg.main(); safe)

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "Misc/build_model_matrix.py"


def ingest(src: Path, only_prefix: str = "", dry_run: bool = False, archive: bool = True):
    sidecars = sorted(src.glob("*.mmline.json"))
    if only_prefix:
        sidecars = [p for p in sidecars if p.name.startswith(only_prefix)]
    if not sidecars:
        sys.exit(f"[ingest] no *.mmline.json in {src}" + (f" matching '{only_prefix}*'" if only_prefix else ""))
    existing = mmg.load_existing_keys()
    if not dry_run:
        mmg.STAGING.mkdir(parents=True, exist_ok=True)
        if archive:
            mmg.RENDER_DIR.mkdir(parents=True, exist_ok=True)
    n_new = n_dup = n_missing = 0
    for sc in sidecars:
        e = json.loads(sc.read_text())
        m4a = e["file"]
        wav = sc.with_suffix("").with_suffix(".wav")  # <clip>.mmline.json -> <clip>.wav
        key = mmg.manifest_key(e)
        if key in existing:
            n_dup += 1
            continue
        if not wav.exists():
            print(f"[ingest] MISSING wav for {m4a}: {wav.name}")
            n_missing += 1
            continue
        print(f"[ingest] {'(dry) ' if dry_run else ''}{m4a}")
        if not dry_run:
            m4a_path = mmg.STAGING / m4a
            if not m4a_path.exists():
                mmg.transcode(wav, m4a_path)
            if archive:
                for f in (wav, wav.with_suffix(".z0.npy")):
                    dest = mmg.RENDER_DIR / f.name
                    if f.exists() and not dest.exists():
                        shutil.copy2(f, dest)
                    m4a_dest = mmg.RENDER_DIR / m4a
                    if not m4a_dest.exists():
                        shutil.copy2(m4a_path, m4a_dest)
            mmg.append_manifest(e)
        existing.add(key)
        n_new += 1
    tail = " [DRY-RUN, nothing written]" if dry_run else ""
    print(f"[ingest] {n_new} new, {n_dup} already-present, {n_missing} missing-wav "
          f"(of {len(sidecars)} sidecars){tail}")
    return n_new, n_dup, n_missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path,
                    help="pulled /renders/matrix_cells/ dir (wavs + z0 + *.mmline.json)")
    ap.add_argument("--only-prefix", default="", help="only ingest clips whose filename starts with this")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--no-archive", action="store_true",
                    help="skip copying wav+z0+m4a to Mantu RENDER_DIR (staged m4a+manifest only)")
    ap.add_argument("--rebuild", action="store_true",
                    help="run build_model_matrix.py after a non-empty ingest")
    a = ap.parse_args()
    n_new, _, _ = ingest(a.src.expanduser(), only_prefix=a.only_prefix,
                         dry_run=a.dry_run, archive=not a.no_archive)
    if a.rebuild and not a.dry_run and n_new:
        print("[ingest] rebuilding board...")
        subprocess.run([sys.executable, str(BUILD)], check=True)
        print("[ingest] board rebuilt -- ship with the standard eval-site sync when ready")


if __name__ == "__main__":
    main()
