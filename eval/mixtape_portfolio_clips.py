#!/usr/bin/env python
"""mixtape_portfolio_clips.py — Kim 2026-09-17: extracts a size-budgeted set of audio
for the "Custom Stable Audio 3 model portfolio" page. The full 76-transition, ~50min
mixtape cannot fit the Artifact page budget (64MB total / 15MB per file) at a
listenable bitrate, so this picks:
  1. N representative transition pairs, spread across the BPM arc, each trimmed to
     just the crossfade window (+/- pad) from both the _plain (pre-a2a) and _a2a
     (post-a2a) pair renders -- small enough for 256kbps.
  2. Two continuous highlight excerpts from the assembled full mixtape (a2a variant),
     one early/slow and one late/fast, at 192kbps to stay under the per-file cap.
Encodes via ffmpeg (already the project's mp3/m4a convention for review pages).
"""
import json
import subprocess
import sys
from pathlib import Path

RENDER_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v5_clean")
PAIRS_JSON = Path(
    "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/"
    "cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/mixtape_pairs.json")
OUT_DIR = Path(
    "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/"
    "cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/portfolio_clips")
N_SAMPLES = 10
PAD_SEC = 3.0


def ffmpeg_trim_encode(src, start, dur, dst, bitrate="256k"):
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
        "-i", str(src), "-c:a", "libmp3lame", "-b:a", bitrate, str(dst),
    ], check=True)


def main():
    pairs = json.loads(PAIRS_JSON.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    idxs = sorted(set(round(i * (len(pairs) - 1) / (N_SAMPLES - 1)) for i in range(N_SAMPLES)))
    manifest = []
    for i in idxs:
        p = pairs[i]
        meta_path = RENDER_DIR / f"{p['out_name']}_run_meta.json"
        meta = json.loads(meta_path.read_text())["measured"]
        start = max(0.0, meta["a_head_sec"] - PAD_SEC)
        dur = (meta["a_head_sec"] + meta["overlap_sec"] + PAD_SEC) - start
        entry = {"pair_idx": i, "out_name": p["out_name"],
                 "a_bpm": p["a_bpm"], "b_bpm": p["b_bpm"], "clip_start": start, "clip_dur": dur}
        for variant in ("plain", "a2a"):
            src = RENDER_DIR / f"{p['out_name']}_{variant}.wav"
            dst = OUT_DIR / f"t{i:02d}_{variant}.mp3"
            ffmpeg_trim_encode(src, start, dur, dst)
            entry[f"{variant}_file"] = dst.name
        manifest.append(entry)
        print(f"[done] transition {i}: {p['out_name']}", flush=True)

    # Two continuous highlight excerpts from the assembled full mix.
    full_a2a = RENDER_DIR / "mixtape_full_a2a.wav"
    highlights = []
    if full_a2a.exists():
        import soundfile as sf
        total_dur = sf.info(str(full_a2a)).duration
        spans = [("early", 0.15 * total_dur, 420.0), ("late", 0.75 * total_dur, 420.0)]
        for label, start, dur in spans:
            dst = OUT_DIR / f"highlight_{label}.mp3"
            ffmpeg_trim_encode(full_a2a, start, min(dur, total_dur - start), dst, bitrate="192k")
            highlights.append({"label": label, "file": dst.name, "start_sec": start})
            print(f"[done] highlight {label}", flush=True)
    else:
        print("[WARN] mixtape_full_a2a.wav not found yet -- run mixtape_assemble_continuous.py first",
              flush=True)

    (OUT_DIR / "portfolio_clips_manifest.json").write_text(
        json.dumps({"transitions": manifest, "highlights": highlights}, indent=2))
    print(f"[all done] {len(manifest)} transitions + {len(highlights)} highlights -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
