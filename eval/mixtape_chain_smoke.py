#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-27)
"""mixtape_chain_smoke.py -- does the bass+body+air LatCH chain (the "graininess fix" from the punch work) clean up the
hot-latent mixtape shortlist clips?

WHY (owner ask 2026-10-27, after post-hoc z0 scaling was parked: x0.85 vs level-matched x0.85g sounded identical, scaling
below x0.85 degrades): the punch DoRA clips lost their coarseness and regained bass with the 'cleanest_air' preset
(rms_energy_bass -10.0 @ gain 8448, rms_energy_body -4.29 @ 11417.6, rms_energy_air -30.33 @ 8448, rho 5913.6, mu 5068.8,
gamma 0.25, n_iter 8; punch_rating_20261014/presets.json). This runs that chain on the shortlist clips the owner flagged as
most sensitive (z0 std 1.8346, 1.7409, 1.7562; all post-trained `medium` + DoRA, so server `--model medium`, 8 steps, cfg 1).
Per clip, same checkpoint/prompt/seed: ctl (no head, must reproduce the original), bb (bass+body only), chain (bass+body+air),
chain_anc (chain + latch_hparams guide_anchor 1.2, the loudness cap). CAVEAT: the bass/body/air target values were tuned on the
punch model at 30 steps / cfg 9, not on these clips at 8 steps; if the chain over- or under-steers, retune the values, do not
conclude the chain does not work. Judge by ear at matched loudness first (kim_feedback null); meters: hf_ratio, crest, raw peak, rms.
Output: Mantu/sa3_lora_runs/mixtape_chain_smoke_2026-10-27/<clip>__<arm>.wav + cells.jsonl + run_meta.json.
RUN (GPU lock held, render server up with --model medium): SAO/.venv/bin/python eval/mixtape_chain_smoke.py
"""
import json, os, shutil, sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P
from mixtape_anchor_smoke import ckpt_for, meters, RUNS, T1, T2

OUT = f"{RUNS}/mixtape_chain_smoke_2026-10-27"
# (label, ckpt epoch, prompt id, prompt text, seed, z0 std in the relcut set)
CLIPS = [("dora128_47s_newcaptions_5ep", 4, "rb_common_1", T1, 225176290, 1.8346),
         ("dora16_avp_originals_64ep", 31, "rb_common_1", T1, 225176290, 1.7409),
         ("dora16_goa_newstack_8ep", 7, "rb_common_2", T2, 544354203, 1.7562)]
ARMS = [("ctl", ()), ("bb", ("rms_energy_bass", "rms_energy_body")),
        ("chain", ("rms_energy_bass", "rms_energy_body", "rms_energy_air")),
        ("chain_anc", ("rms_energy_bass", "rms_energy_body", "rms_energy_air"))]


def main():
    os.makedirs(OUT, exist_ok=True)
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl)} if os.path.exists(jl) else set()
    if not P.render_up():
        print("render server :8056 is not up (start it with --model medium)"); return 2
    pre = P.load_presets()["cleanest_air"]
    slots = {s["head"]: s for s in pre["latch"]}
    for label, ep, pid, text, seed, z0 in CLIPS:
        ck = ckpt_for(label, ep)
        for arm, heads in ARMS:
            cid = f"{label}_ptm_ep{ep}__{pid}__{arm}"
            if cid in done:
                continue
            b = dict(prompt=text, negative_prompt="", steps=8, cfg_scale=1, seed=seed, apg_scale=1, duration=48, ckpt_path=None,
                     dora={"ckpt_path": ck, "strength": 1.0}, latch=[])
            if heads:
                b["latch"] = [dict(slots[h]) for h in heads]
                b.update(rho=pre["rho"], mu=pre["mu"], gamma=pre["gamma"], n_iter=pre["n_iter"])
                if arm.endswith("_anc"):
                    b["guide_anchor"] = 1.2
            r = P.post(b)
            w = f"{OUT}/{cid}.wav"
            shutil.copy(r["files"][0], w)
            x, sr = sf.read(w)
            m = x.mean(1) if x.ndim > 1 else x
            row = dict(id=cid, ckpt=ck, seed=seed, prompt_id=pid, arm=arm, heads=list(heads), z0_std_relcut=z0,
                       rms_db=round(float(20 * np.log10(np.sqrt((m ** 2).mean()) + 1e-12)), 2), **meters(x, sr), warnings=r.get("warnings"))
            open(jl, "a").write(json.dumps(row) + "\n")
            print(cid, row["hf_ratio"], row["crest"], row["rms_db"], flush=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": "Bass+body+air LatCH chain (punch 'cleanest_air' preset) on three hot-latent mixtape shortlist clips, ctl/bb/chain/chain_anc, to see whether it removes the grain that post-hoc z0 scaling could not -- owner ask 2026-10-27.",
                   "hypothesis": "Chain rounds the sound and restores bass as on the punch clips; guide_anchor keeps loudness at the unguided level. Kill: no audible gain over ctl at matched loudness.",
                   "script": "eval/mixtape_chain_smoke.py", "preset_source": "Mantu/sa3_control_runs/punch_rating_20261014/presets.json:cleanest_air",
                   "related": "EXPERIMENTS M1; eval/mixtape_anchor_smoke.py", "result": None, "kim_feedback": None},
                  open(f"{OUT}/run_meta.json", "w"), indent=1)
    print("CHAIN SMOKE DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
