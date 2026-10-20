#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-20)
"""mixtape_anchor_smoke.py -- option 1 smoke test: re-render 5 distorted mixtape-audit clips with an air-head
LatCH slot + latch_hparams guide_anchor, to see whether guide_anchor (std ceiling, latch_guided._anchor_std) removes
the distortion without changing the music.

WHY (owner ask 2026-10-20): re-render the 249-clip kone-mixtape-audit set with the "gradient norm" tool = guide_anchor.
guide_anchor only acts inside the LatCH-guided sampler and the audit clips are plain DoRA renders, so a head must be
attached. Before the 249-clip run, test on the 5 clips with the highest hf_ratio among the 125 rated ones.
Per clip: ctl (same checkpoint/prompt/seed, no head -- must reproduce the original), then the preset
cleanest_air air slot (rms_energy_air, value -30.33, gain 8448 and a quarter of it, 2112) each with guide_anchor 0 / 1.2.
All five clips are post-trained `medium` + base-trained DoRA (_ptm), so the render server must run `--model medium`
(8 steps, cfg 1, pingpong). Output: Mantu/sa3_lora_runs/mixtape_anchor_smoke_2026-10-20/<clip>__<arm>.wav + cells.jsonl +
run_meta.json. Judge by ear first (kim_feedback null); meters: hf_ratio, crest, raw peak.
RUN (GPU lock held, server up with --model medium): SAO/.venv/bin/python eval/mixtape_anchor_smoke.py
"""
import glob, json, os, shutil, sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P

RUNS = "/run/media/kim/Mantu/sa3_lora_runs"
OUT = f"{RUNS}/mixtape_anchor_smoke_2026-10-20"
# (label, ckpt epoch, prompt id, prompt text, seed)
T1 = "mid 90s goa trance, melodic space mood, 140 bpm"
T2 = "mid 90s goa trance, 148 bpm"
CLIPS = [("dora128_newcap_continued_3more", 2, "rb_common_1", T1, 225176290),
         ("sa3-goa-dora-47s-r64", 7, "rb_common_1", T1, 225176290),
         ("dora128_47s_newcaptions_5ep", 4, "rb_common_1", T1, 225176290),
         ("dora128_everything_8ep_lr1x", 7, "rb_common_1", T1, 225176290),
         ("dora128_newcap_continued_3more", 2, "rb_common_2", T2, 544354203)]
ARMS = [("ctl", None, 0.0), ("air8448", 8448.0, 0.0), ("air8448_anc", 8448.0, 1.2),
        ("air2112", 2112.0, 0.0), ("air2112_anc", 2112.0, 1.2)]


def ckpt_for(label, ep):
    c = sorted(glob.glob(f"{RUNS}/{label}/**/epoch={ep}-step=*.ckpt", recursive=True))
    c = [x for x in c if not x.endswith(".weights.ckpt")] or sorted(glob.glob(f"{RUNS}/{label}/**/epoch={ep}-step=*.weights.ckpt", recursive=True))
    assert c, f"no ckpt for {label} ep{ep}"
    return c[0]


def meters(x, sr):
    m = x.mean(1) if x.ndim > 1 else x
    S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return dict(hf_ratio=round(float(S[f > 8000].sum() / S.sum()), 4), crest=round(float(np.abs(m).max() / (np.sqrt((m ** 2).mean()) + 1e-12)), 2),
                raw_peak=round(float(np.abs(x).max()), 4))


def main():
    os.makedirs(OUT, exist_ok=True)
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl)} if os.path.exists(jl) else set()
    if not P.render_up():
        print("render server :8056 is not up (start it with --model medium)"); return 2
    for label, ep, pid, text, seed in CLIPS:
        ck = ckpt_for(label, ep)
        for arm, gain, anc in ARMS:
            cid = f"{label}_ep{ep}__{pid}__{arm}"
            if cid in done:
                continue
            b = dict(prompt=text, negative_prompt="", steps=8, cfg_scale=1, seed=seed, apg_scale=1, duration=48, ckpt_path=None,
                     dora={"ckpt_path": ck, "strength": 1.0}, latch=[])
            if gain:
                b["latch"] = [dict(head="rms_energy_air", kind="constant", value=-30.33, gain=gain, start_pct=0.0, end_pct=1.0)]
                b.update(rho=5913.6, mu=5068.8, gamma=0.25, n_iter=8)
                if anc:
                    b["guide_anchor"] = anc
            r = P.post(b)
            w = f"{OUT}/{cid}.wav"
            shutil.copy(r["files"][0], w)
            x, sr = sf.read(w)
            row = dict(id=cid, ckpt=ck, seed=seed, prompt_id=pid, arm=arm, gain=gain, anchor=anc, **meters(x, sr), warnings=r.get("warnings"))
            open(jl, "a").write(json.dumps(row) + "\n")
            print(cid, row["hf_ratio"], row["crest"], row["raw_peak"], flush=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("WHY")[0].strip() + " -- see module docstring", "script": "eval/mixtape_anchor_smoke.py",
                   "source_audit": "/home/kim/staging/kone-mixtape-audit/index.html", "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    print("SMOKE DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
