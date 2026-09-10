#!/usr/bin/env python
"""length_hf_comparison.py — does render LENGTH itself (short ~20s vs native t2048/190s vs
native t4096/380s) correlate with reduced HF crispness / punch, independent of prompt content?

Kim's ear (2026-08-14): "t4096 clips have a bit less punch and a less crisp/precise high-end
than shorter t256 clips ... is there a theoretical reason, or coincidence?"

THEORY (already documented, stable-audio-3/CLAUDE.md + WORKLOG 2026-08-03): SA3's
use_effective_length_for_schedule reads True but is INERT -- the shipped LogSNRShift has
rate=0, zero-multiplying the only seq_len term, so the noise schedule is BYTE-IDENTICAL for
every context length. If the schedule was ever calibrated against a reference length, a
longer joint sequence changes the aggregate SNR characteristics without the schedule
compensating -- and HF/fine texture is the lowest-SNR, most schedule-fragile signal
component (well established: coarse/global structure survives denoising mismatch, fine
detail is the first casualty). That's a concrete, testable mechanism for exactly this
symptom -- not the only candidate (attention-capacity dilution over 16x more tokens at
T4096 vs T256 is a second, more hand-wavy one), but the best-grounded.

EMPIRICAL CAVEAT: no true per-prompt matched pairs exist locally (native_cells and
matrix_cells used DIFFERENT prompt snapshots for the same checkpoints -- verified 2026-08-14,
same seed/ep/cfg but different prompt_text). So this is same-checkpoint, same-cfg-range,
DIFFERENT-prompt aggregate comparison across length buckets -- informative if the effect is
large/consistent across independent model families (goa, avp) and monotonic across 3 length
points, not a controlled single-prompt A/B.

Metrics (absolute, no reference-original needed -- reusing eval/hf_clarity_diagnosis.py's
band-flatness/rolloff formulas for consistency with the prior HF-clarity finding):
  air_flatness / presence_flatness : spectral flatness in 8-16kHz / 4-8kHz (higher = more
                                      noise-like/detailed; lower = tonal/washed = "veiled")
  rolloff_hz                        : 85%-power spectral rolloff frequency (bass-dominated,
                                       weak HF discriminator per the prior finding -- read
                                       alongside flatness, not alone)
  air_crest                         : peak/RMS crest factor in the 8-16kHz band (higher =
                                       sharper transients in the air band)
  full_crest                        : broadband peak/RMS crest factor (a punch/dynamics proxy)
  air_energy_ratio                  : RMS(8-16kHz band) / RMS(full signal) (HF energy share)
  centroid_hz                       : spectral centroid (brightness)

Run (CPU-only, mir venv):
  mir/bin/python eval/length_hf_comparison.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, welch

SR = 44100
MATRIX = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/matrix_cells")
NATIVE = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/native_cells")
FAMILIES = ["fullft_goa_t4096", "fullft_avp_t4096", "fullft_goa_t2048", "fullft_avp_t2048"]
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/length_hf_comparison")


def load_mono(path):
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if sr != SR:
        raise ValueError(f"{path}: sr={sr} != {SR}")
    return y


def bandpass(y, lo, hi):
    hi = min(hi, SR / 2 - 100)
    return sosfiltfilt(butter(4, [lo, hi], btype="band", fs=SR, output="sos"), y)


def flatness(b):
    f, p = welch(b, fs=SR, nperseg=4096)
    m = p + 1e-12
    return float(np.exp(np.log(m).mean()) / m.mean())


def rolloff(y):
    f, p = welch(y, fs=SR, nperseg=8192)
    c = np.cumsum(p)
    return float(f[np.searchsorted(c, 0.85 * c[-1])])


def centroid(y):
    f, p = welch(y, fs=SR, nperseg=8192)
    return float((f * p).sum() / (p.sum() + 1e-12))


def crest(b):
    return float(np.abs(b).max() / (b.std() + 1e-9))


def clip_metrics(path):
    y = load_mono(path)
    air = bandpass(y, 8000, 16000)
    presence = bandpass(y, 4000, 8000)
    return {
        "air_flatness": round(flatness(air), 4),
        "presence_flatness": round(flatness(presence), 4),
        "rolloff_hz": round(rolloff(y), 0),
        "air_crest": round(crest(air), 3),
        "full_crest": round(crest(y), 3),
        "air_energy_ratio": round(float(air.std() / (y.std() + 1e-9)), 4),
        "centroid_hz": round(centroid(y), 0),
    }


def parse_meta(mmline_path):
    d = json.loads(mmline_path.read_text())
    return d.get("cfg"), d.get("prompt_id"), d.get("seed")


def gather(family):
    """Returns {bucket: [ (path, cfg, metrics), ... ]} for short / t2048 / t4096."""
    buckets = defaultdict(list)
    for wav in sorted(MATRIX.glob(f"{family}__*.wav")):
        if "__d" in wav.stem:
            continue  # skip any duration-suffixed sibling in matrix_cells
        mm = wav.with_suffix("").with_suffix(".mmline.json")
        if not mm.exists():
            continue
        cfg, pid, seed = parse_meta(mm)
        buckets["short"].append((wav, cfg, pid, seed))
    dur_tag = "d380" if "t4096" in family else "d190" if "t2048" in family else None
    for wav in sorted(NATIVE.glob(f"{family}__*__d*.wav")):
        m = re.search(r"__d(\d+)\.wav$", wav.name)
        if not m:
            continue
        d = int(m.group(1))
        bucket = "t4096" if d > 300 else "t2048" if d > 150 else None
        if bucket is None:
            continue
        mm = wav.with_suffix("").with_suffix(".mmline.json")
        if not mm.exists():
            continue
        cfg, pid, seed = parse_meta(mm)
        buckets[bucket].append((wav, cfg, pid, seed))
    return buckets


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for family in ["fullft_goa_t4096", "fullft_avp_t4096"]:
        buckets = gather(family)
        print(f"\n=== {family} ===")
        for bucket, items in buckets.items():
            print(f"  {bucket}: {len(items)} clips")
        for bucket, items in buckets.items():
            for wav, cfg, pid, seed in items:
                try:
                    m = clip_metrics(wav)
                except Exception as e:
                    print(f"  [skip] {wav.name}: {e}")
                    continue
                row = {"family": family, "bucket": bucket, "cfg": cfg,
                       "prompt_id": pid, "seed": seed, "file": wav.name, **m}
                all_rows.append(row)

    (OUT / "raw_rows.json").write_text(json.dumps(all_rows, indent=2))

    # Aggregate per (family, bucket) -- all cfgs, then cfg7-only.
    def summarize(rows, label):
        agg = defaultdict(lambda: defaultdict(list))
        for r in rows:
            key = (r["family"], r["bucket"])
            for k in ("air_flatness", "presence_flatness", "rolloff_hz", "air_crest",
                      "full_crest", "air_energy_ratio", "centroid_hz"):
                agg[key][k].append(r[k])
        print(f"\n=== SUMMARY ({label}) ===")
        order = {"short": 0, "t2048": 1, "t4096": 2}
        for key in sorted(agg, key=lambda k: (k[0], order.get(k[1], 9))):
            fam, bucket = key
            n = len(agg[key]["air_flatness"])
            means = {k: round(float(np.mean(v)), 4) for k, v in agg[key].items()}
            print(f"  {fam:22s} {bucket:6s} n={n:3d}  "
                  f"air_flat={means['air_flatness']:.4f}  "
                  f"pres_flat={means['presence_flatness']:.4f}  "
                  f"rolloff={means['rolloff_hz']:.0f}Hz  "
                  f"air_crest={means['air_crest']:.3f}  "
                  f"full_crest={means['full_crest']:.3f}  "
                  f"air_energy={means['air_energy_ratio']:.4f}  "
                  f"centroid={means['centroid_hz']:.0f}Hz")
        return {f"{k[0]}|{k[1]}": {kk: round(float(np.mean(vv)), 4) for kk, vv in agg[k].items()}
                for k in agg}

    summary_all = summarize(all_rows, "all cfgs")
    cfg7_rows = [r for r in all_rows if r["cfg"] == 7.0]
    summary_cfg7 = summarize(cfg7_rows, "cfg7 only")

    (OUT / "summary.json").write_text(json.dumps(
        {"all_cfgs": summary_all, "cfg7_only": summary_cfg7}, indent=2))
    print(f"\nWrote {OUT / 'raw_rows.json'} and {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
