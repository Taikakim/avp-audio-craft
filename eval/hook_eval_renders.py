#!/usr/bin/env python
"""hook_eval_renders.py — score hook_melodic_ratio (+ the full hook_metric set)
on our rendered clips (model_matrix wavs): muscriptor transcription -> skyline
lead -> per-clip motif metrics. Quantifies the missing-iconic-melodies failure:
hooky corpus decile repeats its best 4-note lead contour ~56x per 380 s clip
(hook_melodic_ratio med 0.076 corpus-wide, 0 in the bland decile).

Run (GPU for transcription; take .gpu.lock first — see MASTER):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python \
      eval/hook_eval_renders.py \
      --wavs '/run/media/kim/Mantu/sa3_lora_runs/model_matrix/*__cfg7__*.wav' \
      --out eval/hook_renders.jsonl

--wavs takes a glob OR a text file of paths (one per line). Resumable two ways:
clips already in --out are skipped entirely; clips with a saved .mid in
--midi-dir (default: <out>_midi/) skip the GPU transcription and are re-scored
on CPU — so metric tweaks never cost a second GPU pass.

Beat period: --bpm if given (seed for all clips), else refined from the
transcription's kick track (preferred), else librosa tempo on the wav.
Either way hook_metric refines +/-4% against kick onsets when kicks exist.

OUTPUT IS PLAIN JSONL ONLY — one {"clip", "file", ...metrics} object per line.
Deliberately does NOT touch clip_metrics.db or any page builder; W wires the
columns into the eval tables downstream (per task split 2026-07-22).

Venv: /home/kim/Projects/SAO/.venv (muscriptor + mido + librosa import there;
stable-audio-3/.venv lacks mido/pretty_midi; mir venv lacks muscriptor).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import glob
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "musicology"))
from hook_metric import hook_metrics, notes_from_midi_bytes  # noqa: E402


def librosa_beat_period(wav_path):
    """Fallback beat period from audio (folded into 90..200 bpm)."""
    import librosa
    import numpy as np
    y, sr = librosa.load(str(wav_path), sr=22050, mono=True)
    try:
        tempo = librosa.feature.rhythm.tempo(y=y, sr=sr)
    except AttributeError:
        tempo = librosa.beat.tempo(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    if bpm <= 0:
        return None
    while bpm < 90:
        bpm *= 2
    while bpm > 200:
        bpm /= 2
    return 60.0 / bpm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wavs", required=True,
                    help="glob pattern, or a text file listing wav paths")
    ap.add_argument("--out", required=True, help="output jsonl (appended, resumable)")
    ap.add_argument("--bpm", type=float, default=None,
                    help="seed BPM for all clips (else kick-derived, else librosa)")
    ap.add_argument("--model", default="medium", help="muscriptor model")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--midi-dir", default=None,
                    help="where transcriptions are cached (default <out>_midi/)")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if os.path.isfile(args.wavs) and not args.wavs.lower().endswith((".wav", ".flac")):
        wavs = [Path(l.strip()) for l in open(args.wavs) if l.strip()]
    else:
        wavs = [Path(p) for p in sorted(glob.glob(args.wavs))]
    if not wavs:
        sys.exit(f"no wavs matched {args.wavs!r}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    midi_dir = Path(args.midi_dir) if args.midi_dir else out.with_name(out.stem + "_midi")
    midi_dir.mkdir(parents=True, exist_ok=True)

    done = set()
    if out.exists():
        for line in open(out):
            try:
                done.add(json.loads(line)["clip"])
            except Exception:
                pass
    todo = [w for w in wavs if w.stem not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[hook_eval] {len(wavs)} wavs, {len(done)} already scored, {len(todo)} to do",
          flush=True)
    if not todo:
        return

    model = None  # lazy: pure re-score passes (cached .mid) never touch the GPU

    with open(out, "a") as f:
        for k, wav in enumerate(todo):
            t0 = time.time()
            mid = midi_dir / (wav.stem + ".mid")
            try:
                if mid.exists():
                    midi = mid.read_bytes()
                    src = "cached-midi"
                else:
                    if model is None:
                        from muscriptor import TranscriptionModel
                        model = TranscriptionModel.load_model(args.model, device=args.device)
                        print(f"[hook_eval] muscriptor {args.model} on {args.device}", flush=True)
                    midi = model.transcribe_to_midi(wav)
                    mid.write_bytes(midi)
                    src = "transcribed"
                notes = notes_from_midi_bytes(midi)
                beat_source = "kick"
                if args.bpm:
                    m = hook_metrics(notes, beat_period_s=60.0 / args.bpm)
                    beat_source = "cli_bpm"
                else:
                    m = hook_metrics(notes, beat_period_s=None)
                    if m.get("no_beat"):
                        bp = librosa_beat_period(wav)
                        if bp is None:
                            row = dict(clip=wav.stem, file=str(wav), error="no beat period",
                                       n_notes=len(notes))
                            f.write(json.dumps(row) + "\n"); f.flush()
                            print(f"[skip] {wav.stem}: no beat period", flush=True)
                            continue
                        m = hook_metrics(notes, beat_period_s=bp)
                        beat_source = "librosa"
                row = dict(clip=wav.stem, file=str(wav), n_notes=len(notes),
                           beat_source=beat_source, midi_source=src,
                           wall_s=round(time.time() - t0, 1))
                row.update(m)
                f.write(json.dumps(row) + "\n"); f.flush()
                print(f"[{k+1}/{len(todo)}] {wav.stem}: hmr={m.get('hook_melodic_ratio')} "
                      f"cnt={m.get('hook_melodic_count')} lead={m.get('n_lead')} "
                      f"({beat_source}, {src}, {row['wall_s']:.0f}s)", flush=True)
            except Exception as e:
                print(f"[FAIL] {wav.stem} {type(e).__name__}: {str(e)[:140]}", flush=True)
    print("[hook_eval done]", flush=True)


if __name__ == "__main__":
    main()
