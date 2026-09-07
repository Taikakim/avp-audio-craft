#!/usr/bin/env python3
"""Render a PT<->base weight blend (eval/soup_pt_ladder.py output) — Kim 2026-09-05.

from_pretrained() only accepts registered model names, so a blend is rendered by loading
medium-base and OVERWRITING the DiT weights from the blend's safetensors — the same
whole-model-load pattern as render_showcase.load_fullft_state, minus the EMA branch
(a blend has no EMA shadow).

⚠ PT is a few-step ping-pong denoiser (--steps 8); base is a normal multi-step sampler. An
intermediate alpha belongs to NEITHER, so render each blend at BOTH step counts rather than
assuming one carries over.

  eval/render_soup.py --blend /run/media/kim/Mantu/soups/ptm_a050 --out ~/evals_aac/soup/a050
"""
import argparse, json, os, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blend", type=Path,
                    help="a soup_pt_ladder.py blend dir (mutually exclusive with --endpoint)")
    ap.add_argument("--endpoint", choices=["base", "pt"],
                    help="render an UNBLENDED endpoint straight from its registered name — "
                         "the alpha=0 / alpha=1 references the blends are judged against. "
                         "Loads the model as-is, no weight overwrite, so it cannot silently "
                         "differ from the endpoint the ladder actually interpolated between.")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--steps", type=int, nargs="+", default=[8, 24])
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--sampler", default="euler",
                    help="euler | pingpong | rk4 | dpmpp. Default euler for EVERY arm so ladder "
                         "differences are purely weights. But PT (medium) is diffusion_objective "
                         "'rf_denoiser', whose native sampler is pingpong, while base is "
                         "'rectified_flow'/euler — and a blend loads medium-base's CONFIG, so "
                         "every blend samples as rectified_flow regardless of alpha. Render PT "
                         "with --sampler pingpong too, or you are judging post-training by how "
                         "it sounds on the wrong sampler.")
    a = ap.parse_args()
    if bool(a.blend) == bool(a.endpoint):
        ap.error("give exactly one of --blend or --endpoint")

    os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
    import torch, numpy as np, soundfile as sf
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stable-audio-3"))
    from stable_audio_3 import StableAudioModel
    from safetensors.torch import load_file

    PROMPTS = [
        ("goa", "Goa trance, 145 BPM, rolling acid bassline, hypnotic lead melody, tight kick"),
        ("psy", "Psytrance, 143 BPM, driving percussion, morphing lead, deep sub bass"),
        ("break", "Breakbeat-driven psychedelic track, syncopated drums, evolving pads"),
    ]
    if a.endpoint:
        name = "medium-base" if a.endpoint == "base" else "medium"
        m = StableAudioModel.from_pretrained(name, device="cuda")
        tag, meta = f"endpoint_{a.endpoint}_{a.sampler}", {"endpoint": a.endpoint, "model": name,
                                               "alpha": 0.0 if a.endpoint == "base" else 1.0}
        print(f"  endpoint {a.endpoint} -> from_pretrained({name!r}), no weight overwrite")
        return render(a, m, tag, meta, sf, torch)

    m = StableAudioModel.from_pretrained("medium-base", device="cuda")
    sd = load_file(str(a.blend / "model.safetensors"))
    tgt = m.model.model
    want = set(dict(tgt.named_parameters())) | set(dict(tgt.named_buffers()))
    # blend keys carry the full "model.model.<...>" path; strip to the DiT's own namespace
    strip = {}
    for k, v in sd.items():
        for pfx in ("model.model.", "model.", ""):
            if k.startswith(pfx) and k[len(pfx):] in want:
                strip[k[len(pfx):]] = v
                break
    missing, _ = tgt.load_state_dict(
        {k: v.to(next(tgt.parameters()).dtype) for k, v in strip.items()}, strict=False)
    cov = 1 - len(missing) / max(1, len(list(tgt.state_dict())))
    print(f"  blend load coverage {cov:.2%} ({len(strip)} tensors, {len(missing)} missing)")
    assert cov > 0.99, f"blend covers only {cov:.1%} — refusing to render a half-loaded model"

    meta = json.loads((a.blend / "BLEND.json").read_text()) if (a.blend / "BLEND.json").exists() else {}
    # suffix non-default samplers: the euler pass already wrote {blend}__*, and render()
    # skips existing files, so an unsuffixed pingpong pass would silently write NOTHING.
    tag = a.blend.name + ("" if a.sampler == "euler" else f"_{a.sampler}")
    return render(a, m, tag, meta, sf, torch)


def render(a, m, tag, meta, sf, torch):
    import json
    from pathlib import Path
    PROMPTS = [
        ("goa", "Goa trance, 145 BPM, rolling acid bassline, hypnotic lead melody, tight kick"),
        ("psy", "Psytrance, 143 BPM, driving percussion, morphing lead, deep sub bass"),
        ("break", "Breakbeat-driven psychedelic track, syncopated drums, evolving pads"),
    ]
    a.out.mkdir(parents=True, exist_ok=True)
    for steps in a.steps:
        for name, prompt in PROMPTS:
            f = a.out / f"{tag}__{name}__st{steps}__cfg{a.cfg:g}.wav"
            if f.exists():
                continue
            with torch.no_grad():
                audio = m.generate(prompt=prompt, duration=a.seconds, steps=steps,
                                   cfg_scale=a.cfg, seed=a.seed, sampler_type=a.sampler)
            x = audio.squeeze(0).float().cpu().numpy().T if hasattr(audio, "cpu") else audio
            sf.write(str(f), x, 44100)
            json.dump({"blend": str(a.blend) if a.blend else None, "steps": steps, "cfg": a.cfg,
                       "prompt": prompt, "seed": a.seed, "sampler": a.sampler, **meta},
                      open(str(f)[:-4] + ".json", "w"), indent=1)
            print(f"  wrote {f.name}", flush=True)


if __name__ == "__main__":
    main()
