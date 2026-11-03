#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-11-03)
"""e25b_caption_words.py -- EXPERIMENTS E25b: does a mood word the merged captions add actually change what the model renders?

The merged captions (eval/recover_mf2_lost_moods.py) add words such as dark, tense, industrial. Prompting is the cheap read, no training:
same prompt, same seed, with and without the word, on medium-base and the Goa LoRA. Every clip goes through plain generate() (no LatCH), so
both arms share one sampler path and the gain-0 baseline trap does not apply.

Words: those the merge raises most (goa_archive and goa_src), `euphoric` (which it cuts); PLACEBOS (blue, wooden, tuesday: any change of text moves a
render, so these are the noise floor); `ambient` is the known positive for the meter.
Grid: 14 canonical prompts x 2 models x (plain + 23 words) = 672 clips (504 in the first pass), 20 s, 24 Euler steps, cfg 7.
Read with eval/e25b_report.py. KILL for a word: its change is not more consistent across prompts than the placebos'.
RUN: eval/run_e25b.sh (GPU lock, CPU scoring).
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "stable-audio-3")); sys.path.insert(0, str(HERE.parent / "control"))
import mood_deconf_render as W  # noqa: E402  (models, canonical prompts, render settings)

OUT = Path("/home/kim/evals_aac/control_runs/e25b_caption_words_20261103")
TEST = ["dark", "tense", "aggressive", "industrial", "minimalist", "mechanical", "dystopian", "raw", "unsettling", "gritty", "introspective", "acidic", "euphoric"]
PLACEBO = ["blue", "wooden", "tuesday", "seven", "paper", "window"]
POSITIVE = ["ambient", "solo piano", "ambient, no drums", "heavy metal"]   # the last two passes added after `ambient` alone failed as a known positive
WORDS = TEST + PLACEBO + POSITIVE
slug = lambda w: w.replace(", ", "_").replace(" ", "_")
MODELS = ("base", "goa")


def prompts():
    return [p for p in W.prompts() if p["id"] != "prompt_dark"]


def cells(model):
    return [dict(id=f"{model}__{p['id']}__{slug(w) if w else 'plain'}", model=model, pid=p["id"], seed=p["seed"], word=slug(w) if w else "plain",
                 text=p["text"] if not w else f"{p['text']}, {w}") for p in prompts() for w in [None] + WORDS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / "run_meta.json").exists():
        json.dump({"run": OUT.name, "created": time.strftime("%Y-%m-%d %H:%M"), "owner": "CONTINUITY",
                   "purpose": "EXPERIMENTS E25b: do the mood words the merged captions add change the render? Project go 2026-11-03.",
                   "hypothesis": "Words with audio correlates (dark, aggressive) move the render consistently across prompts; some do not exceed the placebos.",
                   "kill": "A word whose change is no more consistent across prompts than the placebos' is not doing anything prompting can use.",
                   "recipe": {"steps": W.STEPS, "cfg": W.CFG, "duration": W.DURATION, "sampler": "generate() default, no LatCH", "words": WORDS, "models": MODELS},
                   "status": "running", "result": None, "kim_feedback": None, "script": "eval/e25b_caption_words.py"}, open(OUT / "run_meta.json", "w"), indent=1)
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    todo = [c for c in cells(a.model) if c["id"] not in done]
    print(f"[{a.model}] {len(todo)} to render", flush=True)
    if not todo:
        return
    import torch
    import torch.nn.utils.parametrize as P
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
    loras = W.models()[a.model]
    if loras:
        model.load_lora([p for p, _ in loras])
        for i, (_, s) in enumerate(loras):
            model.set_lora_strength(float(s), lora_index=i)
        for mod in list(model.model.model.modules()) + list(model.model.conditioner.modules()):
            if P.is_parametrized(mod):
                for name in list(mod.parametrizations.keys()):
                    with torch.no_grad():
                        P.remove_parametrizations(mod, name, leave_parametrized=True)

    def render(c):
        return model.generate(prompt=c["text"], duration=W.DURATION, steps=W.STEPS, cfg_scale=W.CFG, seed=c["seed"], batch_size=1).float().cpu()

    def bad(x):
        return (not bool(torch.isfinite(x).all())) or float(x.std()) < 1e-3

    x0, x1 = render(todo[0]), render(todo[0])      # throwaway first render: W's first-decode fault, kept as a measurement
    with (OUT / "checks.jsonl").open("a") as f:
        f.write(json.dumps(dict(model=a.model, first_bad=bad(x0), second_bad=bad(x1), rms=float((x0 - x1).pow(2).mean().sqrt()))) + "\n")
    n = 0
    for k, c in enumerate(todo):
        t0 = time.time()
        for attempt in range(3):
            x = render(c)
            if not bad(x):
                break
            print("FAULT", c["id"], attempt, flush=True)
        else:
            print("LEFT OUT", c["id"], flush=True)
            continue
        wav, aac = OUT / f"{c['id']}.wav", OUT / f"{c['id']}.m4a"
        save_audio(str(wav), x[0][:, : int(W.DURATION * W.SR)], W.SR, normalize=True)
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(aac)], check=True)
        with log.open("a") as f:
            f.write(json.dumps(dict(c, attempts=attempt + 1, audio_std=float(x.std()), secs=round(time.time() - t0, 1))) + "\n")
        n += 1
        if k % 25 == 0:
            print(f"  {k + 1}/{len(todo)} {c['id']} {time.time() - t0:.1f}s", flush=True)
        if a.limit and n >= a.limit:
            break


if __name__ == "__main__":
    main()
