#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-11-03)
"""post_run_gate.py -- ONE command: the standard post-run disintegration gate for a control head (docs/TRAINING.md D40, owner 2026-11-03).

Renders ONE prompt at normal settings on the render server (:8056, which must be running base `medium-base`): an UNSTEERED baseline
(the same head attached, rho = mu = 0, so it goes through the guided sampler like the steered render) and a STEERED clip (head at
--gain, constant --value), same prompt and seed. Then eval/disintegration_metrics.py (the wav-side gate: whitening, hf-blowout,
zcr, each vs the baseline) judges the steered clip. Prints PASS/FAIL, writes <out>/post_run_gate.json and, with --run-dir, appends
the result to that run's record (Misc/run_record.py append, D38). Run it on the LAST and the BEST epoch.
NOT covered (say so when reporting): Audiobox CE drift, latent-level leg (z_std) and beat-loss of the full gate in
control_head_disintegration_eval.py. A PASS here means "not obviously disintegrated by the wav-side DSP screen", not good: listen.
Defaults: 24 steps, cfg 7, 23.79 s (256 frames), seed 786795416 (canonical rb_common_0 seed), gain 512 (energy-head operating point).
RUN (GPU lock held by you, render server up with --model medium-base):
  cd /home/kim/Projects/SAO && .venv/bin/python eval/post_run_gate.py --head /path/to/latch_sa3_<feat>_ep10.pt --value -30 [--gain 512] [--run-dir <run dir>]
  --dry-run prints the two requests and exits (no server needed). --value is in the head's RAW feature units (see /info); chroma-type
  heads need --target-npy (a [C,T] raw-unit array) instead.
"""
import argparse, json, os, shutil, subprocess, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RENDER = os.environ.get("SA3_RENDER", "http://127.0.0.1:8056")
PROMPT = "goa trance, psytrance, 145 bpm, rolling bassline, driving kick, hi-hats, hypnotic synth lead"


def post(path, body=None, timeout=1800):
    rq = urllib.request.Request(RENDER + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(rq, timeout=timeout))


def requests(a):
    slot = dict(path=os.path.abspath(a.head), gain=a.gain, start_pct=a.start_pct, end_pct=a.end_pct)
    if a.target_npy:
        import numpy as np
        slot["target_raw"] = np.load(a.target_npy).tolist()
    else:
        slot.update(kind="constant", value=a.value)
    base = dict(prompt=a.prompt, negative_prompt="", steps=a.steps, cfg_scale=a.cfg, seed=a.seed, duration=a.duration, apg_scale=1, ckpt_path=None, dora=None)
    return dict(base, latch=[dict(slot)], rho=0.0, mu=0.0), dict(base, latch=[dict(slot)])    # (baseline, steered)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--head", required=True, help="LatCH head checkpoint (.pt)")
    ap.add_argument("--value", type=float, default=None, help="constant target in RAW feature units")
    ap.add_argument("--target-npy", default=None, help="[C,T] raw-unit target instead of --value")
    ap.add_argument("--gain", type=float, default=512.0); ap.add_argument("--start-pct", type=float, default=0.0); ap.add_argument("--end-pct", type=float, default=0.6)
    ap.add_argument("--prompt", default=PROMPT); ap.add_argument("--steps", type=int, default=24); ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--duration", type=float, default=23.79); ap.add_argument("--seed", type=int, default=786795416)
    ap.add_argument("--out", default=None, help="output dir (default: <head dir>/post_run_gate)"); ap.add_argument("--run-dir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.value is None and not a.target_npy:
        ap.error("give --value (raw units) or --target-npy")
    base_req, steer_req = requests(a)
    if a.dry_run:
        print(json.dumps(dict(baseline=base_req, steered=steer_req), indent=1)[:3000]); return 0
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.head)), "post_run_gate"); os.makedirs(out, exist_ok=True)
    try:
        st = post("/status")
    except Exception as e:
        print("render server not reachable:", e); return 2
    mdl = str(st.get("model") or st.get("model_id") or "")
    if mdl and "base" not in mdl:
        print(f"WARNING: server model is {mdl!r}, the standard gate wants medium-base (24 steps, cfg 7)")
    import disintegration_metrics as D
    tag = os.path.splitext(os.path.basename(a.head))[0]; paths = {}
    for name, req in (("baseline", base_req), ("steered", steer_req)):
        r = post("/generate", req); w = os.path.join(out, f"{tag}__{name}.wav"); shutil.copy(r["files"][0], w); paths[name] = w
    sb, ss = D.measure(paths["baseline"]), D.measure(paths["steered"]); g = D.gate(ss, sb)
    res = dict(head=a.head, prompt=a.prompt, seed=a.seed, steps=a.steps, cfg=a.cfg, gain=a.gain, value=a.value, baseline=sb, steered=ss, gate=g,
               verdict="FAIL" if g["blown"] else "PASS", not_covered="Audiobox CE drift, latent z_std, beat-loss", wavs=paths, warning=("server model " + mdl) if mdl and "base" not in mdl else None)
    json.dump(res, open(os.path.join(out, f"{tag}__post_run_gate.json"), "w"), indent=1)
    print(f"{res['verdict']}  {tag}  gain {a.gain}  reasons {g['reasons']}  (baseline hf {sb['hf']:.4f} -> steered {ss['hf']:.4f}; flat {sb['flatness']:.3f} -> {ss['flatness']:.3f}; zcr {sb['zcr']:.3f} -> {ss['zcr']:.3f})")
    if a.run_dir:
        subprocess.run([sys.executable, os.path.join(HERE, "..", "Misc", "run_record.py"), "append", a.run_dir, "--kind", "auto", "--by", "GHOST-NOTE",
                        "--text", f"post-run disintegration gate {res['verdict']} for {os.path.basename(a.head)} (gain {a.gain}, value {a.value}, {a.steps} steps cfg {a.cfg}, seed {a.seed}): {g['reasons'] or 'no flags'}; hf {sb['hf']:.4f}->{ss['hf']:.4f}. Wav-side screen only (no CE/z_std/beat-loss).",
                        "--source", os.path.join(out, f"{tag}__post_run_gate.json")], check=False)
    return 0 if not g["blown"] else 1


if __name__ == "__main__":
    sys.exit(main())
