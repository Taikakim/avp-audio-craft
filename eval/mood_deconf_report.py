#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""mood_deconf_report.py -- reads the eval/mood_deconf_render.py run: do de-confounded mood targets steer better than the naive ones?

Every clip is compared with its own model + prompt baseline (guided sampler at gain 0). Per clip:
  own      change in the requested mood's classifier score (Essentia EffNet MTG-Jamendo, 56 dimensions)
  melodic  change in the melodic score (what the one-prompt run said de-confounding protects)
  off      mean absolute change over the other musical tags (collateral change; lower = more selective)
  ce       change in Audiobox CE
  gate     control_head_disintegration_eval.gate(), unchanged thresholds, plus the latent-level leg
Paired naive vs de-confounded: same model, prompt and gain, difference Deconf - naive, with a 95% bootstrap interval that
resamples PROMPTS (15), since clips of one prompt are not independent. "wins" counts pairs where Deconf is higher.
Also: at MATCHED own-tag movement (E25 review), and does the result on the one prompt the first run used (rb_bracket_0) hold on the other 14, and the first run's named claims.
Writes report.json and report.txt in the run dir. RUN: mir/bin/python eval/mood_deconf_report.py
"""
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from control_head_disintegration_eval import DB, gate  # noqa: E402

OUT = Path("/home/kim/evals_aac/control_runs/mood_deconf_20261103")
GAINS = (1024, 2048, 4096, 8192)
MODELS = ("base", "adamw", "goa", "combo_fusion_goa")
OWN = {"Melodic": "melodic", "Space": "space", "Dark": "dark", "Deconf_Melodic": "melodic", "Deconf_Space": "space", "Deconf_Dark": "dark",
       "Deconf_Uplifting": "uplifting", "Deconf_AntiDark": "melodic"}
PAIRS = (("Melodic", "Deconf_Melodic"), ("Space", "Deconf_Space"), ("Dark", "Deconf_Dark"))
MUS = ["melodic", "energetic", "space", "retro", "dark", "dream", "relaxing", "meditative", "calm", "soundscape", "film", "epic", "deep", "uplifting",
       "happy", "party", "positive", "upbeat", "groovy", "cool", "heavy", "powerful", "fast", "slow", "sad", "melancholic", "emotional"]
FIRST_PROMPT = "rb_bracket_0"
MEASURES = ("own", "melodic", "off", "ce")


def load():
    cells = {}
    for l in (OUT / "cells.jsonl").read_text().splitlines():
        c = json.loads(l)
        cells[c["id"]] = c
    classes = json.loads((OUT / "classes.json").read_text())
    idx = {k: i for i, k in enumerate(classes)}
    for l in (OUT / "mood_scores.jsonl").read_text().splitlines():
        d = json.loads(l)
        if d["id"] in cells:
            cells[d["id"]]["scores"] = np.array(d["scores"])
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    for c in cells.values():
        c["metrics"] = rows.get(str(OUT / f"{c['id']}.m4a"))
    return cells, idx


def per_clip(cells, idx):
    base = {(c["model"], c["pid"]): c for c in cells.values() if c["gain"] == 0}
    steered = []
    for c in cells.values():
        b = base.get((c["model"], c["pid"]))
        if c["gain"] == 0 or b is None or "scores" not in c or "scores" not in b:
            continue
        d = c["scores"] - b["scores"]
        own = OWN[c["tid"]]
        c["own"] = float(d[idx[own]])
        c["melodic"] = float(d[idx["melodic"]])
        c["off"] = float(np.mean([abs(d[idx[t]]) for t in MUS if t != own]))
        c["dark"] = float(d[idx["dark"]])
        m, mb = c["metrics"], b["metrics"]
        c["ce"] = (m["ce"] - mb["ce"]) if m and mb and m.get("ce") is not None and mb.get("ce") is not None else None
        if m and mb:
            c["bad"], c["why"], _ = gate({**m, "z_std": c["z_std"]}, {**mb, "z_std": b["z_std"]}, rhythmic=True)
        else:
            c["bad"], c["why"] = c["z_std"] / b["z_std"] > 1.3, ["latent-level"] if c["z_std"] / b["z_std"] > 1.3 else []
        c["same_as_base"] = abs(c["z_std"] - b["z_std"]) < 1e-6
        steered.append(c)
    return steered, base


def fmean(xs):
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 4) if xs else None


def summary(rows):
    return {"n": len(rows), "own": fmean([r["own"] for r in rows]), "own_up": round(float(np.mean([r["own"] > 0 for r in rows])), 3) if rows else None,
            "melodic": fmean([r["melodic"] for r in rows]), "off": fmean([r["off"] for r in rows]), "ce": fmean([r["ce"] for r in rows]),
            "fails": sum(1 for r in rows if r["bad"])}


def boot(by_prompt, rng, n=4000):
    """95% interval of the mean, resampling prompts. by_prompt: {pid: [differences]}."""
    means = np.array([np.mean(v) for v in by_prompt.values() if v])
    if len(means) < 2:
        return None, None
    draws = rng.choice(means, size=(n, len(means))).mean(axis=1)
    return round(float(np.percentile(draws, 2.5)), 4), round(float(np.percentile(draws, 97.5)), 4)


def paired(steered, rng, keep=lambda c: True):
    by = {(c["model"], c["pid"], c["tid"], c["gain"]): c for c in steered}
    out = {}
    for naive, dec in PAIRS:
        for measure in MEASURES:
            for g in list(GAINS) + ["all"]:
                bp, n, wins = defaultdict(list), 0, 0
                for (m, p, t, gg), c in by.items():
                    if t != naive or not keep(c) or (g != "all" and gg != g):
                        continue
                    d = by.get((m, p, dec, gg))
                    if d is None or c[measure] is None or d[measure] is None:
                        continue
                    x = d[measure] - c[measure]
                    bp[p].append(x)
                    n += 1
                    wins += x > 0
                if n:
                    lo, hi = boot(bp, rng)
                    out[f"{dec}|{measure}|{g}"] = {"n": n, "diff": round(float(np.mean([x for v in bp.values() for x in v])), 4), "wins": wins, "ci": [lo, hi]}
    return out


def matched(steered, rng, tol=0.01, min_move=0.01):
    """Deconf vs naive at MATCHED movement of the requested tag, not equal gain (CONTINUITY's E25 review): a target that moves its tag
    less also costs less, so an equal-gain comparison can flatter it. Per model + prompt, each naive clip whose tag moved by at least
    min_move is paired with the Deconf gain that moved it closest, if within tol. Both clips gate-clean. A Deconf clip can serve
    two naive gains. Lower collateral and a less negative melodic change favour Deconf."""
    by = defaultdict(list)
    for c in steered:
        by[(c["model"], c["pid"], c["tid"])].append(c)
    out = {}
    for naive, dec in PAIRS:
        rows = []
        for (m, p, t), clips in by.items():
            if t != naive:
                continue
            for c in clips:
                if c["bad"] or c["own"] < min_move:
                    continue
                cand = [d for d in by.get((m, p, dec), []) if not d["bad"]]
                if not cand:
                    continue
                d = min(cand, key=lambda x: abs(x["own"] - c["own"]))
                if abs(d["own"] - c["own"]) <= tol:
                    rows.append((p, c, d))
        res = {"n_pairs": len(rows), "prompts": len({r[0] for r in rows}), "n_naive_eligible": sum(1 for c in steered if c["tid"] == naive and not c["bad"] and c["own"] >= min_move)}
        for measure in ("melodic", "off", "ce"):
            bp = defaultdict(list)
            for p, c, d in rows:
                if c[measure] is not None and d[measure] is not None:
                    bp[p].append(d[measure] - c[measure])
            xs = [x for v in bp.values() for x in v]
            if xs:
                res[measure] = {"diff": round(float(np.mean(xs)), 4), "deconf_higher": int(sum(x > 0 for x in xs)), "n": len(xs), "ci": list(boot(bp, rng))}
        out[dec] = res
    return out


def reach(steered):
    """How far each target can move its own tag: per model + prompt the largest change over gains among gate-clean clips, then the mean."""
    by = defaultdict(list)
    for c in steered:
        if not c["bad"]:
            by[(c["model"], c["pid"], c["tid"])].append(c["own"])
    out = defaultdict(list)
    for (m, p, t), xs in by.items():
        out[t].append(max(xs))
    return {t: {"mean_best": fmean(v), "n": len(v)} for t, v in out.items()}


def main():
    cells, idx = load()
    steered, base = per_clip(cells, idx)
    rng = np.random.default_rng(1)
    rep = {"n_clips": len(cells), "n_steered_scored": len(steered), "expected": 1980}
    rep["by_target_gain"] = {f"{t}|{g}": summary([c for c in steered if c["tid"] == t and c["gain"] == g]) for t in OWN for g in GAINS}
    rep["by_model_target_gain"] = {f"{m}|{t}|{g}": summary([c for c in steered if c["model"] == m and c["tid"] == t and c["gain"] == g])
                                   for m in MODELS for t in OWN for g in GAINS}
    rep["by_prompt_target"] = {f"{p}|{t}": summary([c for c in steered if c["pid"] == p and c["tid"] == t])
                               for p in sorted({c["pid"] for c in steered}) for t in OWN}
    rep["paired"] = paired(steered, rng)
    rep["paired_clean"] = paired(steered, rng, keep=lambda c: not c["bad"])
    rep["matched"] = matched(steered, rng)
    rep["reach"] = reach(steered)
    rep["paired_first_prompt"] = {}
    rep["paired_other_prompts"] = {}
    for naive, dec in PAIRS:
        for measure in MEASURES:
            for label, want in (("paired_first_prompt", True), ("paired_other_prompts", False)):
                by = {(c["model"], c["pid"], c["gain"]): c for c in steered if c["tid"] == dec and (c["pid"] == FIRST_PROMPT) == want}
                xs = [by[(c["model"], c["pid"], c["gain"])][measure] - c[measure] for c in steered if c["tid"] == naive and (c["model"], c["pid"], c["gain"]) in by
                      and c[measure] is not None and by[(c["model"], c["pid"], c["gain"])][measure] is not None]
                rep[label][f"{dec}|{measure}"] = {"n": len(xs), "diff": fmean(xs), "wins": int(sum(x > 0 for x in xs))}

    def score(m, p, t, g, tag):
        c = cells.get(f"{m}__{p}__{t}__g{g}" if g else f"{m}__{p}__base0")
        return round(float(c["scores"][idx[tag]]), 4) if c and "scores" in c else None

    rep["first_run_claims"] = {
        "goa, Deconf_Uplifting, melodic score over gain": {p: [score("goa", p, None, 0, "melodic")] + [score("goa", p, "Deconf_Uplifting", g, "melodic") for g in GAINS]
                                                           for p in sorted({c["pid"] for c in steered})},
        "base, melodic score under Dark vs Deconf_Dark at 4096": {p: [score("base", p, None, 0, "melodic"), score("base", p, "Dark", 4096, "melodic"), score("base", p, "Deconf_Dark", 4096, "melodic")]
                                                                  for p in sorted({c["pid"] for c in steered})},
    }
    why = Counter(w.split("(")[0] for c in steered for w in c["why"])
    rep["gate_reasons"] = dict(why)
    rep["gate_by_gain"] = {str(g): {"fails": sum(1 for c in steered if c["gain"] == g and c["bad"]), "n": sum(1 for c in steered if c["gain"] == g)} for g in GAINS}
    rep["same_as_base"] = [c["id"] for c in steered if c["same_as_base"]]
    rep["no_ce"] = sum(1 for c in steered if c["ce"] is None)
    rep["faults"] = [json.loads(l) for l in (OUT / "faults.jsonl").read_text().splitlines()] if (OUT / "faults.jsonl").exists() else []
    checks = [json.loads(l) for l in (OUT / "chunk_checks.jsonl").read_text().splitlines()]
    rep["checks"] = {
        "first_vs_second": {"n": sum(c["kind"] == "first_vs_second" for c in checks), "first_bad": sum(c.get("first_bad", False) for c in checks),
                            "z_differs": sum(c["kind"] == "first_vs_second" and c["z_rms"] > 0 for c in checks),
                            "first_audio_differs": sum(c["kind"] == "first_vs_second" and abs(c["audio_std_first"] - c["audio_std_second"]) > 1e-4 for c in checks)},
        "repeats": {"n": sum(c["kind"] != "first_vs_second" for c in checks), "bad": sum(c.get("bad", False) or c.get("end_bad", False) for c in checks),
                    "z_differs": sum(c["kind"] != "first_vs_second" and c["z_rms"] > 0 for c in checks),
                    "audio_differs": sum(abs(c.get("audio_std_ref", c.get("audio_std_start", 0)) - c.get("audio_std_now", c.get("audio_std_end", 0))) > 1e-4 for c in checks if c["kind"] != "first_vs_second")},
    }
    (OUT / "report.json").write_text(json.dumps(rep, indent=1))

    L = [f"clips {rep['n_clips']} of {rep['expected']}; steered and scored {rep['n_steered_scored']}; no CE {rep['no_ce']}; steered with the baseline's z_std {len(rep['same_as_base'])}",
         f"faults {len(rep['faults'])}; checks {rep['checks']}", f"gate by gain {rep['gate_by_gain']}; reasons {rep['gate_reasons']}", "",
         "BY TARGET AND GAIN (all models, all prompts): own change, fraction up, melodic change, collateral, CE change, gate fails/n"]
    for t in OWN:
        L.append("  " + t + " [" + OWN[t] + "]: " + " | ".join(f"g{g} {rep['by_target_gain'][f'{t}|{g}']['own']:+.3f} up {rep['by_target_gain'][f'{t}|{g}']['own_up']:.2f} mel {rep['by_target_gain'][f'{t}|{g}']['melodic']:+.3f} off {rep['by_target_gain'][f'{t}|{g}']['off']:.3f} ce {rep['by_target_gain'][f'{t}|{g}']['ce'] if rep['by_target_gain'][f'{t}|{g}']['ce'] is not None else 0:+.2f} {rep['by_target_gain'][f'{t}|{g}']['fails']}/{rep['by_target_gain'][f'{t}|{g}']['n']}" for g in GAINS))
    L += ["", "PAIRED Deconf - naive, all prompts and models (95% interval over prompts):"]
    for k, v in rep["paired"].items():
        L.append(f"  {k}: {v['diff']:+.4f} [{v['ci'][0]}, {v['ci'][1]}] wins {v['wins']}/{v['n']}")
    L += ["", "MATCHED own-tag movement (within 0.01, moved at least 0.01, gate-clean), Deconf - naive; the comparison E25 asked for:"]
    for k, v in rep["matched"].items():
        L.append(f"  {k}: pairs {v['n_pairs']} of {v['n_naive_eligible']} eligible naive clips, {v['prompts']} prompts; " + "; ".join(
            f"{m} {v[m]['diff']:+.4f} {v[m]['ci']} higher {v[m]['deconf_higher']}/{v[m]['n']}" for m in ("melodic", "off", "ce") if m in v))
    L += ["", "REACH, best gate-clean own-tag change per model + prompt, mean:"] + [f"  {t}: {v['mean_best']} (n {v['n']})" for t, v in sorted(rep["reach"].items())]
    L += ["", "PAIRED, the first run's prompt vs the other 14:"]
    for k in rep["paired_first_prompt"]:
        a, b = rep["paired_first_prompt"][k], rep["paired_other_prompts"][k]
        L.append(f"  {k}: first {a['diff']} wins {a['wins']}/{a['n']} | others {b['diff']} wins {b['wins']}/{b['n']}")
    L += ["", "FIRST RUN'S CLAIMS, by prompt:"]
    for k, v in rep["first_run_claims"].items():
        L.append("  " + k)
        for p, xs in v.items():
            L.append(f"    {p}: {xs}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
