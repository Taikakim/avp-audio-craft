#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-16)
"""dronesweep_weights_test.py -- AVP drone-sweep full finetunes: EMA vs online weights, a base-model blend, and the unguided anchor.

WHY (listening 2026-10-16 on renders_pull/dronesweep): the plain arms are clean but "oddly disjointed, like the LR was too
large"; force_scalar runs its final latent std to ~3 at every cfg (healthy ~1.0-1.15); bf16_plain s2 sounds cleaner and more
musical than fp32. All LUMI clips are EMA renders, and the EMA (beta 0.9999) has a ~6900-step half-life over 4784-5980 steps,
so it still holds much of its starting weights and, per the project's suspicion, information from earlier (possibly blown)
epochs. Questions: does the ONLINE (current) set sound more coherent than the EMA; does blending the online set with base
medium-base (25% / 33%) tame it; does capping the latent's level during sampling (the trajectory anchor, here applied to the
UNGUIDED sampler through its step callback, final latent capped too) rescue force_scalar's runaway?

Arms: plain_s2 (fp32, ep7), bf16_plain_s2 (ep9), force_scalar_s1 (ep7). Variants: ema, online, online_b25 (0.75 online +
0.25 base), online_b33, online_anc (anchor s0 1.2), ema_anc. Prompts kl_0, kl_1, housestyle, kimlong with the LUMI clips'
own seeds; cfg 7, 24 steps, 20 s (as on LUMI). z_std recorded per clip.
Output: Mantu/sa3_control_runs/dronesweep_weights_20261016/. RUN (hold the GPU lock): SAO/.venv/bin/python eval/dronesweep_weights_test.py
"""
import glob
import json
import math
import os
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np  # noqa: E402

OUT = "/run/media/kim/Mantu/sa3_control_runs/dronesweep_weights_20261016"
PULL = "/home/kim/Projects/SAO/renders_pull/dronesweep"
ARMS = {
    "plain_s2": "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/avp_dronesweep/plain_s2/epoch=7-step=4784.ckpt",
    "bf16_plain_s2": "/run/media/kim/Mantu/lumi_runs/runs/runs/avp_dronesweep/bf16_plain_s2/epoch=9-step=5980.ckpt",
    "force_scalar_s1": "/run/media/kim/Mantu/lumi_runs/runs/runs/avp_dronesweep/force_scalar_s1/epoch=7-step=4784.ckpt",
}
VARIANTS = ("ema", "online", "online_b25", "online_b33", "online_anc", "ema_anc")
PROMPTS = ("kl_0", "kl_1", "housestyle", "kimlong")
CFG, STEPS, DUR, ANCHOR = 7.0, 24, 20.0, 1.2


def prompts():
    out = {}
    for pid in PROMPTS:
        f = sorted(glob.glob(f"{PULL}/dronesweep_plain_s2__*__cfg7__w100__{pid}__s*.mmline.json"))[0]
        j = json.load(open(f))
        out[pid] = (j["prompt_text"], int(j["seed"]))
    return out


def extract(sd_raw, which, tgt_keys):
    """The DiT weights of one set, keyed like the target module (same prefix logic as eval/model_matrix_gen.py)."""
    pfx = ("diffusion_ema.ema_model.",) if which == "ema" else ("diffusion.model.", "model.")
    return max(({(k[len(p):] if k.startswith(p) else k): v for k, v in sd_raw.items()} for p in pfx),
               key=lambda sd: sum(1 for k in sd if k in tgt_keys))


def main():
    import shutil
    import torch
    import librosa
    import soundfile as sf
    from stable_audio_3 import StableAudioModel
    os.makedirs(OUT, exist_ok=True)
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    P = prompts()
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("Output:")[0].strip(), "arms": ARMS, "variants": VARIANTS,
                   "prompts": {k: {"text": v[0], "seed": v[1]} for k, v in P.items()},
                   "eval": {"cfg": CFG, "steps": STEPS, "duration": DUR, "anchor_s0": ANCHOR, "model": "medium-base + fullft DiT"},
                   "anchor_note": "unguided anchor = callback scaling x in place each step to <= sqrt(((1-t)s0)^2+t^2) std, final latent capped at s0 before decode",
                   "related": ["lumi/sbatch/fullft_avp_dronesweep.sbatch", "lumi/sbatch/dronesweep_render.sbatch", f"{PULL}/run_meta.json"],
                   "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    tgt = model.model.model
    dtype = next(tgt.parameters()).dtype
    tgt_keys = set(tgt.state_dict())
    base = {k: v.detach().to("cpu", copy=True) for k, v in tgt.state_dict().items()}
    sr = model.model.sample_rate

    def cap(x, t, s0=ANCHOR):
        std = x.float().std(dim=tuple(range(1, x.dim())), keepdim=True).clamp_min(1e-8)
        tgt_std = math.sqrt(((1.0 - t) * s0) ** 2 + t ** 2)
        return (tgt_std / std).clamp(max=1.0).to(x.dtype)

    def anchor_cb(d):
        t = float(d["t"].flatten()[0])
        d["x"].mul_(cap(d["x"], t))

    for arm, ck in ARMS.items():
        todo = [(v, pid) for v in VARIANTS for pid in PROMPTS if f"{arm}__{v}__{pid}" not in done]
        if not todo:
            continue
        print(f"[{arm}] loading {ck}", flush=True)
        raw = torch.load(ck, map_location="cpu", mmap=True, weights_only=False)
        raw = raw.get("state_dict", raw)
        sets = {"online": extract(raw, "online", tgt_keys), "ema": extract(raw, "ema", tgt_keys)}
        for v, pid in todo:
            src = sets["ema" if v.startswith("ema") else "online"]
            a = 0.25 if v.endswith("_b25") else 0.33 if v.endswith("_b33") else 0.0
            w = {k: ((1 - a) * src[k].float() + a * base[k].float()).to(dtype) if a else src[k].to(dtype)
                 for k in tgt_keys if k in src}
            missing, _ = tgt.load_state_dict(w, strict=False)
            assert len(missing) < 0.01 * len(tgt_keys), f"{arm}/{v}: {len(missing)} missing keys"
            prompt, seed = P[pid]
            kw = dict(prompt=prompt, duration=DUR, steps=STEPS, cfg_scale=CFG, seed=seed, return_latents=True)
            if v.endswith("_anc"):
                kw["callback"] = anchor_cb
            t0 = time.time()
            z = model.generate(**kw)
            if v.endswith("_anc"):
                z = z * cap(z, 0.0)
            if not torch.isfinite(z).all():
                print(f"  NONFINITE {arm}/{v}/{pid}", flush=True)
                continue
            pt = model.model.pretransform
            with torch.no_grad():
                x = pt.decode(z.detach().type(next(pt.parameters()).dtype)).float()[0, :, :int(DUR * sr)].cpu().numpy()
            cid = f"{arm}__{v}__{pid}"
            pk = float(np.abs(x).max()) or 1e-9
            sf.write(f"{OUT}/{cid}.wav", (x / pk * 0.8913 if pk > 1 else x).T, sr)
            y = x.mean(0)
            row = {"id": cid, "arm": arm, "variant": v, "prompt": pid, "seed": seed,
                   "z_std": round(float(z.float().std()), 4), "raw_peak": round(pk, 3),
                   "onsets": round(len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr), 3),
                   "secs": round(time.time() - t0, 1)}
            with open(jl, "a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"  {cid}: z {row['z_std']} ({row['secs']}s)", flush=True)
        del raw, sets
    tgt.load_state_dict(base)
    print("DONE", flush=True)
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
