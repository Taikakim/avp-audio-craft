#!/usr/bin/env python
"""build_hf_repair_pairs.py — cache (degraded, target) pairs for HF-reconstruction-filter
training (part 1/3 of the SA3 HF-repair post-net pipeline).

WHY. The SAME codec round-trip discards HF temporal/phase detail: measured air-band
(8-16 kHz) envelope-correlation is 0.54 and 4-8 kHz is 0.58 (128 kbps MP3 = 0.97/0.99;
see eval/hf_clarity_diagnosis.py). We want a small decoder-side post-net that restores
that detail. The SAME encode->decode pass is the expensive part; this script runs it
ONCE over a corpus and caches the pairs so the post-net can be trained cheaply many
times (train_hf_repair.py) without touching the GPU codec again.

Per sampled track: take a random ~4 s @44.1k STEREO crop, run it through
cdm.pretransform.encode -> decode (the exact SAME load pattern of hf_clarity_diagnosis),
and cache:
    degraded = SAME-decoded audio   (post-net INPUT)
    target   = original crop        (post-net TARGET)
as a compact .npz ([2, samples] float32 each). Resumable (skips existing), writes a
manifest.json. --data-dial (hours target) controls the pair count.

Run (SA3 venv, GPU; holds SAO/.gpu.lock automatically unless --no-gpu-lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
    stable-audio-3/.venv/bin/python eval/build_hf_repair_pairs.py --data-dial 4.0

Decoupling rationale + measured baseline live in
docs/deep-research/2026-08-01-state-dependent-weights-triage.md (Snake / codec HF ceiling).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
REPO = Path(__file__).resolve().parents[1]
GPU_LOCK = REPO / ".gpu.lock"

# Default corpus: goa full-mixes + a spread of cross-genre ai-music dirs (Mantu).
# NOTE: /run/media/kim/Mantu/goa_archive is 7z archives (not directly readable), so the
# goa source here is the already-extracted Goa_Separated full_mix.flac set. Flag if you
# want the raw archive corpus instead (would need an extract step).
DEFAULT_CORPUS = [
    "/run/media/kim/Mantu/ai-music/Goa_Separated",
    "/run/media/kim/Mantu/ai-music/Rock",
    "/run/media/kim/Mantu/ai-music/Orchestral",
    "/run/media/kim/Mantu/ai-music/Piano",
    "/run/media/kim/Mantu/ai-music/Progressive Trance & Melodic Techno",
    "/run/media/kim/Mantu/ai-music/Post Rock",
    "/run/media/kim/Mantu/ai-music/Punk",
    "/run/media/kim/Mantu/ai-music/Peaceful",
]
DEFAULT_CACHE = "/run/media/kim/Mantu/sa3_lora_runs/hf_repair_pairs"
AUDIO_EXTS = {".flac", ".wav", ".ogg", ".mp3", ".m4a"}


def gather_files(corpus_dirs):
    """Collect source audio files. Goa_Separated -> per-track full_mix.flac only;
    any other dir -> recursive glob of audio files (skip separated-stem names)."""
    stem_names = {"bass.flac", "drums.flac", "other.flac", "vocals.flac"}
    files = []
    for root in corpus_dirs:
        root = Path(root)
        if not root.exists():
            print(f"[warn] corpus dir missing (drive unmounted?): {root}", file=sys.stderr)
            continue
        fulls = sorted(root.glob("*/full_mix.flac"))
        if fulls:
            files.extend(fulls)
            continue
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() in AUDIO_EXTS and p.name not in stem_names:
                files.append(p)
    return files


def load_stereo(path):
    """Load a file as [samples, 2] float32 @ SR (dup mono, resample if needed)."""
    a, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if a.shape[1] == 1:
        a = np.repeat(a, 2, axis=1)
    elif a.shape[1] > 2:
        a = a[:, :2]
    if sr != SR:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, SR)
        a = resample_poly(a, SR // g, sr // g, axis=0).astype(np.float32)
    return a


class gpu_lock:
    """Context manager wrapping Misc/filelock.py --pid-aware around the GPU section."""
    def __init__(self, handle, enabled=True):
        self.handle, self.enabled = handle, enabled

    def __enter__(self):
        if not self.enabled:
            return self
        r = subprocess.run(
            [sys.executable, str(REPO / "Misc" / "filelock.py"), "acquire", str(GPU_LOCK),
             "--handle", self.handle, "--pid-aware", "--pid", str(os.getpid())])
        if r.returncode != 0:
            print(f"[gpu-lock] blocked (rc={r.returncode}); another instance holds "
                  f"{GPU_LOCK}. Wait or pass --no-gpu-lock.", file=sys.stderr)
            sys.exit(1)
        return self

    def __exit__(self, *exc):
        if self.enabled:
            subprocess.run(
                [sys.executable, str(REPO / "Misc" / "filelock.py"), "release", str(GPU_LOCK),
                 "--handle", self.handle])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", nargs="+", default=DEFAULT_CORPUS,
                    help="corpus dirs (Goa_Separated -> full_mix.flac; else recursive glob)")
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE, help="output pair cache dir")
    ap.add_argument("--n", type=int, default=None,
                    help="number of pairs. If unset, derived from --data-dial.")
    ap.add_argument("--data-dial", type=float, default=4.0,
                    help="target hours of audio; n_pairs = ceil(hours*3600/clip_seconds). "
                         "Overridden by --n if given.")
    ap.add_argument("--clip-seconds", type=float, default=4.0, help="crop length (s)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--val-frac", type=float, default=0.1,
                    help="fraction flagged is_val in the manifest (held-out split)")
    ap.add_argument("--no-gpu-lock", action="store_true", help="skip the SAO/.gpu.lock mutex")
    ap.add_argument("--handle", default="hf-repair", help="filelock handle name")
    ap.add_argument("--limit-per-track", type=int, default=4,
                    help="max crops taken from one source track when n_pairs > n_tracks")
    args = ap.parse_args()

    clip_n = int(round(SR * args.clip_seconds))
    n_pairs = args.n if args.n is not None else int(np.ceil(args.data_dial * 3600 / args.clip_seconds))
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    files = gather_files(args.corpus)
    if not files:
        print("[fatal] no source files found (drives unmounted?).", file=sys.stderr)
        sys.exit(1)
    rng = np.random.default_rng(args.seed)

    # Build a sampling plan: (file, crop_index) pairs. Allow up to limit-per-track crops
    # per file when we need more pairs than tracks.
    order = rng.permutation(len(files))
    plan = []  # list of file indices; repeats allowed up to limit-per-track
    rounds = 0
    while len(plan) < n_pairs and rounds < args.limit_per_track:
        plan.extend(order.tolist())
        rounds += 1
    plan = plan[:n_pairs]
    print(f"[plan] {n_pairs} pairs from {len(files)} source files "
          f"(~{n_pairs * args.clip_seconds / 3600:.2f} h @ {args.clip_seconds}s); "
          f"cache={cache}", flush=True)

    # Defer the heavy SA3 import until we actually need the codec (keeps --help CPU-fast).
    import torch
    from stable_audio_3 import StableAudioModel

    manifest_path = cache / "manifest.json"
    manifest = json.loads(manifest_path.read_text())["pairs"] if manifest_path.exists() else []
    have = {m["id"] for m in manifest}

    with gpu_lock(args.handle, enabled=not args.no_gpu_lock):
        model = StableAudioModel.from_pretrained("medium-base", device="cuda")
        cdm = model.model
        device = next(cdm.model.parameters()).device
        mdtype = next(cdm.model.parameters()).dtype

        made = 0
        for i, fidx in enumerate(plan):
            pid = f"pair_{i:06d}"
            out = cache / f"{pid}.npz"
            if pid in have and out.exists():
                continue
            src = files[fidx]
            try:
                a = load_stereo(src)
            except Exception as e:  # noqa: BLE001
                print(f"[skip] {src.name}: {e}", file=sys.stderr)
                continue
            if a.shape[0] < clip_n:
                continue
            start = int(rng.integers(0, a.shape[0] - clip_n + 1))
            crop = a[start:start + clip_n].T.astype(np.float32)  # [2, clip_n]
            with torch.no_grad():
                z = cdm.pretransform.encode(torch.tensor(crop[None]).to(device, mdtype))
                rec = cdm.pretransform.decode(z)
            degraded = rec[0].float().cpu().numpy()[:, :clip_n].astype(np.float32)  # [2, clip_n]
            if degraded.shape[1] < clip_n:  # decoder length rounding guard
                pad = clip_n - degraded.shape[1]
                degraded = np.pad(degraded, ((0, 0), (0, pad)))
            np.savez_compressed(out, degraded=degraded, target=crop)
            is_val = rng.random() < args.val_frac
            manifest.append({"id": pid, "file": str(out.name), "source": str(src),
                             "start_sample": start, "sr": SR, "clip_samples": clip_n,
                             "is_val": bool(is_val)})
            have.add(pid)
            made += 1
            if made % 25 == 0:
                manifest_path.write_text(json.dumps(
                    {"sr": SR, "clip_seconds": args.clip_seconds, "clip_samples": clip_n,
                     "n_pairs": len(manifest), "pairs": manifest}, indent=1))
                print(f"[pair] {made} made ({i + 1}/{len(plan)}) last={src.name[:40]}", flush=True)

    manifest_path.write_text(json.dumps(
        {"sr": SR, "clip_seconds": args.clip_seconds, "clip_samples": clip_n,
         "n_pairs": len(manifest), "pairs": manifest}, indent=1))
    n_val = sum(m["is_val"] for m in manifest)
    print(f"[done] {len(manifest)} pairs cached ({n_val} val) -> {cache}", flush=True)


if __name__ == "__main__":
    main()
