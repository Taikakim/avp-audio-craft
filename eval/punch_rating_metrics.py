#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""punch_rating_metrics.py -- objective metrics for every pair in the punch rating set, so Kim's 1-5 ratings can later be matched against them.

Kim 2026-10-14 (away for hours): "start running the ratings ... zero crossings, CLAP, spectral centroid, crest, etc." For each manifest entry it measures the ORIGINAL and the
LEVEL-MATCHED steered clip (so loudness is not a confound; his criterion is that louder / more compressed is not better): DSP (rms, crest, zcr, centroid, flatness,
hf ratio, flux, onset density), CLAP (match to the clip's own prompt; stock LAION checkpoint, CPU), Audiobox CE/CU/PC/PQ (mir venv, CPU). Writes metrics.json =
{entry_id: {"base": {...}, "matched": {...}, "delta": {...}}} next to the manifest; the rating server merges it into /api/state.
Legs (run by the wrapper in this file's docstring order):   dsp  |  clap  |  audiobox  |  merge
    SAO/.venv/bin/python eval/punch_rating_metrics.py dsp
    SAO/.venv-rocm10-amd/bin/python eval/punch_rating_metrics.py clap
    mir/mir/bin/python eval/punch_rating_metrics.py audiobox
    SAO/.venv/bin/python eval/punch_rating_metrics.py merge
Audit note (CLAUDE.md): CLAP moved 0.11 on the 24-step control at one seed, so it is reported but must not be believed until it correlates with the ratings; the same holds for every number here.
"""
import json
import os
import sys

DATA = "/run/media/kim/Mantu/sa3_control_runs/punch_rating_20261014"
CLIPS = f"{DATA}/clips"


def entries():
    return json.load(open(f"{DATA}/manifest.json"))["entries"]


def files():
    out = {}
    for e in entries():
        out[e["base"]] = f"{CLIPS}/{e['base']}"
        out[e["matched"]] = f"{CLIPS}/{e['matched']}"
    return out


def leg_dsp():
    sys.path.append("/home/kim/Projects/SAO")
    from control.sa3_control.clip_metrics import clip_metrics
    cols = ["dur", "rms", "crest", "zcr", "onset_p95", "centroid", "flatness", "flux", "hf_ratio", "bpm_librosa"]
    res = {}
    for k, p in files().items():
        v = clip_metrics(p)[1]
        res[k] = dict(zip(cols, v)) if v else None
    json.dump(res, open(f"{DATA}/m_dsp.json", "w"))
    print("DSP_DONE", len(res))


def leg_clap():
    import subprocess
    prompt = json.load(open(f"{DATA}/presets.json"))["_base"]["prompt"]
    man = f"{DATA}/m_clap_manifest.jsonl"
    with open(man, "w") as f:
        for k, p in files().items():
            f.write(json.dumps({"file": p, "model": k, "ckpt": None, "prompt_id": "punch", "prompt_text": prompt, "cfg": 9, "strength": None}) + "\n")
    subprocess.run(["/home/kim/Projects/SAO/.venv-rocm10-amd/bin/python", "/home/kim/Projects/SAO/eval/clap_score.py", "--manifest", man, "--clips-dir", "/",
                    "--sample", "0", "--device", "cpu", "--out", f"{DATA}/m_clap.csv"], check=False)
    print("CLAP_DONE")


def leg_audiobox():
    import warnings
    warnings.filterwarnings("ignore")
    sys.path.insert(0, "/home/kim/Projects/mir/src")
    from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics as ab
    res = json.load(open(f"{DATA}/m_audiobox.json")) if os.path.exists(f"{DATA}/m_audiobox.json") else {}
    for i, (k, p) in enumerate(files().items()):
        if k in res:
            continue
        try:
            res[k] = {a: float(b) for a, b in ab(p).items()}
        except Exception as e:
            print("AB fail", k, str(e)[:80], flush=True)
        if i % 8 == 0:
            json.dump(res, open(f"{DATA}/m_audiobox.json", "w"))
    json.dump(res, open(f"{DATA}/m_audiobox.json", "w"))
    print("AUDIOBOX_DONE", len(res))


def leg_merge():
    import csv
    dsp = json.load(open(f"{DATA}/m_dsp.json")) if os.path.exists(f"{DATA}/m_dsp.json") else {}
    clap = {}
    if os.path.exists(f"{DATA}/m_clap.csv"):
        clap = {r["model"]: {"clap": float(r["clap_matched"])} for r in csv.DictReader(open(f"{DATA}/m_clap.csv"))}
    abx = json.load(open(f"{DATA}/m_audiobox.json")) if os.path.exists(f"{DATA}/m_audiobox.json") else {}
    out = {}
    for e in entries():
        row = {}
        for side, key in (("base", e["base"]), ("matched", e["matched"])):
            d = {}
            if dsp.get(key):
                d.update(dsp[key])
            d.update(clap.get(key, {}))
            d.update({"ab_" + a: b for a, b in (abx.get(key) or {}).items()})
            row[side] = d
        row["delta"] = {k: row["matched"][k] - row["base"][k] for k in row["base"] if k in row["matched"] and isinstance(row["base"][k], (int, float)) and k != "dur"}
        out[e["id"]] = row
    json.dump(out, open(f"{DATA}/metrics.json", "w"))
    print("MERGE_DONE", len(out))


if __name__ == "__main__":
    {"dsp": leg_dsp, "clap": leg_clap, "audiobox": leg_audiobox, "merge": leg_merge}[sys.argv[1]]()
