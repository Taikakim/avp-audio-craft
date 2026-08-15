"""Standalone diagnostic, run directly (no sbatch needed -- CPU-only, no GPU) on the LUMI
login node inside the multitorch venv. Five local repros on the desktop (bare _ffmpeg_load,
decode+pad_crop+clamp, full SampleDataset+DataLoader, the full GPU encode+save pipeline, and
40 genuinely distinct real files) were ALL clean -- bounded/noisy RSS, never the relentless
monotonic climb seen on LUMI jobs 21154320/21154650 (110GB->317GB, zero drops). This isolates
whether the bare decode primitive itself leaks specifically inside the LUMI multitorch
container/environment (different glibc/malloc, or the container's own ffmpeg build) --
the one variable none of the local repros could replicate.

Usage: point BIGSET at goa_archive (or any real audio dir) and run with the multitorch venv's
python, PYTHONPATH including stable-audio-3 -- same env every sbatch already sets up.
"""
import os
import sys
import glob

CODE = os.environ.get("SAO_CODE", "/project/project_465003186/code")
sys.path.insert(0, os.path.join(CODE, "stable-audio-3"))
from stable_audio_3.data.dataset import _ffmpeg_load  # noqa: E402

BIGSET = os.environ.get("BIGSET_DIR", "/scratch/project_465003186/goa_archive")
N = int(os.environ.get("N_FILES", "40"))


def rss_kb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])


files = glob.glob(os.path.join(BIGSET, "**", "*.mp3"), recursive=True)[: N * 5][::5][:N]
print(f"start VmRSS={rss_kb()} kB  ({len(files)} distinct files from {BIGSET})", flush=True)
for i, path in enumerate(files):
    try:
        audio, sr = _ffmpeg_load(path)
        nbytes = audio.numel() * audio.element_size()
        print(f"iter {i:2d}  decoded_bytes={nbytes:>12d}  VmRSS={rss_kb():>10d} kB  file={os.path.basename(path)}", flush=True)
        del audio
    except Exception as e:
        print(f"iter {i:2d}  FAILED: {e}", flush=True)
print(f"end   VmRSS={rss_kb()} kB", flush=True)
