#!/usr/bin/env python3
"""
ingest_native_cells.py -- LOCAL ingest half of the native-length-on-LUMI reroute
(Kim direct 2026-07-21: the T>=2048 native model-matrix cells whose long-sequence
attention VRAM crashed the local 16GB display card now render on LUMI; this folds
them back onto the board).

Split (WINTERMUTE = local ingest, CONTINUITY = LUMI render):
  LUMI job (lumi/render_native_cells.py + lumi/sbatch/native_cells_hq.sbatch) writes
  /renders/native_cells/ containing, per cell:
    <clip>.wav + <clip>.z0.npy   -- clip byte-follows model_matrix_gen.clip_name();
                                    natives (steps=24=default, so NO __st token):
                                    {label}__{tag}__cfg7__w100__kl_bracket_0__s1000__d<D>.wav
    native_manifest.jsonl        -- ready-to-append lines in the model_matrix schema
                                    (+ "duration_mode":"native", "file":<m4a name>).
  Kim rsyncs that dir home (his key), then runs THIS to fold the cells onto the board.

Per native_manifest.jsonl line, this ingest:
  1. transcodes the sibling .wav -> .m4a (aac 192k) into the served model-matrix dir
     (STAGING, which symlinks to ~/evals_aac/model_matrix -- where the page reads and
     the eval-site ship pushes from); skips if the .m4a already exists.
  2. archives the .wav + .z0.npy to Mantu RENDER_DIR (where local wav/z0 originals live).
  3. dedup-appends the manifest line by manifest_key (skips a cell already on the board).
Then, with --rebuild, regenerates the board (build_model_matrix.py) so the cells light.
Shipping is a SEPARATE step (needs Kim's DreamHost key) -- run the standard eval-site
sync after this reports clean.

Reuse: STAGING / MANIFEST / RENDER_DIR / manifest_key / load_existing_keys /
append_manifest / transcode are all referenced through model_matrix_gen (imported as
`mmg`) -- ONE source of truth, so the transcode flags, paths, and dedup-key format can
never drift from the local renderer. (torch is imported lazily inside mmg.main(), so
importing the module here is torch-free.)

Run:  eval/ingest_native_cells.py --src <pulled_native_cells_dir> [--dry-run]
                                   [--no-archive] [--rebuild]
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


def _wav_for(m4a_name: str) -> str:
    """The sibling .wav name for a manifest 'file' m4a name."""
    return m4a_name[:-4] + ".wav" if m4a_name.endswith(".m4a") else m4a_name + ".wav"


def ingest(src: Path, dry_run: bool = False, archive: bool = True):
    nm = src / "native_manifest.jsonl"
    if not nm.exists():
        sys.exit(f"[ingest] no native_manifest.jsonl in {src}")
    lines = [json.loads(ln) for ln in nm.read_text().splitlines() if ln.strip()]
    existing = mmg.load_existing_keys()
    if not dry_run:
        mmg.STAGING.mkdir(parents=True, exist_ok=True)
        if archive:
            mmg.RENDER_DIR.mkdir(parents=True, exist_ok=True)
    n_new = n_dup = n_missing = 0
    for e in lines:
        m4a = e["file"]
        wav = src / _wav_for(m4a)
        key = mmg.manifest_key(e)
        if key in existing:
            n_dup += 1
            continue
        if not wav.exists():
            print(f"[ingest] MISSING wav for {m4a}: {wav.name}")
            n_missing += 1
            continue
        print(f"[ingest] {'(dry) ' if dry_run else ''}{m4a}  (T~{e.get('duration')}s)")
        if not dry_run:
            m4a_path = mmg.STAGING / m4a
            if not m4a_path.exists():
                mmg.transcode(wav, m4a_path)
            if archive:
                for f in (wav, wav.with_suffix(".z0.npy")):
                    dest = mmg.RENDER_DIR / f.name
                    if f.exists() and not dest.exists():
                        shutil.copy2(f, dest)
            mmg.append_manifest(e)
        existing.add(key)
        n_new += 1
    tail = " [DRY-RUN, nothing written]" if dry_run else ""
    print(f"[ingest] {n_new} new, {n_dup} already-present, {n_missing} missing-wav "
          f"(of {len(lines)} manifest lines){tail}")
    return n_new, n_dup, n_missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path,
                    help="pulled /renders/native_cells/ dir (wavs + z0 + native_manifest.jsonl)")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--no-archive", action="store_true",
                    help="skip copying wav+z0 to Mantu RENDER_DIR (m4a+manifest only)")
    ap.add_argument("--rebuild", action="store_true",
                    help="run build_model_matrix.py after a non-empty ingest")
    a = ap.parse_args()
    n_new, _, _ = ingest(a.src.expanduser(), dry_run=a.dry_run, archive=not a.no_archive)
    if a.rebuild and not a.dry_run and n_new:
        print("[ingest] rebuilding board...")
        subprocess.run([sys.executable, str(BUILD)], check=True)
        print("[ingest] board rebuilt -- ship with the standard eval-site sync when ready")


if __name__ == "__main__":
    main()
