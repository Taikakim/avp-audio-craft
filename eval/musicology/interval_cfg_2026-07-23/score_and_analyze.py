#!/usr/bin/env python
"""score_and_analyze.py -- scoring + per-cell analysis for the interval-CFG grid
(companion to eval/interval_cfg_render.py; see run_meta.json for the hypothesis).

Stages (each resumable / skippable):
  1. hook   -- eval/hook_eval_renders.py on renders/*.wav (muscriptor GPU transcription,
               taken under the fleet .gpu.lock; cached .mid in <out_root>/midi, incl. the
               symlinked transcriptions of reused model_matrix control cells).
  2. clap   -- eval/clap_score.py (sat-venv, CPU) against our manifest.jsonl.
  3. disint -- eval/disintegration_metrics.py measure()+gate() per clip vs the c7
               constant-cfg baseline of the same (model, prompt, seed).
  4. analyze-- per (model, arm) cells, NEVER pooled across models (Kim's convention):
               hmr median, no-lead rate, clap_matched mean, gate-fail count
               -> results.json + REPORT.md skeleton table.

Run (SAO venv): /home/kim/Projects/SAO/.venv/bin/python \
    eval/musicology/interval_cfg_2026-07-23/score_and_analyze.py [--skip-hook] ...
"""
import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/kim/Projects/SAO")
OUT_ROOT = Path("/run/media/kim/Mantu/sa3_lora_runs/interval_cfg_2026-07-23")
RENDERS = OUT_ROOT / "renders"
EXP = ROOT / "eval/musicology/interval_cfg_2026-07-23"
GPU_LOCK = str(ROOT / ".gpu.lock")
LOCK_HANDLE = "CONTINUITY-icfg"
SAO_PY = str(ROOT / ".venv/bin/python")
SAT_PY = str(ROOT / "stable-audio-tools/sat-venv/bin/python")

HOOK_OUT = EXP / "hook.jsonl"
CLAP_OUT = EXP / "clap.csv"
DISINT_OUT = EXP / "disint.json"
ARM_ORDER = ["c7", "c16", "ivA", "ivB", "ivC", "ivD"]


def manifest():
    rows = []
    seen = set()
    for ln in (OUT_ROOT / "manifest.jsonl").read_text().splitlines():
        e = json.loads(ln)
        if e["file"] in seen:
            continue
        seen.add(e["file"])
        rows.append(e)
    return rows


def run_hook():
    subprocess.check_call(["python3", str(ROOT / "Misc/filelock.py"), "acquire",
                           GPU_LOCK, "--handle", LOCK_HANDLE, "--pid-aware",
                           "--pid", str(os.getpid()), "--timeout", "43200"])
    try:
        subprocess.check_call(
            [SAO_PY, str(ROOT / "eval/hook_eval_renders.py"),
             "--wavs", str(RENDERS / "*.wav"),
             "--out", str(HOOK_OUT), "--midi-dir", str(OUT_ROOT / "midi")],
            cwd=str(ROOT),
            env={**os.environ, "FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE"})
    finally:
        subprocess.call(["python3", str(ROOT / "Misc/filelock.py"), "release",
                         GPU_LOCK, "--handle", LOCK_HANDLE])


def run_clap():
    subprocess.check_call(
        [SAT_PY, str(ROOT / "eval/clap_score.py"),
         "--manifest", str(OUT_ROOT / "manifest.jsonl"),
         "--clips-dir", str(RENDERS), "--sample", "0", "--device", "cpu",
         "--out", str(CLAP_OUT)] + (["--append"] if CLAP_OUT.exists() else []),
        cwd=str(ROOT))


def run_disint(man):
    sys.path.insert(0, str(ROOT / "eval"))
    from disintegration_metrics import measure, gate
    done = json.load(open(DISINT_OUT)) if DISINT_OUT.exists() else {}
    by_file = {e["file"]: e for e in man}
    # baselines: constant-cfg7 cell of the same (model, prompt, seed)
    base_key = {}
    for e in man:
        if e["arm"] == "c7":
            base_key[(e["model"], e["prompt_id"], e["seed"])] = e["file"]
    stats_cache = {}

    def stats_for(fname):
        if fname not in stats_cache:
            p = RENDERS / fname
            stats_cache[fname] = measure(p) if p.exists() else None
        return stats_cache[fname]

    n = 0
    for e in man:
        if e["file"] in done:
            continue
        st = stats_for(e["file"])
        if st is None:
            continue
        bfile = base_key.get((e["model"], e["prompt_id"], e["seed"]))
        bst = stats_for(bfile) if bfile else None
        g = gate(st, bst) if bst else {"blown": None, "reasons": ["no-baseline"]}
        done[e["file"]] = {**st, **g, "baseline": bfile}
        n += 1
        if n % 25 == 0:
            json.dump(done, open(DISINT_OUT, "w"))
            print(f"[disint] {n} scored", flush=True)
    json.dump(done, open(DISINT_OUT, "w"), indent=0)
    print(f"[disint] total {len(done)} rows -> {DISINT_OUT}")


def med(xs):
    return round(statistics.median(xs), 3) if xs else None


def analyze(man):
    hook = {}
    if HOOK_OUT.exists():
        for ln in HOOK_OUT.read_text().splitlines():
            try:
                r = json.loads(ln)
                hook[r["clip"]] = r
            except Exception:
                pass
    clap = {}
    if CLAP_OUT.exists():
        for r in csv.DictReader(CLAP_OUT.open()):
            clap[r["file"]] = r
    disint = json.load(open(DISINT_OUT)) if DISINT_OUT.exists() else {}

    cells = {}
    for e in man:
        stem = Path(e["file"]).stem
        cells.setdefault((e["model"], e["arm"]), []).append({
            "hook": hook.get(stem), "clap": clap.get(e["file"]),
            "disint": disint.get(e["file"]), "entry": e})

    results = {"cells": {}, "meta": json.load(open(OUT_ROOT / "run_meta.json"))
               if (OUT_ROOT / "run_meta.json").exists() else {}}
    lines = ["| model | arm | n | hmr med | no-lead % | pedal-occ med | clap med | gate fails |",
             "|---|---|---|---|---|---|---|---|"]
    for model in dict.fromkeys(m for m, a in cells):
        for arm in ARM_ORDER:
            rows = cells.get((model, arm), [])
            hks = [r["hook"] for r in rows if r["hook"] and "hook_melodic_ratio" in (r["hook"] or {})]
            hmr = [h["hook_melodic_ratio"] for h in hks]
            nolead = [1 if (h.get("n_lead") or 0) == 0 else 0 for h in
                      [r["hook"] for r in rows if r["hook"]]]
            pocc = [h["pedal_occupancy"] for h in hks if h.get("pedal_occupancy") is not None]
            cl = [float(r["clap"]["clap_matched"]) for r in rows if r["clap"]]
            gf = sum(1 for r in rows if r["disint"] and r["disint"].get("blown"))
            cell = {"n": len(rows), "n_hook": len(hks),
                    "hmr_median": med(hmr),
                    "no_lead_rate": round(sum(nolead) / len(nolead), 3) if nolead else None,
                    "pedal_occ_median": med(pocc),
                    "clap_matched_median": med(cl), "clap_n": len(cl),
                    "gate_fails": gf}
            results["cells"][f"{model}|{arm}"] = cell
            lines.append(f"| {model} | {arm} | {cell['n']} | {cell['hmr_median']} | "
                         f"{cell['no_lead_rate']} | {cell['pedal_occ_median']} | "
                         f"{cell['clap_matched_median']} | {gf} |")
    json.dump(results, open(EXP / "results.json", "w"), indent=1)
    table = "\n".join(lines)
    print(table)
    (EXP / "results_table.md").write_text(table + "\n")
    print(f"[analyze] -> {EXP / 'results.json'} + results_table.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-hook", action="store_true")
    ap.add_argument("--skip-clap", action="store_true")
    ap.add_argument("--skip-disint", action="store_true")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()
    man = manifest()
    print(f"[score] {len(man)} manifest cells")
    if not args.analyze_only:
        if not args.skip_hook:
            run_hook()
        if not args.skip_clap:
            run_clap()
        if not args.skip_disint:
            run_disint(man)
    analyze(man)


if __name__ == "__main__":
    main()
