#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-10-28)
"""e21b_transposition_server.py -- EXPERIMENTS E21, second run: the transposition probe on the 14 canonical matrix prompts, with
the onset leg's best LatCH settings, rendered through the :8056 render server (a thin client, like W's E7/E18 drivers).

Kim 2026-10-28: "fix the bug, re-run e21, be sure to use our best settings from the onsets leg; create eval pages using the
standard prompts from our matrix." Bug fixed in eval/chroma_steer_render.py (bass root from the chord, not argmax).
Settings from the onset leg (EXPERIMENTS E7/E18, Kim's 10-15 verdict): the goa DoRA finetune at strength 1.0 (standing default for
LatCH evals), euler 50 steps, cfg 7, apg 1, 20 s, LatCH over the whole run (start 0, end 1) with the default alpha weighting,
gain 512 (the sweet spot) and 2048 (the upper usable end). Prompts and seeds: eval/model_matrix_gen.build_prompts (14 canonical).
Heads: hpcp (12-d) and same_chroma (384-d), cosine loss, static major triads on C / Eb / F# / A (k = 0/3/6/9 semitones).
Cells: 14 unguided + 14 x 2 heads x 4 keys x 2 gains = 238.
SCORE (CPU): output SAME chroma folded to 12 (bass, mid). Equivariance: best rotation between the k=0 and k outputs (same
prompt/head/gain) equals k (chance 1/12). Steering: cos to own target minus unguided, against the same for the other three
triads (specificity). Positive control: k=0 renders pitch-shifted with bungee (eval/e21_bungee_posctl.py --out OUT).
RUN: eval/run_e21b_20261028.sh (owns the GPU lock, starts and stops :8056, renders, positive control, score, page).
FOLLOW-UPS (2026-10-29): --out DIR, --head NAME=PATH@G1,G2 (repeatable; replaces the default two heads), --base-from DIR (reuse the
unguided renders of an earlier run with the same prompts/seeds/settings instead of re-rendering them), --purpose TEXT (run_meta).
Defaults reproduce the 10-28 run exactly. E21c driver: eval/run_e21c_20261029.sh.
"""
import argparse, json, os, shutil, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chroma_steer_render as CSR  # noqa: E402

OUT = "/run/media/kim/Mantu/sa3_control_runs/e21b_transposition_canon_20261028"
SERVER = "http://127.0.0.1:8056"
FT = ("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/"
      "epoch=63-step=12480.ckpt")
GAINS = (512, 2048)
HEADS = {"hpcp": ("latch_sa3_hpcp_best.pt", 12, GAINS), "same_chroma": ("latch_sa3_same_chroma_best.pt", 384, GAINS)}
KEYS = {0: "C", 3: "Eb", 6: "F#", 9: "A"}
BASE_FROM = None
PURPOSE = None


def parse_head(spec):
    """NAME=PATH@G1,G2 -> (NAME, (PATH, dim, gains)); dim 12 for hpcp heads, else the 384-d SAME chroma."""
    name, rest = spec.split("=", 1)
    path, gains = rest.rsplit("@", 1)
    return name, (path, 12 if "hpcp" in name else 384, tuple(int(g) for g in gains.split(",")))
DUR, STEPS, CFG = 20.0, 50, 7.0


def prompts():
    import model_matrix_gen as M
    return M.build_prompts(n_per_band=3, n_kimlong=3)


def cid(pid, head=None, k=None, g=None):
    return f"{pid}__base" if head is None else f"{pid}__{head}__k{k}__g{g}"


def cells():
    out = []
    for p in prompts():
        out.append(dict(id=cid(p["id"]), pid=p["id"], seed=int(p["seed"]), head=None))
        for h, (_, _, gains) in HEADS.items():
            for k in KEYS:
                for g in gains:
                    out.append(dict(id=cid(p["id"], h, k, g), pid=p["id"], seed=int(p["seed"]), head=h, k=k, gain=g))
    return out


def payload(c, text, n_frames):
    p = {"prompt": text, "duration": DUR, "steps": STEPS, "cfg_scale": CFG, "seed": c["seed"], "sampler_type": "euler",
         "apg_scale": 1.0, "dora": {"ckpt_path": FT, "strength": 1.0}}
    if c["head"]:
        fn, dim, _ = HEADS[c["head"]]
        raw = CSR.build_target_raw(dim, {"id": KEYS[c["k"]], "kind": "static", "chord": KEYS[c["k"]]}, n_frames)
        p["latch"] = [{"path": fn if os.path.isabs(fn) else str(CSR.HEADS_DIR / fn), "gain": float(c["gain"]), "start_pct": 0.0, "end_pct": 1.0,
                       "loss_type": "cosine", "target_raw": raw.astype(float).round(5).tolist()}]
    return p


def render(dry=False):
    import requests
    os.makedirs(OUT, exist_ok=True)
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    text = {p["id"]: p["text"] for p in prompts()}
    todo = [c for c in cells() if c["id"] not in done]
    n_frames = int(round(DUR * CSR.FPS))
    print(f"[e21b] {len(todo)} cells to render ({len(done)} done)", flush=True)
    if dry:
        for c in todo[:3]:
            print(c["id"], json.dumps(payload(c, text[c["pid"]], n_frames))[:300])
        return
    if BASE_FROM:
        for c in list(todo):
            src = f"{BASE_FROM}/{c['id']}.wav"
            if c["head"] is None and os.path.exists(src):
                shutil.copyfile(src, f"{OUT}/{c['id']}.wav")
                c.update(secs=0.0, warnings=[], copied_from=BASE_FROM)
                with open(jl, "a") as f:
                    f.write(json.dumps(c) + "\n")
                todo.remove(c)
        print(f"[e21b] unguided renders reused from {BASE_FROM}; {len(todo)} left to render", flush=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"run": os.path.basename(OUT), "created": time.strftime("%Y-%m-%d %H:%M"), "owner": "CONTINUITY",
                   "purpose": PURPOSE or ("EXPERIMENTS E21 second run (Kim 2026-10-28): transposition equivariance of the hpcp "
                              "and same_chroma LatCH heads on the 14 canonical matrix prompts, with the onset leg's best "
                              "settings, after fixing the same_chroma bass-root bug."),
                   "hypothesis": "If a head steers pitch class, the output chroma for a target moved by k semitones is the k=0 output "
                                 "rotated by k, and moves more toward its own triad than toward the others.",
                   "kill": "Hits near the bungee positive control and positive specificity => equivariant, no regulariser; close E21.",
                   "recipe": {"finetune": "goa DoRA finetune (subloss_k24 biggoa t512, epoch 63), strength 1.0", "sampler": "euler",
                              "steps": STEPS, "cfg": CFG, "apg": 1.0, "duration": DUR, "latch_window": [0.0, 1.0],
                              "guide_schedule": "alpha (default)", "loss": "cosine", "keys": KEYS,
                              "heads": {h: {"path": v[0], "gains": list(v[2])} for h, v in HEADS.items()},
                              "unguided_from": BASE_FROM, "prompts": "model_matrix_gen.build_prompts(3,3)"},
                   "status": "running", "result": None, "kim_feedback": None,
                   "script": "eval/e21b_transposition_server.py"}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    for c in todo:
        t0 = time.time()
        while True:
            try:
                r = requests.post(f"{SERVER}/generate", json=payload(c, text[c["pid"]], n_frames), timeout=1800)
                break
            except requests.exceptions.ConnectionError:
                print(f"  {time.strftime('%H:%M')} server unreachable, retrying in 60 s", flush=True)
                time.sleep(60)
        res = r.json()
        if r.status_code != 200 or res.get("status") != "ok" or not res.get("files"):
            print(f"  FAIL {c['id']}: {r.status_code} {str(res)[:300]}", flush=True)
            continue
        shutil.copyfile(res["files"][0], f"{OUT}/{c['id']}.wav")
        c.update(secs=round(time.time() - t0, 1), warnings=res.get("warnings") or [])
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
        print(f"  {c['id']} ({c['secs']}s)", flush=True)


def profile(path):
    import soundfile as sf
    x, sr = sf.read(path, always_2d=True)
    ch = CSR.sc.compute_same_chroma(x, sr, align_to_latent=False)
    out = {}
    for bi, band in ((0, "bass"), (1, "mid")):
        v = CSR.sc.fold_to_12(ch[bi].mean(axis=-1)).astype(np.float64)
        out[band] = v / (np.linalg.norm(v) + 1e-9)
    out["peak"] = float(np.abs(x).max())
    return out


def score():
    from sa3_control.chroma_guided_generator import chord_to_chroma
    rows = [json.loads(l) for l in open(f"{OUT}/cells.jsonl") if l.strip()]
    P = {r["id"]: profile(f"{OUT}/{r['id']}.wav") for r in rows}
    T = {k: (lambda v: v / np.linalg.norm(v))(chord_to_chroma(c).astype(np.float64)) for k, c in KEYS.items()}
    rot = lambda a, b: int(np.argmax([float(np.roll(a, r) @ b) for r in range(12)]))
    pids = sorted({r["pid"] for r in rows})
    summary, per_prompt = {}, {}
    for h, (_, _, gains) in HEADS.items():
        for g in gains:
            for band in ("bass", "mid"):
                hits = n = 0; own = []; other = []
                for pid in pids:
                    base, k0 = P.get(cid(pid)), P.get(cid(pid, h, 0, g))
                    if base is None or k0 is None:
                        continue
                    for k in KEYS:
                        pk = P.get(cid(pid, h, k, g))
                        if pk is None:
                            continue
                        own.append(float(pk[band] @ T[k] - base[band] @ T[k]))
                        other += [float(pk[band] @ T[j] - base[band] @ T[j]) for j in KEYS if j != k]
                        if k:
                            r = rot(k0[band], pk[band]); hit = int(r == k); hits += hit; n += 1
                            per_prompt.setdefault(f"{h}|g{g}|{band}", {}).setdefault(pid, []).append([k, r])
                summary[f"{h}|g{g}|{band}"] = {"equivariance_hits": hits, "n": n, "chance": round(n / 12, 1),
                                               "own_delta": round(float(np.mean(own)), 4), "other_delta": round(float(np.mean(other)), 4),
                                               "specificity": round(float(np.mean(own) - np.mean(other)), 4)}
    pc = {}
    for f in sorted(os.listdir(OUT)):
        if f.startswith("posctl__") and f.endswith(".wav"):
            stem, kk = f[:-4].rsplit("__k", 1)
            src = stem[len("posctl__"):]
            q = profile(f"{OUT}/{f}")
            for band in ("bass", "mid"):
                pc.setdefault(band, [0, 0]); pc[band][0] += int(rot(P[src][band], q[band]) == int(kk)); pc[band][1] += 1
    dead = sorted(k for k, v in P.items() if v["peak"] > 0.999)
    res = {"summary": summary, "positive_control_bungee": {b: {"hits": h, "n": n} for b, (h, n) in pc.items()},
           "per_prompt_k_and_best_rotation": per_prompt, "dead_clips_peak_1": dead, "n_clips": len(rows)}
    json.dump(res, open(f"{OUT}/e21b_results.json", "w"), indent=1)
    for k, v in summary.items():
        print(k, v)
    print("positive control:", res["positive_control_bungee"], "dead:", len(dead))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["render", "score", "dry"])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--head", action="append", default=None, help="NAME=PATH@G1,G2 (repeatable; replaces the defaults)")
    ap.add_argument("--base-from", default=None, help="dir holding <pid>__base.wav renders to reuse")
    ap.add_argument("--purpose", default=None)
    a = ap.parse_args()
    OUT, BASE_FROM, PURPOSE = a.out, a.base_from, a.purpose
    if a.head:
        HEADS = dict(parse_head(h) for h in a.head)
    {"render": render, "score": score, "dry": lambda: render(dry=True)}[a.mode]()
