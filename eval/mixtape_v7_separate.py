#!/usr/bin/env python
"""mixtape_v7_separate.py — BS-RoFormer 4-stem separation of the v7 mix clips (spec S1/S4 input).

WHY (GHOST-NOTE 2026-10-07, project guidance via CONTINUITY): the v7 stem-transition idea needs drums / bass /
other / vocals for every clip in the mix, plus the RESIDUAL  mix - sum(stems)  per clip (the separator output does
not sum back to the clip; the residual is added back later so a recomposed transition is continuous with the
untouched clip, spec S4). Also measures the S1 numbers: residual level re the mix and low-band bleed.

RUN (mir venv, GPU; take the lock first with Misc/gpu_guard.sh, hold it across the whole batch):
  ROCR_VISIBLE_DEVICES=0 /home/kim/Projects/mir/mir/bin/python eval/mixtape_v7_separate.py \\
      --order <mixtape_v7_phase0>/order_used.json --out-dir <Mantu>/sa3_lora_runs/mixtape_v7_stems
Output per clip: <out>/<NN>/{full_mix,drums,bass,other,vocals,residual}.wav and <out>/stems_report.json.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

MIR = Path("/home/kim/Projects/mir")
sys.path.insert(0, str(MIR / "src"))
sys.path.insert(0, str(MIR))
import torch  # noqa: E402
from preprocessing.bs_roformer_sep import load_audio, load_bs_roformer, separate_audio  # noqa: E402

STEMS = ("drums", "bass", "other", "vocals")
MODEL = "SYH99999-bs_roformer_4stems_ft"


def db(x):
    return 10 * np.log10(max(float(x), 1e-20))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    order = json.loads(Path(a.order).read_text())
    if a.limit:
        order = order[:a.limit]
    model_dir = str(MIR / "models" / "bs-roformer")
    sep, model_cfg, audio_cfg, inf_cfg = load_bs_roformer(MODEL, model_dir, device="cuda")
    names = list(model_cfg.instruments) if model_cfg.instruments else list(STEMS)
    assert set(names) >= set(STEMS), names
    report = []
    t_all = time.time()
    for k, o in enumerate(order):
        d = out / f"{k:02d}"
        d.mkdir(exist_ok=True)
        fm = d / "full_mix.wav"
        if not fm.exists():
            os.symlink(o["path"], fm)
        if not all((d / f"{s}.wav").exists() for s in STEMS):
            t = time.time()
            audio, sr0 = load_audio(fm, audio_cfg.sample_rate)          # (N, C)
            peak = float(np.abs(audio).max())
            gain = 0.9 / max(peak, 1e-8)                                # the separator wants a normalised input;
            y = separate_audio(sep, (audio * gain).astype(np.float32), audio_cfg, model_cfg, inf_cfg,
                               torch.device("cuda")) / gain             # undo it: stems stay at the clip's own scale
            for i, nm in enumerate(names[:y.shape[0]]):
                if nm in STEMS:
                    sf.write(str(d / f"{nm}.wav"), y[i], sr0, subtype="FLOAT")
            print(f"[sep] {k:02d} {o['id'][:40]} {time.time() - t:.1f}s", flush=True)
        mix, sr = sf.read(str(fm), dtype="float32")
        st = {s: sf.read(str(d / f"{s}.wav"), dtype="float32")[0] for s in STEMS}
        n = min([len(mix)] + [len(v) for v in st.values()])
        mix = mix[:n]
        ssum = sum(v[:n] for v in st.values())
        res = mix - ssum
        sf.write(str(d / "residual.wav"), res, sr, subtype="FLOAT")
        pm = float((mix ** 2).mean())
        # low-band (<150 Hz) energy share of each stem: bass-in-other and bass-in-drums bleed indicators
        from scipy.signal import butter, sosfiltfilt
        lp = butter(4, 150, "low", fs=sr, output="sos")
        low = {s: float((sosfiltfilt(lp, v[:n].mean(1)) ** 2).mean()) for s, v in st.items()}
        tot_low = sum(low.values()) + 1e-20
        report.append({"k": k, "id": o["id"], "n": int(n), "sr": sr,
                       "residual_db_re_mix": db((res ** 2).mean()) - db(pm),
                       "stem_db_re_mix": {s: db((v[:n] ** 2).mean()) - db(pm) for s, v in st.items()},
                       "lowband_share": {s: low[s] / tot_low for s in STEMS}})
        (out / "stems_report.json").write_text(json.dumps(report, indent=1))
    r = np.array([x["residual_db_re_mix"] for x in report])
    print(f"[done] {len(report)} clips in {time.time() - t_all:.0f}s; residual dB re mix: med {np.median(r):.1f} "
          f"worst {r.max():.1f} (spec S1 wants <= -20)", flush=True)


if __name__ == "__main__":
    main()
