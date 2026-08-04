#!/usr/bin/env python
"""breathing_a2a_run.py — tier-1 breathing-noise controller GPU validation (#35).

Wires W's recurrence meter (mir/src/tools/recurrence_meter.py) + the SA3 model + the
BreathingController into a real windowed a2a run over a source track, and emits the
"does it breathe" artifact: the nl trajectory plotted against the per-window novelty and
the source's self-calibrated floor. Compare to a FIXED-nl baseline of the same track.

Run (SA3 venv, GPU):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/breathing_a2a_run.py \
    --track "<source.flac>" --ckpt <adapter.ckpt> --prompt "..." \
    --requested-nl 0.7 --out-dir <Mantu>/sa3_lora_runs/breathing_<name>
The control law + loop are unit-tested (test_breathing_{controller,a2a}.py); this driver
is the integration + the GPU pass.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import argparse, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
sys.path.insert(0, "/home/kim/Projects/mir/src")
from sa3_control.audio_io import save_audio                       # noqa: E402
from stable_audio_3 import StableAudioModel                       # noqa: E402
from tools.recurrence_meter import novelty_curve, calibrate_source  # noqa: E402
from breathing_controller import (BreathingController, BreathingControllerV2,  # noqa: E402
                                  BreathingControllerV3)
from breathing_a2a import (breathing_loop, breathing_loop_v2, breathing_loop_v3,  # noqa: E402
                           make_a2a_renderer, plan_windows, make_novelty_measure,
                           source_break_flags, _source_features, derive_source_flags,
                           calibrate_hf_static)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--requested-nl", type=float, default=0.7)
    ap.add_argument("--window-sec", type=float, default=25.0)
    ap.add_argument("--overlap-sec", type=float, default=5.0)
    ap.add_argument("--nl-step", type=float, default=0.1)
    ap.add_argument("--nl-min", type=float, default=0.3)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--baseline", action="store_true",
                    help="also render a fixed-nl baseline (controller disabled) for A/B")
    ap.add_argument("--v2", action="store_true",
                    help="controller v2 (Kim 2026-07-10): wider band + source-break ducking")
    ap.add_argument("--break-floor", type=float, default=0.30)
    ap.add_argument("--reramp-start", type=float, default=0.41)
    ap.add_argument("--reramp-step", type=float, default=0.05)
    ap.add_argument("--break-pct", type=float, default=25.0)
    ap.add_argument("--v3", action="store_true",
                    help="controller v3 (Kim 2026-07-10): deep flush dips + fill/low-density/HF-static")
    ap.add_argument("--relax-ceiling", type=float, default=0.30)
    ap.add_argument("--flush-floor", type=float, default=0.05)
    ap.add_argument("--fast-reramp-step", type=float, default=0.15)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    audio, sr = sf.read(args.track, dtype="float32", always_2d=True)
    audio = audio.T
    measure = make_novelty_measure(sr, novelty_curve)

    # self-calibrate thresholds from the SOURCE's own novelty (once, up front)
    cal = calibrate_source(audio.mean(axis=0).astype(np.float32), sr=sr)
    print(f"[calibrate] {cal}", flush=True)

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    render = make_a2a_renderer(model, args.prompt, args.seed, args.steps, args.cfg_scale)

    if args.v3:
        feats = _source_features(audio, sr, args.window_sec, args.overlap_sec)
        flags = derive_source_flags(feats, break_pct=args.break_pct)
        hf_thr = calibrate_hf_static(audio, sr, args.window_sec, args.overlap_sec)
        print(f"[v3 flags] break={sum(flags['break'])} fill={sum(flags['fill'])} "
              f"low_density={sum(flags['low_density'])} hf_thr={hf_thr:.4f}", flush=True)
        ctl = BreathingControllerV3(ceiling=args.requested_nl, relax_ceiling=args.relax_ceiling,
                                    nl_min=args.nl_min, novelty_floor=cal["novelty_floor"],
                                    flush_floor=args.flush_floor, reramp_start=args.reramp_start,
                                    reramp_step=args.reramp_step, fast_reramp_step=args.fast_reramp_step,
                                    nl_step=args.nl_step)
        full, traj = breathing_loop_v3(audio, sr, args.window_sec, args.overlap_sec, render,
                                       measure, ctl, source_flags=flags, hf_static_thr=hf_thr)
    elif args.v2:
        breaks = source_break_flags(audio, sr, args.window_sec, args.overlap_sec, pct=args.break_pct)
        print(f"[source-breaks] {sum(breaks)}/{len(breaks)} windows flagged", flush=True)
        ctl = BreathingControllerV2(requested_nl=args.requested_nl,
                                    novelty_floor=cal["novelty_floor"],
                                    novelty_up=cal.get("novelty_median", cal["novelty_floor"]),
                                    nl_min=args.nl_min, nl_step=args.nl_step,
                                    break_floor=args.break_floor, reramp_start=args.reramp_start,
                                    reramp_step=args.reramp_step)
        full, traj = breathing_loop_v2(audio, sr, args.window_sec, args.overlap_sec,
                                       render, measure, ctl, source_breaks=breaks)
    else:
        ctl = BreathingController(requested_nl=args.requested_nl,
                                  novelty_floor=cal["novelty_floor"],
                                  novelty_up=cal.get("novelty_median", cal["novelty_floor"]),
                                  r_src_max=cal.get("r_max"),
                                  nl_step=args.nl_step, nl_min=args.nl_min)
        full, traj = breathing_loop(audio, sr, args.window_sec, args.overlap_sec,
                                    render=render, measure=measure, controller=ctl)
    save_audio(args.out_dir / "breathing.wav", __import__("torch").tensor(full), sr, normalize=True)

    meta = {"purpose": "breathing-noise controller validation (#35): windowed a2a with "
                       "per-window nl driven by output-novelty (+ source-break ducking in v2)",
            "version": "v3" if args.v3 else ("v2" if args.v2 else "v1"),
            "track": os.path.basename(args.track), "prompt": args.prompt, "seed": args.seed,
            "requested_nl": args.requested_nl, "window_sec": args.window_sec,
            "overlap_sec": args.overlap_sec, "nl_step": args.nl_step, "nl_min": args.nl_min,
            "calibration": cal, "checkpoint": args.ckpt,
            "windows": plan_windows(audio.shape[1] / sr, args.window_sec, args.overlap_sec),
            "trajectory": traj,
            "note": ("v2 (Kim 2026-07-10): wider band [nl_min..ceiling], duck HARD to break_floor "
                     f"({args.break_floor}) on source breaks then re-ramp ({args.reramp_start}) + climb; "
                     "novelty feedback breaks output loops elsewhere." if args.v2 else
                     "nl DROPs where output novelty < source floor, recovers above median.")}
    if args.v2:
        meta.update({"break_floor": args.break_floor, "reramp_start": args.reramp_start,
                     "reramp_step": args.reramp_step, "break_pct": args.break_pct})
    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, default=float))

    if args.baseline:
        flat = BreathingController(requested_nl=args.requested_nl,
                                   novelty_floor=-1.0, novelty_up=2.0, nl_step=0.0,
                                   nl_min=args.requested_nl)  # never triggers => fixed nl
        fb, _ = breathing_loop(audio, sr, args.window_sec, args.overlap_sec,
                               render=render, measure=measure, controller=flat)
        save_audio(args.out_dir / "baseline_fixed_nl.wav",
                   __import__("torch").tensor(fb), sr, normalize=True)
    print("[done] nl trajectory:", [round(x, 2) for x in traj["nl"]], flush=True)


if __name__ == "__main__":
    main()
