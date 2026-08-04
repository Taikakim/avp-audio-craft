"""muscriptor_stem_probe.py — Gate #0 for the MIDI-frame-conditioner (Kim + CONTINUITY,
2026-07-20): does MuScriptor actually transcribe BS-RoFormer/Demucs STEMS reliably, or is
separator output "alien" to it? W's spec (2026-07-20-midi-frame-conditioner-design.md §4)
assumes stems give CLEANER notes than the full mix — but the task-#41 tryout found the
OPPOSITE on one track (bass stem 0 notes / +12dB rescue vs full-mix 572-note bassline). This
confirms/refutes that corpus-wide before any originals upload or training is committed.

Per sampled track, transcribe a matched 60 s window of full_mix / bass / other with MuScriptor
medium, and compare note yield + sustain (legato) recovery. If bass/other systematically yield
FEWER notes than full_mix, W's "transcribe stems" data decision needs rework (full-mix bassline
extraction may be the better source).

Run (SA3 venv, GPU free): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/muscriptor_stem_probe.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import json
import random
import statistics as st
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from muscriptor_batch_goa import note_stats  # reuse the exact stats

CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/muscriptor_stem_probe"); OUT.mkdir(parents=True, exist_ok=True)
SOURCES = ["full_mix", "bass", "other"]
N_TRACKS = 10
WIN_START, WIN_DUR = 120.0, 60.0     # same 60 s window per source (matches the #41 methodology)


def cut(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(WIN_START), "-t", str(WIN_DUR),
                    "-i", str(src), str(dst)], check=True)


def main():
    from muscriptor import TranscriptionModel
    model = TranscriptionModel.load_model("medium", device="cuda")
    print("[probe] medium loaded on cuda", flush=True)

    dirs = sorted(d for d in CORPUS.iterdir()
                  if all((d / f"{s}.flac").exists() for s in SOURCES))
    random.seed(42)
    sample = random.sample(dirs, min(N_TRACKS, len(dirs)))
    print(f"[probe] {len(sample)} tracks x {SOURCES}\n", flush=True)
    print(f"{'track':32s} | {'mix':>18s} | {'bass':>18s} | {'other':>18s}")
    print(f"{'':32s} | {'n  nps  sus':>18s} | {'n  nps  sus':>18s} | {'n  nps  sus':>18s}")

    rows = []
    for d in sample:
        r = {"track": d.name}
        for s in SOURCES:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tmp = tf.name
            try:
                cut(d / f"{s}.flac", tmp)
                t0 = time.time()
                midi = model.transcribe_to_midi(tmp)
                stt = note_stats(midi)
                r[s] = {"n": stt.get("n_notes", 0), "nps": stt.get("notes_per_sec", 0),
                        "sus": stt.get("frac_sustained_gt1s", 0), "wall": round(time.time() - t0, 1)}
            except Exception as e:
                r[s] = {"n": -1, "err": f"{type(e).__name__}: {str(e)[:80]}"}
            finally:
                os.unlink(tmp)
        def cell(x): return f"{x['n']:4d} {str(x.get('nps','-'))[:4]:>4s} {str(x.get('sus','-'))[:4]:>4s}"
        print(f"{d.name[:32]:32s} | {cell(r['full_mix']):>18s} | {cell(r['bass']):>18s} | {cell(r['other']):>18s}", flush=True)
        rows.append(r)

    # ── verdict ──────────────────────────────────────────────────────────────
    def med(s, key="n"): return st.median([r[s][key] for r in rows if r[s].get(key, -1) >= 0]) if rows else 0
    def zeros(s): return sum(1 for r in rows if r[s].get("n", -1) == 0)
    print("\n=== aggregate ===")
    for s in SOURCES:
        print(f"  {s:9s}: median notes {med(s):.0f}, median notes/s {med(s,'nps'):.2f}, "
              f"median sustained>1s {med(s,'sus'):.3f}, zero-note tracks {zeros(s)}/{len(rows)}")
    bass_worse = sum(1 for r in rows if 0 <= r["bass"]["n"] < r["full_mix"]["n"])
    other_worse = sum(1 for r in rows if 0 <= r["other"]["n"] < r["full_mix"]["n"])
    print(f"\n  bass  < full_mix on {bass_worse}/{len(rows)} tracks")
    print(f"  other < full_mix on {other_worse}/{len(rows)} tracks")
    verdict = ("STEMS ARE HARDER — confirms #41; W's 'transcribe stems' data decision needs rework "
               "(full-mix bassline extraction is the more reliable source)"
               if bass_worse >= 0.6 * len(rows) else
               "STEMS OK — the #41 single-track result did not generalize; the stem-transcription "
               "pipeline is viable, proceed to upload + Phase 0")
    print(f"\n[probe] VERDICT: {verdict}")
    OUT_json = {"purpose": "Gate #0: MuScriptor reliability on BS-RoFormer/Demucs stems vs full-mix",
                "window": [WIN_START, WIN_DUR], "n_tracks": len(rows), "rows": rows,
                "median_notes": {s: med(s) for s in SOURCES},
                "bass_worse_than_mix": f"{bass_worse}/{len(rows)}", "verdict": verdict}
    (OUT / "stem_probe_result.json").write_text(json.dumps(OUT_json, indent=1))
    print(f"[probe] -> {OUT}/stem_probe_result.json")


if __name__ == "__main__":
    main()
