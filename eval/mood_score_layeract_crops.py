#!/usr/bin/env python
"""mood_score_layeract_crops.py — continuous Essentia mood scores for the 150 crops
behind the DiT layer-activation dumps (Kim 2026-07-11: steer by 'happy' etc).

Phase 1 of the diff-in-means concept-direction experiment (papers/arxiv-2505.18186.md):
score every crop in layer_activations_base/manifest.json with the fully-LOCAL
continuous heads — discogs-effnet embeddings -> mtg_jamendo_moodtheme (56 sigmoid
mood/theme activations: happy, sad, dark, energetic, calm, ...) + the VGGish
danceability graph — and carry over the crop-level MIR scalars already in the
latents_sa3 JSONs so Phase 2 builds directions for both families from one CSV.

(The dedicated binary mood_happy/sad/... + emomusic valence/arousal heads need the
audioset-vggish-3 embedding trunk, which is NOT on disk — skipped; moodtheme covers
the same qualifiers continuously.)

CPU-only ONNX (mir's wrappers hard-select MIGraphX=GPU, so we inline CPU twins) —
safe alongside GPU renders.
Run: /home/kim/Projects/mir/mir/bin/python eval/mood_score_layeract_crops.py
"""
import csv
import json
import time
from pathlib import Path

import numpy as np

DUMP_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/layer_activations_base")
LATENT_DIR = Path("/home/kim/Projects/latents_sa3")
MODELS = Path("/home/kim/Projects/mir/models/essentia")
OUT_CSV = DUMP_DIR / "crop_mood_scores.csv"

# crop-level scalars carried over from the latents_sa3 JSONs (known-feature sanity
# directions: if diff-in-means can't steer onset_density, it won't steer 'happy')
CARRY_SCALARS = ["onset_density", "onset_strength_mean", "spectral_flatness",
                 "spectral_flux", "spectral_skewness", "lufs", "syncopation",
                 "rhythmic_complexity", "bpm_madmom", "onset_per_beat",
                 "harmonic_movement_other", "onset_density_average_drums"]


class EffnetMoodCPU:
    """discogs-effnet embeddings -> mtg_jamendo_moodtheme, CPU EP (preprocessing
    mirrors mir/src/classification/effnet_onnx.py: musicnn mel, 128-frame patches,
    hop 62 ≈ 1Hz predictions)."""

    def __init__(self):
        import onnxruntime as ort
        import essentia.standard as es
        cpu = ["CPUExecutionProvider"]
        self.emb = ort.InferenceSession(str(MODELS / "discogs-effnet-bsdynamic-1.onnx"), providers=cpu)
        self.head = ort.InferenceSession(str(MODELS / "mtg_jamendo_moodtheme-discogs-effnet-1.onnx"), providers=cpu)
        self.classes = json.load(open(MODELS / "mtg_jamendo_moodtheme-discogs-effnet-1.json"))["classes"]
        self.mel_fn = es.TensorflowInputMusiCNN()
        self.frame_fn = es.FrameGenerator

    def __call__(self, audio):
        """16kHz mono float32 -> (56,) mean sigmoid activations."""
        mel = np.array([self.mel_fn(f) for f in
                        self.frame_fn(audio, frameSize=512, hopSize=256, startFromZero=True)])
        if len(mel) < 128:
            raise RuntimeError("audio too short for an effnet patch")
        patches = np.stack([mel[i:i + 128] for i in range(0, len(mel) - 127, 62)]).astype(np.float32)
        embs = np.concatenate([self.emb.run(["embeddings"], {"melspectrogram": patches[i:i + 16]})[0]
                               for i in range(0, len(patches), 16)])
        preds = np.concatenate([self.head.run(["model/Sigmoid:0"], {"model/Placeholder:0": embs[i:i + 64]})[0]
                                for i in range(0, len(embs), 64)])
        return preds.mean(axis=0)


class DanceabilityCPU:
    """danceability-vggish graph (full trunk: takes VGGish mel patches), CPU EP."""

    def __init__(self):
        import onnxruntime as ort
        import essentia.standard as es
        self.session = ort.InferenceSession(str(MODELS / "danceability-vggish-audioset-1.onnx"),
                                            providers=["CPUExecutionProvider"])
        self.vggish_in = es.TensorflowInputVGGish()
        self.frame_fn = es.FrameGenerator

    def __call__(self, audio):
        frames = np.array([self.vggish_in(f) for f in
                           self.frame_fn(audio, frameSize=400, hopSize=160, startFromZero=True)])
        if len(frames) < 96:
            raise RuntimeError("audio too short for a vggish patch")
        patches = np.stack([frames[i:i + 96] for i in range(0, len(frames) - 95, 96)]).astype(np.float32)
        preds = np.concatenate([self.session.run(["model/Sigmoid:0"], {"model/Placeholder:0": patches[i:i + 32]})[0]
                                for i in range(0, len(patches), 32)])
        return float(preds.mean(axis=0)[0])


def main():
    from essentia.standard import MonoLoader

    stems = [c["stem"] for c in json.load(open(DUMP_DIR / "manifest.json"))["crops"]]
    mood = EffnetMoodCPU()
    dance = DanceabilityCPU()
    score_cols = [f"mt_{c}" for c in mood.classes] + ["danceability"]
    print(f"[mood-score] {len(stems)} crops, 56 moodtheme classes + danceability", flush=True)

    rows, failed = [], []
    for i, stem in enumerate(stems):
        meta = json.load(open(LATENT_DIR / f"{stem}.json"))
        t0 = time.time()
        row = {"stem": stem, "source": meta.get("source_track", "")}
        for k in CARRY_SCALARS:
            row[k] = meta.get(k, "")
        try:
            audio = MonoLoader(filename=meta["path"], sampleRate=16000, resampleQuality=4)()
            sr_src = float(meta.get("sample_rate", 44100))
            lo = int(meta["start_sample"] / sr_src * 16000)
            hi = int(meta["end_sample"] / sr_src * 16000)
            audio = audio[lo:hi]
            if audio.shape[0] < 16000 * 10:
                raise RuntimeError(f"crop too short after slice: {audio.shape[0]/16000:.1f}s")
            m = mood(audio)
            for c, v in zip(mood.classes, m):
                row[f"mt_{c}"] = float(v)
            row["danceability"] = dance(audio)
        except Exception as e:
            failed.append(stem)
            print(f"[FAIL {stem}] {e}", flush=True)
            continue
        rows.append(row)
        top = sorted(mood.classes, key=lambda c: -row[f"mt_{c}"])[:4]
        print(f"[{i+1}/{len(stems)}] {stem} {time.time()-t0:.1f}s "
              f"dance={row['danceability']:.2f} top: "
              + " ".join(f"{c}={row[f'mt_{c}']:.2f}" for c in top), flush=True)

    cols = ["stem", "source"] + CARRY_SCALARS + score_cols
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (DUMP_DIR / "crop_mood_scores.meta.json").write_text(json.dumps(
        {"purpose": "continuous Essentia mood/theme scores for the layer-activation crops; "
                    "Phase 1 of diff-in-means concept-direction steering (arxiv-2505.18186 "
                    "triage, Kim ask 2026-07-11)",
         "heads": "discogs-effnet -> mtg_jamendo_moodtheme (56 sigmoid) + danceability-vggish",
         "n_scored": len(rows), "failed": failed,
         "score_stats": {c: {"mean": float(np.mean([r[c] for r in rows])),
                             "std": float(np.std([r[c] for r in rows])),
                             "min": float(np.min([r[c] for r in rows])),
                             "max": float(np.max([r[c] for r in rows]))}
                         for c in score_cols} if rows else {}}, indent=2))
    print(f"[done] {len(rows)} scored, {len(failed)} failed -> {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
