#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-11-03)
"""e25b_report.py -- read E25b: same prompt and seed with and without a word.
consistency = leave-one-prompt-out projection of a clip's mood change (logit space) on the mean change of the other 13 prompts; high means the word pushes
the render the same way whatever the prompt. Compared with the placebo words. Interval: 95% bootstrap over prompts. RUN: .venv/bin/python eval/e25b_report.py"""
import json, sqlite3
from pathlib import Path
import numpy as np
OUT = Path("/home/kim/evals_aac/control_runs/e25b_caption_words_20261103")
DB = "/home/kim/Projects/SAO/eval/clip_metrics.db"
TEST = ["dark", "tense", "aggressive", "industrial", "minimalist", "mechanical", "dystopian", "raw", "unsettling", "gritty", "introspective", "acidic", "euphoric"]
PLACEBO = ["blue", "wooden", "tuesday", "seven", "paper", "window"]
POS = ["ambient", "solo_piano", "ambient_no_drums", "heavy_metal"]
TAG = {"solo_piano": "calm", "ambient_no_drums": "calm", "heavy_metal": "heavy", "dark": "dark", "euphoric": "uplifting", "ambient": "calm", "aggressive": "heavy", "introspective": "calm", "dystopian": "dark", "tense": "dark", "unsettling": "dark", "gritty": "heavy", "raw": "heavy", "industrial": "heavy", "mechanical": "heavy"}
cells = {json.loads(l)["id"]: json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()}
S = {json.loads(l)["id"]: json.loads(l) for l in (OUT / "scores.jsonl").read_text().splitlines()}
C = json.load(open(OUT / "classes.json"))
db = sqlite3.connect(DB); cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)")]
ce = {Path(r[cols.index("path")]).stem: r[cols.index("ce")] for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
L = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
rng = np.random.default_rng(0)
pids = sorted({c["pid"] for c in cells.values()})
def stats(m, w):
    D, dp, dce, dc, df, don = [], [], [], [], [], []
    for p in pids:
        a, b = S[f"{m}__{p}__plain"], S[f"{m}__{p}__{w}"]
        D.append(L(np.array(b["mood"])) - L(np.array(a["mood"]))); dp.append(np.array(b["mood"]) - np.array(a["mood"]))
        dce.append((ce.get(f"{m}__{p}__{w}") or np.nan) - (ce.get(f"{m}__{p}__plain") or np.nan))
        dc.append(np.log2(b["centroid"] / a["centroid"]) * 12); df.append(b["flatness"] - a["flatness"]); don.append(b["onsets"] - a["onsets"])
    D, dp = np.array(D), np.array(dp); n = len(D)
    proj = np.array([D[i] @ ((v := D[np.arange(n) != i].mean(0)) / (np.linalg.norm(v) + 1e-9)) for i in range(n)])
    boots = [proj[rng.integers(0, n, n)].mean() for _ in range(2000)]
    t = dp.mean(0) / (dp.std(0, ddof=1) / np.sqrt(n) + 1e-9)
    top = [(C[i], round(float(dp.mean(0)[i]), 3), int((dp[:, i] > 0).sum())) for i in np.argsort(-np.abs(t))[:4]]
    tag = TAG.get(w)
    return dict(consistency=round(float(proj.mean()), 3), ci=[round(float(x), 3) for x in np.percentile(boots, [2.5, 97.5])], move=round(float(np.linalg.norm(D, axis=1).mean()), 2),
                tag=tag, tag_change=None if not tag else round(float(dp[:, C.index(tag)].mean()), 4), tag_up=None if not tag else int((dp[:, C.index(tag)] > 0).sum()),
                ce=round(float(np.nanmean(dce)), 2), centroid_st=round(float(np.mean(dc)), 2), centroid_up=int((np.array(dc) > 0).sum()), flatness=round(float(np.mean(df)), 4), onsets=round(float(np.mean(don)), 2), top=top)
R = {}; out = []
for m in ("base", "goa"):
    rows = {w: stats(m, w) for w in TEST + PLACEBO + POS}
    pl = [rows[w]["consistency"] for w in PLACEBO]
    for w, r in rows.items():
        r["above_placebos"] = bool(r["ci"][0] > max(pl))
    R[m] = rows
    out.append(f"\n{m}  placebo consistency {pl}, max {max(pl)}; known positives { {w: rows[w]['consistency'] for w in POS} }")
    out.append(f"{'word':14s} {'consist':>7s} {'95% CI':>15s} {'above':>5s} {'move':>5s} {'tag':>9s} {'dTag':>7s} {'up/14':>5s} {'dCE':>6s} {'dCent st':>8s} {'dOnset':>6s}  top tags")
    for w in sorted(rows, key=lambda x: -rows[x]["consistency"]):
        r = rows[w]
        out.append(f"{w:14s} {r['consistency']:7.3f} {str(r['ci']):>15s} {str(r['above_placebos'])[0]:>5s} {r['move']:5.2f} {str(r['tag'])[:9]:>9s} {str(r['tag_change']):>7s} {str(r['tag_up']):>5s} {r['ce']:6.2f} {r['centroid_st']:8.2f} {r['onsets']:6.2f}  " + " ".join(f"{a}{b:+.3f}({c})" for a, b, c in r["top"][:3]))
(OUT / "report.txt").write_text("\n".join(out) + "\n"); json.dump(R, open(OUT / "report.json", "w"), indent=1)
print("\n".join(out))

# --- placebo-referenced read: every appended word, placebos included, shifts the render the same way (space up on base), so a word's own effect is word minus placebos
def deltas(m, w, field="mood"):
    if field == "mood":
        return np.array([L(np.array(S[f"{m}__{p}__{w}"]["mood"])) - L(np.array(S[f"{m}__{p}__plain"]["mood"])) for p in pids])
    if field == "prob":
        return np.array([np.array(S[f"{m}__{p}__{w}"]["mood"]) - np.array(S[f"{m}__{p}__plain"]["mood"]) for p in pids])
out2 = []; R2 = {}
for m in ("base", "goa"):
    PD = {w: deltas(m, w) for w in PLACEBO}; PP = {w: deltas(m, w, "prob") for w in PLACEBO}
    rows = {}
    for w in TEST + POS + PLACEBO:
        ref = [x for x in PLACEBO if x != w]
        D = deltas(m, w) - np.mean([PD[x] for x in ref], 0); n = len(D)
        proj = np.array([D[i] @ ((v := D[np.arange(n) != i].mean(0)) / (np.linalg.norm(v) + 1e-9)) for i in range(n)])
        ci = np.percentile([proj[rng.integers(0, n, n)].mean() for _ in range(2000)], [2.5, 97.5])
        P_ = deltas(m, w, "prob") - np.mean([PP[x] for x in ref], 0)
        t = P_.mean(0) / (P_.std(0, ddof=1) / np.sqrt(n) + 1e-9)
        top = [(C[i], round(float(P_.mean(0)[i]), 3), int((P_[:, i] > 0).sum())) for i in np.argsort(-np.abs(t))[:3]]
        tg = TAG.get(w)
        rows[w] = dict(cons=round(float(proj.mean()), 3), ci=[round(float(x), 3) for x in ci], tag=tg, dtag=None if not tg else round(float(P_[:, C.index(tg)].mean()), 4), up=None if not tg else int((P_[:, C.index(tg)] > 0).sum()), top=top)
    R2[m] = rows
    pmax = max(rows[w]["cons"] for w in PLACEBO)
    out2.append(f"\n{m} word minus placebos. placebo vs the other two {[rows[w]['cons'] for w in PLACEBO]}")
    for w in sorted(rows, key=lambda x: -rows[x]["cons"]):
        r = rows[w]
        out2.append(f"{w:14s} {r['cons']:6.3f} {str(r['ci']):>16s} {'CLEAR' if r['ci'][0] > 0 and r['cons'] > pmax else '':5s} {str(r['tag'])[:9]:>9s} {str(r['dtag']):>7s} {str(r['up']):>4s}  " + " ".join(f"{a}{b:+.3f}({c})" for a, b, c in r["top"]))
open(OUT / "report.txt", "a").write("\n".join(out2) + "\n"); json.dump(R2, open(OUT / "report_placebo_referenced.json", "w"), indent=1)
print("\n".join(out2))
