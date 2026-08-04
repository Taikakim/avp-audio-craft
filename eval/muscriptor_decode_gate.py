#!/usr/bin/env python
"""muscriptor_decode_gate.py -- the REQUIRED local gate for the MuScriptor LUMI batch
(spec: docs/superpowers/specs/2026-07-17-muscriptor-lumi-batch.md).

Question: does transcribing SAME-DECODED latents degrade the MIDI (and hence the
section labels) vs transcribing original audio?

Design: for N tracks present in BOTH the existing MuScriptor sample (original
full-track .mid) and latents_sa3: transcribe (a) the SAME-decode of the crop and
(b) the ORIGINAL AUDIO cut to the same crop window. Score both against the
original full-track MIDI windowed to the crop span. (b) is the self-consistency
CEILING (windowing + transcriber noise cancel); the gate metric is the GAP
(a) vs (b), not an absolute threshold.

Metrics per track: onset-F1 (±100 ms, exact pitch), notes/sec ratio,
pitch-class histogram correlation. GREEN if median F1 gap <= 0.10 and pc-corr
gap <= 0.05.

Run in the sa3 venv on a free card slot (~30 min at N=12):
  stable-audio-3/.venv/bin/python eval/muscriptor_decode_gate.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import glob
import json
from pathlib import Path

import numpy as np

SAMPLE = Path("/run/media/kim/Mantu/sa3_lora_runs/muscriptor_goa_midis")
LATENTS = Path("/home/kim/Projects/latents_sa3")
OUT = Path("/home/kim/Projects/SAO/eval/muscriptor_gate.json")
CROP_SEC = 4096 / 10.7666


def build_pairs(n):
    mids = {p.stem: p for p in SAMPLE.glob("*.mid")}
    pairs = []
    for j in sorted(LATENTS.glob("*.json")):
        meta = json.load(open(j))
        st = meta.get("source_track")
        if st in mids and Path(meta.get("source_path", "")).exists():
            pairs.append({"track": st, "mid": str(mids[st]), "npy": str(j.with_suffix(".npy")),
                          "src": meta["source_path"], "t0": float(meta.get("seconds_start", 0))})
            del mids[st]
        if len(pairs) >= n:
            break
    return pairs


def midi_notes(path, t0=0.0, t1=None):
    import mido
    mid = mido.MidiFile(path)
    notes, now = [], 0.0
    for msg in mid:  # merged track, seconds
        now += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            if now >= t0 and (t1 is None or now <= t1):
                notes.append((now - t0, msg.note))
    return notes


def onset_f1(ref, hyp, tol=0.1):
    if not ref or not hyp:
        return 0.0
    used = set()
    tp = 0
    for t, p in hyp:
        for i, (rt, rp) in enumerate(ref):
            if i not in used and rp == p and abs(rt - t) <= tol:
                used.add(i); tp += 1
                break
    prec, rec = tp / len(hyp), tp / len(ref)
    return 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0


def pc_hist(notes):
    h = np.zeros(12)
    for _, p in notes:
        h[p % 12] += 1
    return h / max(h.sum(), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--workdir", default="/tmp/muscriptor_gate")
    args = ap.parse_args()
    wd = Path(args.workdir); wd.mkdir(parents=True, exist_ok=True)

    pairs = build_pairs(args.n)
    print(f"[gate] {len(pairs)} track pairs", flush=True)
    assert len(pairs) >= 8, "too few overlapping tracks"

    import soundfile as sf
    import torch
    from stable_audio_3 import StableAudioModel
    from muscriptor import TranscriptionModel

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    pt = model.model.pretransform
    sr = model.model.sample_rate
    tm = TranscriptionModel.load_model("medium", device="cuda")

    rows = []
    for p in pairs:
        z = torch.from_numpy(np.load(p["npy"]).astype(np.float32)).unsqueeze(0).cuda()
        with torch.no_grad():
            y = pt.decode(z.to(next(pt.parameters()).dtype))[0].float().cpu().numpy()
        dec_wav = wd / "dec.wav"
        sf.write(dec_wav, y.T, sr)
        # original audio, same window
        info = sf.info(p["src"])
        s0 = int(p["t0"] * info.samplerate)
        orig, osr = sf.read(p["src"], start=s0, frames=int(CROP_SEC * info.samplerate),
                            dtype="float32", always_2d=True)
        orig_wav = wd / "orig.wav"
        sf.write(orig_wav, orig, osr)

        ref = midi_notes(p["mid"], p["t0"], p["t0"] + CROP_SEC)
        res = {}
        for tag, wav in (("decode", dec_wav), ("origcrop", orig_wav)):
            mid_out = wd / f"{tag}.mid"
            mid_out.write_bytes(tm.transcribe_to_midi(wav))
            hyp = midi_notes(str(mid_out))
            res[tag] = {"f1": round(onset_f1(ref, hyp), 3),
                        "nps_ratio": round(len(hyp) / max(len(ref), 1), 3),
                        "pc_corr": round(float(np.corrcoef(pc_hist(ref), pc_hist(hyp))[0, 1]), 3)}
        rows.append({"track": p["track"], **{f"{k}_{m}": v for k, r in res.items() for m, v in r.items()}})
        print(f"[gate] {p['track'][:40]:42s} F1 dec {res['decode']['f1']:.2f} vs orig {res['origcrop']['f1']:.2f}  "
              f"pc {res['decode']['pc_corr']:.2f}/{res['origcrop']['pc_corr']:.2f}", flush=True)

    med = lambda k: float(np.median([r[k] for r in rows]))
    gap_f1 = med("origcrop_f1") - med("decode_f1")
    gap_pc = med("origcrop_pc_corr") - med("decode_pc_corr")
    verdict = "GREEN" if (gap_f1 <= 0.10 and gap_pc <= 0.05) else "RED"
    summary = {"n": len(rows), "median_f1_decode": med("decode_f1"),
               "median_f1_origcrop_ceiling": med("origcrop_f1"), "f1_gap": round(gap_f1, 3),
               "median_pc_decode": med("decode_pc_corr"), "pc_gap": round(gap_pc, 3),
               "verdict": verdict}
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(f"[gate] VERDICT: {verdict}  f1_gap={gap_f1:.3f} pc_gap={gap_pc:.3f} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
