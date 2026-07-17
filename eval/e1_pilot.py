#!/usr/bin/env python
"""e1_pilot.py -- E1 anti-loop guide pilot (validation plan 2026-07-15 §2-E1).

Guided arms of the a2a_kaikkialla_newstack ladder: SAME track/ckpt/prompt/seed/
steps/cfg, adding the builtin recurrence potential (band_hinge) at a lambda
ladder. Baselines = the existing unguided ladder renders on Mantu.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import json, sys, time
from pathlib import Path
import numpy as np, soundfile as sf, torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

TRACK = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-flac/009 goddess guerrilla (2006)/Aavepyora - Goddess Guerilla - Kaikki-Alla.flac"
CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora16_goa_newstack_8ep/epoch=3-step=5400.ckpt"
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/e1_pilot_20260716")
PROMPT, SEED, STEPS, CFG = "aggressive upbeat goa trance", 1234, 24, 6.0
import os as _os
EDGE = float(_os.environ.get("E1_EDGE", "0.738"))
WIDTH, GAMMA, WIN = 0.05, 0.15, (0.3, 0.8)
SUFFIX = _os.environ.get("E1_SUFFIX", "")
GRID = [tuple(map(float, g.split(":"))) for g in _os.environ.get(
    "E1_GRID", "0.50:1e2,0.50:1e3,0.50:1e4,0.60:1e2,0.60:1e3,0.60:1e4,0.60:1e5").split(",")]
MAX_SEC, OVERLAP = 378.0, 10.0


def a2a(model, audio, sr, nl, lam):
    a = torch.tensor(audio)
    dur = audio.shape[1] / sr
    ds = model.model.pretransform.downsampling_ratio
    budget = int(np.ceil((dur + 8.0) * sr / ds)) * ds
    cfgs = [{"builtin": "recurrence", "value": EDGE, "huber_beta": WIDTH,
             "start_pct": WIN[0], "end_pct": WIN[1], "weight": 1.0}]
    hp = {"rho": lam, "mu": lam, "gamma": GAMMA, "n_iter": 4, "log_norms": True}
    out = model.generate(prompt=PROMPT, duration=dur, steps=STEPS, cfg_scale=CFG,
                         seed=SEED, batch_size=1, sample_size=budget,
                         init_audio=(sr, a), init_noise_level=nl,
                         latch_configs=cfgs, latch_hparams=hp)
    y = out[0].float().cpu().numpy()
    if y.shape[1] < audio.shape[1] * 0.98:
        raise RuntimeError(f"a2a output {y.shape[1]/sr:.1f}s << {dur:.1f}s")
    return y


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audio, sr = sf.read(TRACK, dtype="float32", always_2d=True)
    audio = audio.T
    total = audio.shape[1] / sr
    wins = [(0.0, total)] if total <= MAX_SEC else [(0.0, MAX_SEC), (MAX_SEC - OVERLAP, total)]
    (OUT / "run_meta.json").write_text(json.dumps({
        "purpose": "E1 pilot: does the builtin recurrence band-hinge guide reduce loop-attractor "
                   "statistics (line_frac/l_max/det_soft) at matched quality on the known "
                   "loop-prone a2a ladder?",
        "hypothesis": "sparse repellency fires only above the corpus q90 edge; expect movement at "
                      "nl60 (labeled loopy) and none-needed at nl50; lambda ladder finds authority.",
        "baselines": "sa3_lora_runs/a2a_kaikkialla_newstack (identical track/ckpt/prompt/seed/steps/cfg, unguided)",
        "track": Path(TRACK).name, "checkpoint": CKPT, "prompt": PROMPT, "seed": SEED,
        "steps": STEPS, "cfg": CFG, "grid_nl_lambda": GRID,
        "guide": {"builtin": "recurrence", "edge_q90": EDGE, "hinge_width": WIDTH,
                  "gamma": GAMMA, "window_pct": WIN, "n_iter": 4,
                  "provenance": "eval/corpus_bands.json r_max q90; pre-test eval/e1_gradsnr_pretest.json"},
        "training_dataset": "dora16_goa_newstack_8ep (goa corpus, see its run dir)",
        "result": None, "kim_feedback": None}, indent=2))
    print(f"[load] {CKPT}", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([CKPT])
    for nl, lam in GRID:
        name = f"e1_nl{int(nl*100):02d}_lam{lam:.0e}{SUFFIX}.wav".replace("+0", "")
        op = OUT / name
        if op.exists():
            print(f"[skip] {name}", flush=True)
            continue
        t0 = time.time()
        pieces = [a2a(model, audio[:, int(lo*sr):int(hi*sr)], sr, nl, lam)[:, :int((hi-lo)*sr)]
                  for lo, hi in wins]
        if len(pieces) == 1:
            full = pieces[0]
        else:
            n = int(OVERLAP * sr)
            t = np.linspace(0, np.pi/2, n, dtype=np.float32)
            join = pieces[0][:, -n:]*np.cos(t) + pieces[1][:, :n]*np.sin(t)
            full = np.concatenate([pieces[0][:, :-n], join, pieces[1][:, n:]], axis=1)
        save_audio(op, torch.tensor(full), sr, normalize=True)
        print(f"[done] {name} {time.time()-t0:.0f}s", flush=True)
    print("[pilot complete]", flush=True)


if __name__ == "__main__":
    main()
