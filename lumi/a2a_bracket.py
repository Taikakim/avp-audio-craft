#!/usr/bin/env python3
"""a2a_bracket.py — EXPERIMENTS D14: cross-prompt a2a bracket at high noise, across model families.

Kim 2026-08-22: "bracket a2a transformations with noising values at random between 0.5 and 0.9,
pick t4096 crops from our datasets and a2a them with a random prompt from another clip (does not
have to be the same set). use at least the melody subspace models and other things which might
help, also can try the morphs, the midi control..."

WHAT THIS REUSES INSTEAD OF REBUILDING (the a2a lane already cost the fleet one lost night):
  * `SDEditReanchor.reanchor(latents, sigma_peak, prompt, seed)` from
    stable_audio_3/inference/longform.py — LATENT-IN, LATENT-OUT prompt-conditioned SDEdit at an
    arbitrary sigma. Our corpora are stored AS latents, so the whole experiment runs in latent
    space: no audio load, no SAME encode, no decode/encode round trip corrupting the init.
    This is shipped, tested code; do not hand-roll a sampler call.
  * adapter loading / control context from lumi/render_morph.py + control/sa3_control.
  * lumi/render_showcase.load_fullft_state for full-FT backbones.

WHY THE PROMPT COMES FROM ANOTHER CLIP: it forces the model to choose between the init audio and
the caption, which is exactly where a control signal (subspace weighting, contour tokens, note
roll) should assert itself. F confirmed 2026-08-22 that no deliberate audio/caption mismatch test
exists anywhere in this codebase — D14 is the first.

⚠️ THE NOISE BAND IS NOT NEUTRAL GROUND. W (2026-07-30, Misc/latent_noise_fragility.py): the
mid-band a2a loss is the DiT ABANDONING HARMONY, not input fragility. [0.5, 0.9] straddles that
band, so BASELINE DEGRADATION IS THE EXPECTED RESULT, not a bug. The read is the DELTA between
families at matched sigma. --anchors adds a few cells BELOW the band for exactly this reason:
D1 (the survival-curve twin) has never actually been run, so there is no measured curve saying
where quality falls off, and without a low anchor "everything sounds degraded" is uninterpretable.

⚠️ SIGMA IS DRAWN PER (crop, family) AND REUSED ACROSS FAMILIES — see draw_plan(): the plan is
built from --plan-seed ALONE, so every family renders the SAME crops, the SAME donor prompts and
the SAME sigmas. Without this the family comparison is confounded by the draw.
"""
import argparse
import glob
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np

SR = 44100
FPS = 44100 / 4096


def load_sidecar(path):
    if not path or not os.path.exists(path):
        return {}
    return json.load(open(path))


def prompt_of(side, stem):
    """t3 if present, else t2/t1 — the sidecar tiers, same convention as render_morph."""
    d = side.get(stem) or {}
    if isinstance(d, str):
        return d
    for k in ("t3", "t2", "t1", "prompt", "caption"):
        v = d.get(k)
        if v:
            return v
    return None


def draw_plan(corpora, n_crops, frames, plan_seed, lo, hi, anchors, cross_frac,
               anchor_frac=0.15):
    """Build the (source, donor-prompt, sigma) plan ONCE from plan_seed so every family gets an
    identical grid. corpora = [(name, latent_dir, sidecar_dict)]."""
    rng = random.Random(plan_seed)
    pools = []
    for name, d, side in corpora:
        allst = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(d, "*.npy")))
        stems = [s for s in allst if prompt_of(side, s)]
        # FATAL, never silently drop: a stem/sidecar-key mismatch (e.g. latents_avp_ctrl stems are
        # "000000.ctrl" while the sidecar keys on "000000") yields an EMPTY pool, and a silently
        # dropped corpus turns a cross-corpus run into a within-corpus one with nothing in the log
        # to say so. Same failure shape as the shard-key mismatch and the caption-tier fallback.
        if not stems:
            raise SystemExit(
                f"[a2a] FATAL: corpus '{name}' contributed 0 usable crops — {len(allst)} .npy in "
                f"{d} but NONE of their stems are keys in its sidecar (sample stems "
                f"{allst[:3]}; sample sidecar keys {list(side)[:3]}). Fix the pairing; do not let "
                f"this run continue with fewer corpora than asked for.")
        pools.append({"name": name, "dir": d, "side": side, "stems": stems})
        print(f"[a2a] pool {name}: {len(stems)}/{len(allst)} crops have captions", flush=True)
    assert pools, "no corpus given"
    plan = []
    for i in range(n_crops):
        src = rng.choice(pools)
        stem = rng.choice(src["stems"])
        # donor: another CLIP, and per cross_frac another CORPUS
        cross = len(pools) > 1 and rng.random() < cross_frac
        dpool = rng.choice([p for p in pools if p["name"] != src["name"]]) if cross else src
        donor = rng.choice([s for s in dpool["stems"] if s != stem] or dpool["stems"])
        if anchors and rng.random() < anchor_frac:
            sigma = float(rng.choice(anchors))
            band = "anchor"
        else:
            sigma = round(rng.uniform(lo, hi), 3)
            band = "kim"
        plan.append({"idx": i, "src_corpus": src["name"], "src_dir": src["dir"], "src_stem": stem,
                     "donor_corpus": dpool["name"], "donor_stem": donor,
                     "prompt": prompt_of(dpool["side"], donor), "sigma": sigma, "band": band,
                     "cross_corpus": bool(cross), "seed": 20260822 + i})
    return plan


def crop_window(path, frames, rng):
    z = np.load(path, mmap_mode="r")
    T = z.shape[-1]
    if T <= frames:
        arr = np.asarray(z).astype(np.float32)
        pad = frames - arr.shape[-1]
        if pad > 0:
            arr = np.pad(arr, [(0, 0)] * (arr.ndim - 1) + [(0, pad)])
        return arr, 0
    i0 = rng.randrange(0, T - frames)
    return np.asarray(z[..., i0:i0 + frames]).astype(np.float32), i0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="family label, e.g. subloss_v3sel_k5")
    ap.add_argument("--ckpt", default="none", help="adapter/control ckpt, or 'none' for backbone-only")
    ap.add_argument("--base-state-ckpt", default=None, help="full-FT backbone state to load first")
    ap.add_argument("--corpus", action="append", required=True,
                    help="NAME:/path/to/latents:/path/to/sidecar.json (repeatable)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-crops", type=int, default=24)
    ap.add_argument("--frames", type=int, default=4096, help="T4096 = 380 s (Kim's spec)")
    ap.add_argument("--noise-lo", type=float, default=0.5)
    ap.add_argument("--noise-hi", type=float, default=0.9)
    ap.add_argument("--anchors", default="", help="extra sigmas BELOW the band, e.g. 0.3,0.4")
    ap.add_argument("--cross-corpus-frac", type=float, default=0.5,
                    help="fraction of cells whose donor prompt comes from a DIFFERENT corpus")
    ap.add_argument("--anchor-frac", type=float, default=0.15,
                    help="fraction of cells drawn from --anchors instead of Kim's band; keep it a "
                         "minority, the band is the experiment and the anchors are the yardstick")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--plan-seed", type=int, default=20260822,
                    help="SHARED across families — do not vary it per arm or the comparison breaks")
    ap.add_argument("--control-gain", type=float, default=1.0)
    ap.add_argument("--control-dir", default=None,
                    help="dir of <stem>.melody8.npy contour sidecars for the CONTROL arms. The "
                         "control fed to each cell is the SOURCE crop's OWN contour over the SAME "
                         "window -- i.e. 'keep this clip's melodic shape while a foreign caption "
                         "pulls the timbre elsewhere', which is the sharpest form of Kim's ask. A "
                         "control ckpt WITHOUT this dir is a FATAL error, not a silent no-op.")
    ap.add_argument("--refs", action="store_true", help="also decode the untouched source crop")
    a = ap.parse_args()

    import torch
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stable_audio_3 import StableAudioModel
    from stable_audio_3.inference.longform import SDEditReanchor
    from sa3_control.audio_io import save_audio
    from render_showcase import load_fullft_state
    from sa3_control.adapters import ControlContext, use_control_context

    corpora = []
    for spec in a.corpus:
        name, d, side = spec.split(":", 2)
        corpora.append((name, d, load_sidecar(side)))
        print(f"[a2a] corpus {name}: {len(glob.glob(os.path.join(d,'*.npy')))} latents", flush=True)

    anchors = [float(x) for x in a.anchors.split(",") if x.strip()]
    plan = draw_plan(corpora, a.n_crops, a.frames, a.plan_seed, a.noise_lo, a.noise_hi,
                     anchors, a.cross_corpus_frac, a.anchor_frac)
    out = Path(a.out)
    (out / "refs").mkdir(parents=True, exist_ok=True)

    def cell_name(p):
        return (f"a2a__{a.label}__{p['src_stem']}__sig{p['sigma']:.3f}"
                f"__from_{p['donor_corpus']}_{p['donor_stem']}__cfg{a.cfg:g}.wav")

    todo = [p for p in plan if not (out / cell_name(p)).exists()]
    if not todo:
        print(f"[a2a:{a.label}] all {len(plan)} cells present", flush=True)
        return
    print(f"[a2a:{a.label}] {len(todo)}/{len(plan)} cells to render "
          f"(sigma {a.noise_lo}-{a.noise_hi}, anchors {anchors or 'none'}, "
          f"cross-corpus {a.cross_corpus_frac})", flush=True)

    device = "cuda"
    sam = StableAudioModel.from_pretrained("medium-base", device=device)
    if a.base_state_ckpt:
        assert os.path.exists(a.base_state_ckpt), a.base_state_ckpt
        load_fullft_state(sam, a.base_state_ckpt)
        print(f"[a2a:{a.label}] backbone <- {os.path.basename(a.base_state_ckpt)}", flush=True)

    ctrl_ctx = None
    if a.ckpt and a.ckpt != "none":
        ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
        md = next(sam.model.model.parameters()).dtype
        if ck.get("control_mode"):          # Head-B control adapter (morph / contour)
            from sa3_control.conditioner import MelodyContourEncoder
            from sa3_control.generate import load_adapter_state
            from sa3_control.inject import install_adapters
            cargs = ck["args"]
            wrappers = install_adapters(sam, control_dim=int(cargs.get("control_dim", 768)))
            enc = MelodyContourEncoder(control_dim=int(cargs.get("control_dim", 768)),
                                       n_classes=int(cargs.get("melody_vocab", 9)))
            enc = enc.to(device=device, dtype=md)
            load_adapter_state(ck["state"], wrappers, enc)
            for w in wrappers:
                w.adapter.to(device=device, dtype=md)
            enc.eval()
            ctrl_ctx = enc
            if not a.control_dir:
                raise SystemExit(
                    f"[a2a] FATAL: {a.ckpt} is a control checkpoint (control_mode="
                    f"{ck.get('control_mode')}) but no --control-dir was given. Running it "
                    f"without a control stream would train-load the adapter and then condition on "
                    f"NOTHING -- it would look like a working arm and silently be an ablation.")
            print(f"[a2a:{a.label}] control adapter, vocab={cargs.get('melody_vocab')}", flush=True)
        else:                                # plain LoRA/DoRA adapter checkpoint
            # model.load_lora([path]) is the loader render_matrix_cells.py uses (arch is read
            # from the ckpt's own lora_config -- never hardcode rank/alpha here, MASTER §5).
            sam.load_lora([a.ckpt])
            print(f"[a2a:{a.label}] adapter <- {os.path.basename(a.ckpt)}", flush=True)

    reanchor = SDEditReanchor(sam, steps=a.steps, cfg_scale=a.cfg)
    decode_dtype = next(sam.model.pretransform.parameters()).dtype

    def decode_save(z, path):
        with torch.no_grad():
            audio = sam.model.pretransform.decode(z.type(decode_dtype))
        audio = audio.to(torch.float32).cpu()
        audio = (audio / audio.abs().amax().clamp(min=1.0))[0]
        save_audio(str(path), audio, SR)

    for p in todo:
        t0 = time.time()
        rng = random.Random(p["seed"])
        lat, i0 = crop_window(os.path.join(p["src_dir"], p["src_stem"] + ".npy"), a.frames, rng)
        if lat.ndim == 2:
            lat = lat[None]
        z_in = torch.from_numpy(lat).to(device)
        if a.refs:
            rp = out / "refs" / f"ref__{p['src_corpus']}_{p['src_stem']}__w{i0}.wav"
            if not rp.exists():
                decode_save(z_in, rp)
        with torch.inference_mode():
            if ctrl_ctx is None:
                z_out = reanchor.reanchor(z_in, p["sigma"], p["prompt"], p["seed"])
            else:
                # the SOURCE crop's own contour over the SAME window as the latent crop
                cp = os.path.join(a.control_dir, p["src_stem"] + ".melody8.npy")
                if not os.path.exists(cp):
                    print(f"[a2a:{a.label}] no contour for {p['src_stem']}; skipping cell",
                          flush=True)
                    continue
                stream = np.load(cp)[i0:i0 + a.frames].astype(np.int64)
                if len(stream) < a.frames:
                    stream = np.pad(stream, (0, a.frames - len(stream)))
                ctrl = ctrl_ctx(torch.from_numpy(stream)[None].to(device))
                if a.cfg != 1.0:
                    ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)
                with use_control_context(ControlContext(ctrl, gain=a.control_gain)):
                    z_out = reanchor.reanchor(z_in, p["sigma"], p["prompt"], p["seed"])
                np.save(out / (cell_name(p)[:-4] + ".stream.npy"), stream.astype(np.int8))
        name = cell_name(p)
        np.save(out / (name[:-4] + ".z0.npy"), z_out.cpu().to(torch.float16).numpy())
        decode_save(z_out, out / name)
        json.dump({**p, "label": a.label, "ckpt": a.ckpt, "base_state_ckpt": a.base_state_ckpt,
                   "window": [i0, i0 + a.frames], "frames": a.frames, "steps": a.steps,
                   "cfg": a.cfg, "duration_s": a.frames / FPS,
                   "read_note": "cross-prompt a2a: the caption describes a DIFFERENT clip. High "
                                "CLAP-to-own-prompt means the init was discarded, which is the "
                                "failure mode, not a win. Compare families at matched sigma."},
                  open(out / (name[:-4] + ".json"), "w"), indent=1)
        print(f"[a2a:{a.label}] {name} sig={p['sigma']:.3f} {'X' if p['cross_corpus'] else '='}"
              f" {time.time()-t0:.0f}s", flush=True)
    print(f"[a2a:{a.label}] done", flush=True)


if __name__ == "__main__":
    main()
