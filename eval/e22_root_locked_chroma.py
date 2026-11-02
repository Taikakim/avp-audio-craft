#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-10-29)
"""e22_root_locked_chroma.py -- EXPERIMENTS E22: steer a chord SHAPE (colour) while the root stays where the prompt and
seed put it. Kim 2026-10-29: "it's fine that it shifts the fundamental/root, but very cool would also be one which does not,
forcing it to be maybe more creative."

Two modes, both on the E21 settings (goa finetune, euler 50, cfg 7, whole window, the 14 canonical prompts and seeds):
  rotinv  loss_type cosine_rotinv (stable_audio_3/inference/chroma_losses.chroma_loss_rotinv): soft-min over the 12
          transpositions of the target, so the gradient pulls toward the NEAREST transposition of the shape.
  locked  the plain cosine target, placed on the UNGUIDED render's own bass root (read from E21b's unguided render).
Shapes: major, minor, sus4, diminished (none is a transposition of another). Heads: hpcp (production) and the E13-retrained
same_chroma (C3 ep10), the two heads E21b/E21c showed are transposition-equivariant, at gain 2048.
Unguided renders are reused from E21b; E21b/E21c's absolute major-on-C renders (k0, g2048) are the "root moves" reference.

SCORE (CPU, SAME chroma meter folded to 12, the E21 profile()): root kept = bass-band argmax equals the unguided render's;
colour = best-rotation cosine of the MID band to the shape, minus the unguided render's, against the same for the other three
shapes (specificity > 0 = the render took on the requested colour, in its own key).
RUN: eval/run_e22_20261029.sh (GPU lock, own :8056, render, score).
"""
import argparse, json, os, shutil, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e21b_transposition_server as E  # noqa: E402  (prompts, payload settings, profile, cid)

OUT = "/run/media/kim/Mantu/sa3_control_runs/e22_root_locked_chroma_20261029"
BASE = "/run/media/kim/Mantu/sa3_control_runs/e21b_transposition_canon_20261028"
REF_C = {"hpcp": (BASE, "hpcp"), "same_chroma_e13": ("/run/media/kim/Mantu/sa3_control_runs/e21c_same_chroma_gain_20261029",
                                                     "same_chroma_e13")}
C3 = "/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt"
HEADS = {"hpcp": ("latch_sa3_hpcp_best.pt", 12), "same_chroma_e13": (C3, 384)}
SHAPES = {"maj": "", "min": "m", "sus4": "sus4", "dim": "dim"}
MODES = ("rotinv", "locked")
GAIN = 2048
NOTE = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def shape_vec(shape):
    from sa3_control.chroma_guided_generator import chord_to_chroma
    v = chord_to_chroma("C" + SHAPES[shape]).astype(np.float64)
    return v / np.linalg.norm(v)


def rotmax(a, b):
    return max(float(np.roll(a, r) @ b) for r in range(12))


def base_root(pid):
    return int(np.argmax(E.profile(f"{BASE}/{E.cid(pid)}.wav")["bass"]))


def cid(pid, head, shape, mode):
    return f"{pid}__{head}__{shape}__{mode}__g{GAIN}"


def cells():
    out = []
    for p in E.prompts():
        out.append(dict(id=E.cid(p["id"]), pid=p["id"], seed=int(p["seed"]), head=None))
        for h in HEADS:
            for sh in SHAPES:
                for m in MODES:
                    out.append(dict(id=cid(p["id"], h, sh, m), pid=p["id"], seed=int(p["seed"]), head=h, shape=sh, mode=m))
    return out


def payload(c, text, n_frames, roots):
    p = {"prompt": text, "duration": E.DUR, "steps": E.STEPS, "cfg_scale": E.CFG, "seed": c["seed"], "sampler_type": "euler",
         "apg_scale": 1.0, "dora": {"ckpt_path": E.FT, "strength": 1.0}}
    if c["head"]:
        fn, dim = HEADS[c["head"]]
        root = 0 if c["mode"] == "rotinv" else roots[c["pid"]]
        chord = NOTE[root] + SHAPES[c["shape"]]
        c["chord"] = chord
        raw = E.CSR.build_target_raw(dim, {"id": chord, "kind": "static", "chord": chord}, n_frames)
        p["latch"] = [{"path": fn if os.path.isabs(fn) else str(E.CSR.HEADS_DIR / fn), "gain": float(GAIN),
                       "start_pct": 0.0, "end_pct": 1.0,
                       "loss_type": "cosine_rotinv" if c["mode"] == "rotinv" else "cosine",
                       "target_raw": raw.astype(float).round(5).tolist()}]
    return p


def render():
    import requests
    os.makedirs(OUT, exist_ok=True)
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    text = {p["id"]: p["text"] for p in E.prompts()}
    roots = {pid: base_root(pid) for pid in text}
    todo = [c for c in cells() if c["id"] not in done]
    for c in [c for c in todo if c["head"] is None]:
        shutil.copyfile(f"{BASE}/{c['id']}.wav", f"{OUT}/{c['id']}.wav")
        c.update(secs=0.0, copied_from=BASE, base_root=roots[c["pid"]])
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
    todo = [c for c in todo if c["head"]]
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"run": os.path.basename(OUT), "created": time.strftime("%Y-%m-%d %H:%M"), "owner": "CONTINUITY",
                   "purpose": "EXPERIMENTS E22 (Kim 2026-10-29): steer chord colour while the root stays where prompt and seed put "
                              "it. rotinv = rotation-invariant cosine (soft-min over 12 transpositions); locked = plain cosine on "
                              "the unguided render's own bass root.",
                   "hypothesis": "rotinv keeps the unguided root far more often than absolute major-on-C steering and still moves "
                                 "the mid-band colour toward the requested shape (specificity > 0).",
                   "kill": "root moves as often as under absolute steering, or colour specificity <= 0 at gain 2048.",
                   "recipe": {"finetune": "goa DoRA finetune (subloss_k24 biggoa t512, epoch 63), strength 1.0", "sampler": "euler",
                              "steps": E.STEPS, "cfg": E.CFG, "apg": 1.0, "duration": E.DUR, "latch_window": [0.0, 1.0],
                              "gain": GAIN, "shapes": SHAPES, "modes": list(MODES), "rotinv_tau": 0.05,
                              "heads": {h: os.path.basename(v[0]) for h, v in HEADS.items()},
                              "unguided": "reused from E21b (same prompts, seeds, settings)", "base_roots": roots},
                   "status": "running", "result": None, "kim_feedback": None,
                   "script": "eval/e22_root_locked_chroma.py"}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    n_frames = int(round(E.DUR * E.CSR.FPS))
    print(f"[e22] {len(todo)} cells to render", flush=True)
    for c in todo:
        t0 = time.time()
        while True:
            try:
                r = requests.post(f"{E.SERVER}/generate", json=payload(c, text[c["pid"]], n_frames, roots), timeout=1800)
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


def score():
    rows = [json.loads(l) for l in open(f"{OUT}/cells.jsonl") if l.strip()]
    P = {r["id"]: E.profile(f"{OUT}/{r['id']}.wav") for r in rows}
    S = {s: shape_vec(s) for s in SHAPES}
    pids = sorted({r["pid"] for r in rows})
    root0 = {pid: int(np.argmax(P[E.cid(pid)]["bass"])) for pid in pids}
    summary = {}
    for h in HEADS:
        for m in MODES:
            kept, n, own, other = 0, 0, [], []
            for pid in pids:
                b = P[E.cid(pid)]
                for sh in SHAPES:
                    q = P.get(cid(pid, h, sh, m))
                    if q is None:
                        continue
                    n += 1
                    kept += int(int(np.argmax(q["bass"])) == root0[pid])
                    own.append(rotmax(q["mid"], S[sh]) - rotmax(b["mid"], S[sh]))
                    other += [rotmax(q["mid"], S[o]) - rotmax(b["mid"], S[o]) for o in SHAPES if o != sh]
            summary[f"{h}|{m}"] = {"root_kept": kept, "n": n, "own_delta": round(float(np.mean(own)), 4),
                                   "other_delta": round(float(np.mean(other)), 4),
                                   "specificity": round(float(np.mean(own) - np.mean(other)), 4)}
        # reference: absolute major on C (E21b / E21c k0 g2048), and how often the root moved there
        src, tag = REF_C[h]
        kept = n = 0
        for pid in pids:
            f = f"{src}/{pid}__{tag}__k0__g2048.wav"
            if os.path.exists(f):
                n += 1
                kept += int(int(np.argmax(E.profile(f)["bass"])) == root0[pid])
        summary[f"{h}|absolute_C_major_ref"] = {"root_kept": kept, "n": n,
                                                "note": f"{sum(1 for p in pids if root0[p] == 0)} of {len(pids)} unguided roots are C"}
    dead = sorted(k for k, v in P.items() if v["peak"] > 0.999)
    res = {"summary": summary, "unguided_roots": {p: NOTE[r] for p, r in root0.items()}, "dead_clips_peak_1": dead,
           "n_clips": len(rows)}
    json.dump(res, open(f"{OUT}/e22_results.json", "w"), indent=1)
    for k, v in summary.items():
        print(k, v)
    print("dead:", len(dead))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["render", "score", "dry"])
    a = ap.parse_args()
    if a.mode == "dry":
        text = {p["id"]: p["text"] for p in E.prompts()}
        cs = [c for c in cells() if c["head"]]
        print(len(cs), "guided cells;", json.dumps(payload(cs[1], text[cs[1]["pid"]], 215, {p: 7 for p in text}))[:400])
    else:
        {"render": render, "score": score}[a.mode]()
