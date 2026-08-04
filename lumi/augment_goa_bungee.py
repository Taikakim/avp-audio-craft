#!/usr/bin/env python3
"""
augment_goa_bungee.py — 8-variant Bungee pitch/tempo augmentation for the GOA corpus (v1).

RUN WITH A BUNGEE-CAPABLE PYTHON (bungee_python importable — see the LUMI PORT RISK
note below):
    <venv>/bin/python lumi/augment_goa_bungee.py <crop-dir> --out <out-dir> [--jobs N]

DESIGN (reuses two proven conventions rather than reinventing them — see
DISCOVERY note at the bottom):
  - Variant table / BPM-cap / peak-norm / resumable-ProcessPool structure from the
    canonical avp augmenter, `mir/src/tools/augment_tracks.py` (8-variant pitch/tempo) —
    **v1 now matches that set EXACTLY** (Kim's ruling 2026-07-23: no +8% tempo variant,
    no combined pitch+tempo variants — keep GOA's recipe identical to the proven avp one).
  - Crop-window-aware slicing (read a WIDER source window, speed-transform it, trim
    back to the parent crop's exact sample count) from `SAO/Misc/augment_slice.py`,
    which already validated this technique against `latents_sa3` crop metadata.

INPUT: a directory of latents_sa3-style crop-metadata JSONs (`<id>.json`, one per
crop, siblings of `<id>.npy`/`<id>.TIMESERIES.npz` — see /home/kim/Projects/latents_sa3
locally for the exact schema; pass the LUMI-staged equivalent dir via the positional
arg). Each JSON carries `source_path` / `start_sample` / `end_sample` /
`source_total_samples` / `bpm_madmom` describing a crop cut from a full-track source
file. `<id>.TIMBRAL.json` sidecars (same dir) are auto-skipped.

For every crop this script, for each of the 8 v1 variants:
  1. computes the required source-side window length so that, AFTER Bungee's
     pitch/speed transform, the rendered output is exactly `crop_len` samples long
     (crop_len = end_sample - start_sample) — i.e. every augmented crop is
     duration-matched to its un-augmented parent, ready for SAME encoding at the
     same T with no extra crop/pad logic downstream (ARTIFACT 2 in the aug8 spec);
  2. reads that window from the source audio, centered on the parent crop's window
     (clamped to the source track's bounds);
  3. pitch-shifts / time-stretches with Bungee, peak-normalizes, trims/pads to
     exactly crop_len, and writes FLAC;
  4. appends a manifest row (crop id, variant, semitones, speed, output path,
     inherited prompt/bpm) for the downstream SAME-encode step.

VARIANTS (v1 — 8 total, IDENTICAL to mir/src/tools/augment_tracks.py's set; edit the
two constants below to change it):
  pitch : -2, -1, +1, +2 semitones (tempo preserved)
  tempo : -10%, -5%, +5%, +10% RELATIVE — target_bpm = min(round(bpm*(1+pct/100)),
          155), speed = target_bpm/bpm. BPM-capped at 155 exactly like
          augment_tracks.py (keeps tempo-up variants from running away on already-
          fast Goa/Psy material); a variant whose capped target duplicates the
          source BPM (or another variant's target) is skipped, not rendered twice.

Bungee: `set_pitch(2**(st/12))` changes pitch only; `set_speed(x>1)` speeds up
(raises tempo, shortens the source-side read window is what compensates for it —
see step 1). Output is peak-normalized into [-1, 1] before FLAC write (matches
augment_tracks.py's `_peak_norm`).

Resumable: a variant whose output FLAC already exists is skipped (re-emitted into
the manifest as `status: skipped-exists`, not re-rendered) — safe to re-run after a
partial/killed job. `--jobs N` (ProcessPoolExecutor over crops, one file load per
worker at a time — mirrors augment_tracks.py's memory-capping rationale). `--limit N`
processes only the first N crops (debug). `--dry-run` samples up to 200 crops,
prints the projected variant count, renders nothing.

SOURCE PATH REBASE — `--source-prefix-map OLD=NEW` (repeatable): every crop's recorded
`source_path` is rewritten by replacing a LEADING match of OLD with NEW before the file
is opened. Agreed LUMI convention (Kim, 2026-07-23): source audio is rsynced with
`--files-from` in a way that PRESERVES the absolute path structure under a scratch root,
e.g. `/run/media/kim/Mantu/ai-music/Goa_Separated/.../full_mix.flac` lands at
`$SCRATCH/goa_src/run/media/kim/Mantu/ai-music/Goa_Separated/.../full_mix.flac` — so the
LUMI invocation passes `--source-prefix-map /=/scratch/project_465003186/goa_src/`
(strips the leading `/` and re-roots everything under `goa_src/`). No mapping (default)
= use `source_path` verbatim, which is what local runs want.

CPU-ONLY. Bungee has no GPU path — do not request a GPU for this job; run it on a
CPU partition / node, or as CPU-only HyperQueue tasks alongside a GPU encode stage
(see ARTIFACT 2, lumi/sbatch/aug8_encode.sbatch).

*** LUMI PORT RISK — flagged 2026-07-23, UNVERIFIED, read before relying on this ***
`bungee_python` is a compiled extension (C++ core + Python bindings), not a pure-
Python pip package, and it is NOT part of the `sa3.sif` base container. This script
fails LOUD at startup (`_startup_check_bungee`, unless `--dry-run`) if it can't
`import bungee_python`, rather than limping along or silently no-op'ing. To fix a
failure:
  1. Confirm the failure is real: `singularity exec <sif> python3 -c "import
     bungee_python"` on LUMI.
  2. If missing, build a wheel matching the container's glibc/Python ABI — either
     locally (matching manylinux target) or inside `singularity exec --writable-tmpfs
     <sif> bash` — then `pip install --target <overlay-dir> bungee_python*.whl` and add
     `<overlay-dir>` to `PYTHONPATH` for the job (a venv OVERLAY bound in alongside the
     read-only SIF, same shape as the `lumi/vendor` FusionOpt shim already in use).
  3. Re-verify the import check before submitting the real (non-dry-run) job — a
     submit that fails this check burns a queue slot for nothing.
This is flagged, not solved; it's the #1 named risk in the aug8 campaign spec
(docs/superpowers/specs/2026-07-23-aug8-15ep-campaign.md) — it now also gates the
DDP training lane (aug8_train_ddp.sbatch), since both need real aug8 latents to train on.
"""
import sys
import os
import json
import math
import random
import hashlib
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import soundfile as sf

# ── variant table (v1 — edit here to change the augmentation set; matches
# mir/src/tools/augment_tracks.py exactly, per Kim's 2026-07-23 ruling) ────────
PITCH_SEMITONES = [-2, -1, 1, 2]
TEMPO_PCT = [-10, -5, 5, 10]
BPM_CAP = 155.0
BPM_KEYS = ["bpm_madmom", "bpm_essentia", "bpm", "tempo"]


def _startup_check_bungee():
    try:
        import bungee_python  # noqa: F401
    except ImportError as e:
        sys.exit(
            "[augment_goa_bungee] FATAL: bungee_python is not importable in this "
            "Python.\n"
            "  This is CPU-only Bungee time-stretch (compiled extension, not a pure-"
            "Python pip package).\n"
            "  On LUMI it is NOT in the base sa3.sif container — see the module "
            "docstring's LUMI PORT RISK section for the venv-overlay install recipe.\n"
            f"  Original ImportError: {e}"
        )


def pick_bpm(d: dict):
    for k in BPM_KEYS:
        v = d.get(k)
        try:
            if v is not None and 20.0 < float(v) < 400.0:
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def variants_for(bpm):
    """Return [(variant_name, semitones, speed)] for the 8 v1 variants (4 fewer —
    pitch-only — if bpm is unusable). Tempo targets are BPM-capped at 155 and deduped
    against the source BPM and each other by (semitones, target_bpm)."""
    out = [(f"pitch{s:+d}", s, 1.0) for s in PITCH_SEMITONES]
    if bpm is None:
        return out

    def cap(pct):
        return min(round(bpm * (1.0 + pct / 100.0)), int(BPM_CAP))

    seen = {(0, round(bpm))}  # the untransformed source itself
    for pct in TEMPO_PCT:
        target = cap(pct)
        sig = (0, target)
        if sig in seen:
            continue
        seen.add(sig)
        out.append((f"tempo{pct:+d}", 0, target / bpm))
    return out


def _stable_seed(crop_id):
    """Cross-run-stable integer seed from a crop id. Python's builtin hash() is salted
    per process (PYTHONHASHSEED) -> NOT stable across runs, which would make the sampled
    variant set change on a re-run and break resumability. SHA1 is stable everywhere."""
    return int.from_bytes(hashlib.sha1(crop_id.encode()).digest()[:8], "big")


def sample_variants(vs, crop_id, n, stratify):
    """Deterministically pick n of a crop's variants, seeded by crop_id so a RE-RUN picks
    the SAME set (resumability: skipped-exists checks stay consistent). When stratify and
    both families are present, guarantee >=1 pitch (semitones!=0) and >=1 tempo
    (speed!=1.0) so every crop teaches both invariances; the remaining slots are filled at
    random from the rest. n>=len(vs) (or n is None) returns the full set unchanged, so the
    full-cross-product path is exactly the pre-existing behaviour."""
    if n is None or n >= len(vs):
        return vs
    rng = random.Random(_stable_seed(crop_id))
    chosen = []
    if stratify:
        pitch = [v for v in vs if v[1] != 0]
        tempo = [v for v in vs if v[2] != 1.0]
        if pitch and tempo:                       # can't stratify a pitch-only crop (no bpm)
            chosen = [rng.choice(pitch), rng.choice(tempo)]
    remaining = [v for v in vs if v not in chosen]
    rng.shuffle(remaining)
    chosen = chosen + remaining[: max(0, n - len(chosen))]
    return chosen[:n]


def parse_prefix_map(pairs):
    """--source-prefix-map OLD=NEW [OLD=NEW ...] -> [(old, new), ...], longest OLD
    first so a more specific mapping wins over a shorter one that happens to also match."""
    out = []
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"[augment_goa_bungee] --source-prefix-map expects OLD=NEW, got: {p}")
        old, new = p.split("=", 1)
        out.append((old, new))
    return sorted(out, key=lambda kv: -len(kv[0]))


def resolve_source(source_path: str, prefix_map) -> str:
    """Rebase source_path by replacing a LEADING match of an OLD prefix with its NEW
    counterpart (first match wins, longest-OLD-first). No-op if prefix_map is empty or
    nothing matches (caller then hits a clean file-not-found, not a silently wrong path)."""
    for old, new in prefix_map:
        if source_path.startswith(old):
            return new + source_path[len(old):]
    return source_path


def _render(data, sr, semis, speed):
    from bungee_python import bungee as B
    ch = data.shape[1] if data.ndim > 1 else 1
    st = B.Bungee(sample_rate=sr, channels=ch)
    if semis:
        st.set_pitch(2.0 ** (semis / 12.0))
    if speed != 1.0:
        st.set_speed(speed)
    ai = data.astype(np.float32)
    if ai.ndim == 1:
        ai = ai.reshape(-1, 1)
    out = np.asarray(st.process(ai), dtype=np.float32)
    if ch == 1:
        out = out.reshape(-1)
    elif out.ndim == 1:
        out = np.column_stack([out] * ch)
    return out


def _peak_norm(x):
    p = float(np.max(np.abs(x))) if x.size else 0.0
    return (x * (0.999 / p)).astype(np.float32) if p > 0.999 else x.astype(np.float32)


def _fit_length(x, n):
    if len(x) >= n:
        return x[:n]
    pad = n - len(x)
    if x.ndim == 1:
        return np.pad(x, (0, pad))
    return np.pad(x, ((0, pad), (0, 0)))


def _manifest_row(crop_id, name, semis, speed, out_path, d, status):
    return {
        "crop_id": crop_id,
        "variant": name,
        "semitones": semis,
        "speed": round(speed, 6),
        "out_path": str(out_path),
        "source_path": d.get("source_path"),
        "source_bpm": pick_bpm(d),
        "prompt": d.get("prompt"),
        "status": status,
    }


def process_crop(json_path_str, out_dir_str, prefix_map, sample_n=None, stratify=True):
    """Worker: render this crop's variants (all of them, or a deterministic sampled
    subset of size sample_n) and return (json_name, n_rendered, top_level_status,
    manifest_rows)."""
    jp = Path(json_path_str)
    out_dir = Path(out_dir_str)
    try:
        d = json.load(open(jp))
    except Exception as e:
        return (jp.name, 0, f"json read: {e}", [])

    sp = d.get("source_path")
    s0 = d.get("start_sample")
    s1 = d.get("end_sample")
    st_total = d.get("source_total_samples")
    if not (sp and s0 is not None and s1 is not None):
        return (jp.name, 0, "missing source_path/start_sample/end_sample", [])

    src = resolve_source(sp, prefix_map)
    if not os.path.exists(src):
        return (jp.name, 0, f"source missing: {src}", [])

    crop_len = s1 - s0
    if crop_len <= 0:
        return (jp.name, 0, "bad crop_len (end_sample <= start_sample)", [])

    bpm = pick_bpm(d)
    crop_id = jp.stem
    vs = variants_for(bpm)
    if sample_n is not None:
        vs = sample_variants(vs, crop_id, sample_n, stratify)
    made = 0
    rows = []
    for name, semis, speed in vs:
        out_path = out_dir / f"{crop_id}__{name}.flac"
        if out_path.exists():
            rows.append(_manifest_row(crop_id, name, semis, speed, out_path, d, "skipped-exists"))
            continue
        try:
            src_len = int(math.ceil(crop_len * speed))
            center_shift = (src_len - crop_len) // 2
            ns0 = max(0, s0 - center_shift)
            if st_total:
                ns0 = min(ns0, max(0, int(st_total) - src_len))
            audio, sr = sf.read(src, start=ns0, stop=ns0 + src_len, dtype="float32")
            out = _render(audio, sr, semis, speed)
            out = _peak_norm(out)
            out = _fit_length(out, crop_len)
            out_dir.mkdir(parents=True, exist_ok=True)
            tmp = out_dir / f".{crop_id}__{name}.flac.tmp"
            sf.write(str(tmp), out, sr, format="FLAC")
            tmp.rename(out_path)
            made += 1
            rows.append(_manifest_row(crop_id, name, semis, speed, out_path, d, "ok"))
        except Exception as e:
            rows.append({"crop_id": crop_id, "variant": name, "status": f"error: {e}"})
    return (jp.name, made, "ok", rows)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("crop_dir", help="Dir of latents_sa3-style crop metadata JSONs (<id>.json)")
    ap.add_argument("--out", required=True, help="Output dir for augmented FLAC crops + manifest.jsonl")
    ap.add_argument(
        "--source-prefix-map", nargs="*", default=None, metavar="OLD=NEW",
        help="Rewrite a LEADING match of OLD to NEW in every crop's recorded source_path "
             "before opening it (repeatable). LUMI convention: "
             "--source-prefix-map /=/scratch/project_465003186/goa_src/ (source audio "
             "rsynced with --files-from preserves the absolute path structure under "
             "goa_src/). Default: use source_path as recorded (fine locally).",
    )
    ap.add_argument("--jobs", type=int, default=8, help="ProcessPoolExecutor worker count")
    ap.add_argument(
        "--sample-n", type=int, default=None, metavar="N",
        help="SAMPLED mode: render only N deterministically-chosen variants per crop "
             "(seeded by crop id -> resumable) instead of the full cross-product. For the "
             "large GOA corpus N=3 gives pitch/tempo invariance at ~3/8 the compute (Kim "
             "2026-07-29). Omit for the full 8-variant set (unchanged default).",
    )
    ap.add_argument(
        "--stratify", action=argparse.BooleanOptionalAction, default=True,
        help="With --sample-n, guarantee >=1 pitch AND >=1 tempo variant per crop so every "
             "crop teaches both invariances (default on; --no-stratify = pure random pick).",
    )
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N crops (debug)")
    ap.add_argument("--dry-run", action="store_true", help="Print projected variant counts, render nothing")
    args = ap.parse_args()

    if not args.dry_run:
        _startup_check_bungee()

    prefix_map = parse_prefix_map(args.source_prefix_map)
    crop_dir = Path(args.crop_dir)
    out_dir = Path(args.out)
    jsons = sorted(p for p in crop_dir.glob("*.json") if not p.name.endswith(".TIMBRAL.json"))
    if args.limit:
        jsons = jsons[: args.limit]
    print(f"[augment_goa_bungee] {len(jsons)} crops, {args.jobs} workers, out={out_dir}", flush=True)

    if args.dry_run:
        sample_n = min(len(jsons), 200)
        total_variants = 0
        no_bpm = 0
        for jp in jsons[:sample_n]:
            try:
                d = json.load(open(jp))
            except Exception:
                continue
            bpm = pick_bpm(d)
            if bpm is None:
                no_bpm += 1
            vfull = variants_for(bpm)
            vs = sample_variants(vfull, jp.stem, args.sample_n, args.stratify) \
                if args.sample_n is not None else vfull
            total_variants += len(vs)
        avg = total_variants / max(sample_n, 1)
        mode = f"sampled {args.sample_n}/crop (stratify={args.stratify})" \
            if args.sample_n is not None else "full cross-product"
        print(
            f"[dry-run] {mode}; sampled {sample_n}/{len(jsons)} crops: avg {avg:.1f} "
            f"variants/crop ({no_bpm} with no usable bpm -> pitch-only 4 variants). "
            f"Projected total renders ~= {avg * len(jsons):.0f} (of a {8 * len(jsons)} full max)."
        )
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.jsonl"
    all_rows = []
    total_made = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = {
            ex.submit(process_crop, str(jp), str(out_dir), prefix_map, args.sample_n, args.stratify): jp
            for jp in jsons
        }
        done = 0
        for f in as_completed(futs):
            name, made, status, rows = f.result()
            all_rows.extend(rows)
            total_made += made
            done += 1
            if status != "ok" or done % 100 == 0:
                print(
                    f"[augment_goa_bungee] {done}/{len(jsons)} rendered={total_made} "
                    f"last={name} ({status})", flush=True,
                )

    with open(manifest_path, "w") as mf:
        for row in all_rows:
            mf.write(json.dumps(row) + "\n")
    print(
        f"[augment_goa_bungee] DONE rendered={total_made} flacs across {len(jsons)} crops, "
        f"manifest -> {manifest_path} ({len(all_rows)} rows)", flush=True,
    )


if __name__ == "__main__":
    main()
