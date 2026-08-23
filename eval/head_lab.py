#!/usr/bin/env python3
"""head_lab.py — the CONTROL-HEAD EXPERIMENTATION DRIVER (Kim 2026-08-23: "it should allow
experimenting with values and combinations of control heads so I can kickstart a phase of
experimenting with what we have").

WHAT THIS IS. SA3 already supports guiding a render with SEVERAL LatCH heads at once —
`model.generate(latch_configs=[...])` -> `sample_flow_euler_multi_latch_guided`, one guide per
config, each with its own weight and t-window. What did NOT exist was any way to drive it except
hand-writing config dicts in Python. This is that driver: heads and their values on the command
line, one render per combination, every resolved parameter written to a JSON sidecar so a result
can be replayed or handed to a UI.

WHAT IT DOES NOT DO, stated up front so nobody assumes otherwise:
  * It drives LatCH guidance only. Head-B CONTROL ADAPTERS (control_mode=melody_contour etc.) use a
    different mechanism (control-context tokens through a module-global slot) and **only one can be
    active at a time** — they do not compose with each other, and combining them with LatCH
    guidance here is untested. See docs/INFERENCE-SURFACE.md §4.
  * t2a only. LatCH guidance is not carried by the a2a/longform samplers.

HEAD SPEC GRAMMAR  (--head, repeatable):
    <name>[:<kind>:<value>][,weight=W][,start=S][,end=E][,loss=L][,w_sec=X]
  name    a file stem in --heads-dir (see --list-heads), or 'recurrence' for the parameterless
          built-in anti-loop potential, or an explicit path to a .pt
  kind    constant | ramp_up | ramp_down | beat_grid      (beat_grid's value is BPM)
          omitted -> the head's own metadata default
  value   float, default 1.0
  weight  guidance strength, default 1.0
  start/end   the fraction of the sampling trajectory the head acts over, defaults 0.0/1.0.
          This is the knob most worth sweeping: a head that helps late often hurts early.
  loss    override the head's trained loss_type (rarely needed; the default comes from metadata)

EXAMPLES
    # what is available, and what defaults each head carries
    head_lab.py --list-heads
    # two heads at once
    head_lab.py --head same_chroma:constant:1.0,weight=1.5 --head beat_activation:beat_grid:142 \
                --prompt "psychedelic goa trance" --duration 20 --out runs/lab1
    # sweep ONE axis, everything else pinned — the comparison stays clean
    head_lab.py --head hpcp:constant:1,weight=1 --sweep head0.weight=0.5,1,2,4 --out runs/sweep

Outputs per render: <name>.wav + <name>.z0.npy + <name>.json (the FULL resolved config).
Run in the SAO venv. Needs a GPU to render; --list-heads and --dry-run are CPU-only.
"""
import argparse
import itertools
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")

REPO = Path(__file__).resolve().parent.parent
# self-add so the tool runs from anywhere without the caller setting PYTHONPATH (the same
# courtesy render_matrix_cells.py does for sa3_control)
for _p in (REPO / "stable-audio-3", REPO / "control", REPO / "lumi"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
DEFAULT_HEADS = REPO / "stable-audio-3" / "latch_weights_sa3_medium"
TARGET_KINDS = ("constant", "ramp_up", "ramp_down", "beat_grid")


def parse_head(spec, heads_dir):
    """'<name>[:<kind>:<value>][,k=v...]' -> a latch_configs dict (+ a label for filenames)."""
    head_part, *opts = spec.split(",")
    bits = head_part.split(":")
    name = bits[0]
    cfg = {}
    if name == "recurrence":
        cfg["builtin"] = "recurrence"
    else:
        p = Path(name)
        if not p.exists():
            p = Path(heads_dir) / f"latch_sa3_{name}_best.pt"
        if not p.exists():
            raise SystemExit(f"[head_lab] FATAL: no head '{name}' — tried {p}. "
                             f"Run --list-heads to see what exists.")
        cfg["model_path"] = str(p)
    if len(bits) > 1 and bits[1]:
        if bits[1] not in TARGET_KINDS:
            raise SystemExit(f"[head_lab] FATAL: kind '{bits[1]}' not in {TARGET_KINDS}")
        cfg["kind"] = bits[1]
    if len(bits) > 2 and bits[2]:
        cfg["value"] = float(bits[2])
    for o in opts:
        if not o.strip():
            continue
        k, _, v = o.partition("=")
        k = k.strip()
        key = {"start": "start_pct", "end": "end_pct", "loss": "loss_type"}.get(k, k)
        cfg[key] = v if key == "loss_type" else float(v)
    return name, cfg


def apply_sweep(base_cfgs, axis, value):
    """axis like 'head0.weight' or 'hparams.gamma' -> a COPY of the config list with it set."""
    cfgs = [dict(c) for c in base_cfgs]
    scope, _, field = axis.partition(".")
    if scope.startswith("head"):
        i = int(scope[4:] or 0)
        if i >= len(cfgs):
            raise SystemExit(f"[head_lab] FATAL: --sweep names {scope} but only "
                             f"{len(cfgs)} head(s) given")
        cfgs[i][{"start": "start_pct", "end": "end_pct"}.get(field, field)] = float(value)
    return cfgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", action="append", default=[], help="see the grammar in the docstring")
    ap.add_argument("--heads-dir", default=str(DEFAULT_HEADS))
    ap.add_argument("--list-heads", action="store_true",
                    help="print every head with the defaults ITS OWN metadata carries, then exit")
    ap.add_argument("--prompt", default="psychedelic goa trance, hypnotic acid lead, 143 BPM")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--frames", type=int, default=None,
                    help="NATIVE-length render: latent T (multiple of 256). WITHOUT this, "
                         "generate() silently uses a 120 s context — see INFERENCE-SURFACE §7")
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--base-state-ckpt", default=None, help="full-FT backbone to load first")
    ap.add_argument("--hparams", default="", help="rho=1,mu=1,gamma=0.3,n_iter=4")
    ap.add_argument("--sweep", default=None,
                    help="ONE axis, e.g. head0.weight=0.5,1,2 — everything else stays pinned so "
                         "the comparison is clean. Renders one clip per value.")
    ap.add_argument("--baseline", action="store_true",
                    help="also render with NO guidance — the control every combination needs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true", help="print the resolved configs, render nothing")
    a = ap.parse_args()

    if a.list_heads:
        import torch
        from stable_audio_3.models.latch import load_latch_from_checkpoint
        for p in sorted(Path(a.heads_dir).glob("*.pt")):
            try:
                h = load_latch_from_checkpoint(str(p), device="cpu")
                m = getattr(h, "metadata", {}) or {}
                print(f"{p.stem.replace('latch_sa3_','').replace('_best',''):26} "
                      f"out_ch={getattr(h,'out_channels','?'):<4} "
                      f"loss={m.get('loss_type','mse'):<14} "
                      f"kind={m.get('target_kind_default','constant'):<10} "
                      f"std={'y' if m.get('standardized') else 'n'}")
            except Exception as e:
                print(f"{p.stem:26} UNREADABLE: {e}")
        print("\nplus 'recurrence' — parameterless built-in (E1 anti-loop potential), no checkpoint")
        return

    if not a.head:
        raise SystemExit("[head_lab] FATAL: give at least one --head (or --list-heads)")

    labels, base_cfgs = zip(*[parse_head(h, a.heads_dir) for h in a.head])
    base_cfgs = list(base_cfgs)
    hp = {}
    for kv in a.hparams.split(","):
        if kv.strip():
            k, _, v = kv.partition("=")
            hp[k.strip()] = float(v)

    runs = []
    if a.sweep:
        axis, _, vals = a.sweep.partition("=")
        for v in vals.split(","):
            runs.append((f"{axis.replace('.','_')}{v}", apply_sweep(base_cfgs, axis, v)))
    else:
        runs.append(("+".join(labels), base_cfgs))
    if a.baseline:
        runs.insert(0, ("baseline_noguidance", []))

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"[head_lab] {len(runs)} render(s); heads={list(labels)}; hparams={hp or 'defaults'}")
    for name, cfgs in runs:
        print(f"  {name}: {json.dumps(cfgs, default=str)[:180]}")
    if a.dry_run:
        return

    import numpy as np
    import torch
    sys.path.insert(0, str(REPO / "lumi"))
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio

    sam = StableAudioModel.from_pretrained(a.model, device="cuda")
    if a.base_state_ckpt:
        from render_showcase import load_fullft_state
        load_fullft_state(sam, a.base_state_ckpt)

    for name, cfgs in runs:
        stem = out / f"{name}__cfg{a.cfg:g}__s{a.seed}"
        if stem.with_suffix(".wav").exists():
            print(f"[head_lab] {name}: exists, skipping")
            continue
        kw = {}
        if a.frames:
            kw["sample_size"] = a.frames * 4096
        with torch.inference_mode():
            z0 = sam.generate(prompt=a.prompt, duration=a.duration, steps=a.steps,
                              cfg_scale=a.cfg, seed=a.seed, return_latents=True,
                              latch_configs=(cfgs or None),
                              latch_hparams=(hp or None), **kw)
            audio = sam.model.pretransform.decode(
                z0.type(next(sam.model.pretransform.parameters()).dtype))
        audio = audio.to(torch.float32).cpu()
        save_audio(str(stem.with_suffix(".wav")),
                   (audio / audio.abs().amax().clamp(min=1.0))[0], 44100)
        np.save(str(stem) + ".z0.npy", z0.cpu().to(torch.float16).numpy())
        json.dump({"name": name, "latch_configs": cfgs, "latch_hparams": hp,
                   "prompt": a.prompt, "cfg": a.cfg, "steps": a.steps, "seed": a.seed,
                   "duration": a.duration, "frames": a.frames, "model": a.model,
                   "base_state_ckpt": a.base_state_ckpt},
                  open(str(stem) + ".json", "w"), indent=1, default=str)
        print(f"[head_lab] wrote {stem.name}.wav", flush=True)


if __name__ == "__main__":
    main()
