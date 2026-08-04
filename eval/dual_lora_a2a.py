#!/usr/bin/env python
"""dual_lora_a2a.py — dual-LoRA weight oscillation a2a (#35 Cluster B, Kim 2026-07-10).

Kim's v3 finding: higher nl doesn't give variety — the model collapses to ONE static
distributional average (the "goa wash"). Fix hypothesis: load TWO adapters and oscillate
their strengths per window so the model alternates between TWO averages → the output
stops sitting on one static mean. Held at a FIXED nl (the v3-static regime) so the only
variable is the adapter oscillation; compared to the single-adapter render at the same nl.

set_lora_strength(s, lora_index=i) is a live unmerged knob → per-window oscillation is cheap.
Run (SA3 venv, GPU): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/dual_lora_a2a.py ...
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import argparse, json, math, sys
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sa3_control.audio_io import save_audio                       # noqa: E402
from stable_audio_3 import StableAudioModel                       # noqa: E402
from breathing_a2a import plan_windows, _crossfade_join           # noqa: E402


def oscillation_schedule(n, period=2.0, base=0.65, amp=0.35, phase_deg=0.0):
    """Anti-phase strength pairs (sA, sB) per window. sA swings base±amp with `period`
    windows; sB is anti-phase, so each window has a DIFFERENT dominant adapter → the
    model's target average moves. Pure (testable)."""
    out = []
    for k in range(n):
        a = base + amp * math.cos(2 * math.pi * k / period + math.radians(phase_deg))
        b = base + amp * math.cos(2 * math.pi * k / period + math.radians(phase_deg) + math.pi)
        out.append((round(a, 4), round(b, 4)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--ckpt-a", required=True)
    ap.add_argument("--ckpt-b", default=None,
                    help="second adapter to oscillate; omit for SINGLE-adapter mode (isolates "
                         "the prompt-arc lever, no blend)")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--prompts-json", default=None,
                    help="JSON list of rich section prompts to crossfade through (Kim's arc idea); "
                         "windows are mapped evenly across the sections")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--nl", type=float, default=0.55)
    ap.add_argument("--window-sec", type=float, default=25.0)
    ap.add_argument("--overlap-sec", type=float, default=5.0)
    ap.add_argument("--period", type=float, default=2.0)
    ap.add_argument("--base", type=float, default=0.65)
    ap.add_argument("--amp", type=float, default=0.35)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    audio, sr = sf.read(args.track, dtype="float32", always_2d=True)
    audio = audio.T
    wins = plan_windows(audio.shape[1] / sr, args.window_sec, args.overlap_sec)
    sched = oscillation_schedule(len(wins), args.period, args.base, args.amp)
    prompts = json.load(open(args.prompts_json)) if args.prompts_json else [args.prompt]

    single = args.ckpt_b is None or args.ckpt_b == args.ckpt_a
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt_a] if single else [args.ckpt_a, args.ckpt_b])

    def a2a(chunk, sa, sb, prompt):
        import torch
        model.set_lora_strength(sa, lora_index=0)
        if not single:
            model.set_lora_strength(sb, lora_index=1)
        dur = chunk.shape[1] / sr
        ds = model.model.pretransform.downsampling_ratio
        budget = int(np.ceil((dur + 8.0) * sr / ds)) * ds
        out = model.generate(prompt=prompt, duration=dur, steps=args.steps,
                             cfg_scale=args.cfg_scale, seed=args.seed, batch_size=1,
                             sample_size=budget, init_audio=(sr, torch.tensor(chunk)),
                             init_noise_level=float(args.nl))
        return out[0].float().cpu().numpy()[:, :chunk.shape[1]]

    pieces, used = [], []
    for k, (lo, hi) in enumerate(wins):
        sa, sb = sched[k]
        section = min(len(prompts) - 1, int(k * len(prompts) / len(wins)))  # even section map
        prompt = prompts[section]
        y = a2a(audio[:, int(lo * sr):int(hi * sr)], sa, sb, prompt)
        pieces.append(y)
        used.append({"window": k, "section": section, "A": sa, "B": sb})
        print(f"[w{k:02d}] nl={args.nl} A={sa} B={sb} sec={section} :: {prompt[:48]}", flush=True)
    full = _crossfade_join(pieces, sr, args.overlap_sec)
    import torch
    save_audio(args.out_dir / "dual_lora.wav", torch.tensor(full), sr, normalize=True)
    meta = {"purpose": "dual-LoRA weight oscillation a2a (#35 Cluster B): two adapters, "
                       "anti-phase per-window strengths, fixed nl — does oscillating the "
                       "adapter disrupt the static distributional average?",
            "track": os.path.basename(args.track), "prompt": args.prompt, "seed": args.seed,
            "nl": args.nl, "ckpt_a": args.ckpt_a, "ckpt_b": args.ckpt_b,
            "period": args.period, "base": args.base, "amp": args.amp,
            "prompts": prompts, "schedule": sched, "per_window": used, "windows": wins,
            "note": "dual-LoRA oscillation + rich prompt-arc (Kim): fight the static average in "
                    "adapter-space AND conditioning-space. Compare HF-variance vs single-adapter/"
                    "single-prompt at the same nl — higher = less static."}
    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, default=float))
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
