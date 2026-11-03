#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-11-04)
"""Figures for the blog post "Melody in Stable Audio 3: a field guide" -> blog/assets/melody-field-guide/*.png.

Every value is read from a run's own report files; nothing is typed in. Measured, not heard.
Run (CPU only): cd /tmp && /home/kim/Projects/SAO/.venv/bin/python /home/kim/Projects/SAO/Misc/build_melody_guide_figures.py
"""
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path("/home/kim/Projects/SAO/blog/assets/melody-field-guide")
CR = Path("/home/kim/evals_aac/control_runs")
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, NEUTRAL = "#2a78d6", "#eb6834", "#b4b2aa"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "savefig.dpi": 160})


def gain_ladder():
    r = json.load(open(CR / "chroma_e13_20261028/report.json"))["ladder"]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for head, name, c in (("C3_ep10_ema1", "Retrained head", BLUE), ("prod", "Production head", ORANGE)):
        rows = sorted((x for x in r if x["head"] == head and x["gain"] <= 8192), key=lambda x: x["gain"])
        g, y = [x["gain"] for x in rows], [x["mid_fcos"] for x in rows]
        ax.plot(g, y, color=c, lw=2, marker="o", ms=7, mec=SURF, mew=2, label=name)
        ax.annotate(f"{name} {y[-1]:+.3f}", (g[-1], y[-1]), xytext=(-6, 9), textcoords="offset points", ha="right", color=INK, fontsize=10)
    ax.set_xscale("log", base=2); ax.set_xticks([512, 1024, 2048, 4096, 8192]); ax.set_xticklabels(["512", "1024", "2048", "4096", "8192"]); ax.minorticks_off()
    ax.set_ylim(0, .45); ax.grid(axis="y", color=GRID, lw=.8); ax.set_axisbelow(True); ax.tick_params(length=0)
    ax.set_xlabel("Guidance gain"); ax.set_ylabel("Change in mid-band chroma cosine")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(OUT / "gain_ladder.png"); plt.close(fig)


def speed_limit():
    r = json.load(open(CR / "d16_contour_ceiling_20261103/report.json"))
    r = sorted(r, key=lambda x: -x["period"])
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    x = np.arange(len(r)); y = np.array([p["follow"] for p in r])
    lo = y - np.array([p["ci"][0] for p in r]); hi = np.array([p["ci"][1] for p in r]) - y
    ax.axhline(0, color=INK2, lw=1)
    ax.errorbar(x, y, yerr=[lo, hi], fmt="o", ms=8, color=BLUE, mec=SURF, mew=2, elinewidth=2, capsize=0)
    ax.annotate(f"{y[0]:+.3f}", (0, y[0]), xytext=(10, 0), textcoords="offset points", va="center", color=INK, fontsize=10)
    ax.set_xticks(x); ax.set_xticklabels([f"{p['period']:g} s" for p in r]); ax.set_xlim(-.5, len(r) - .5)
    ax.set_ylim(-.3, .35); ax.grid(axis="y", color=GRID, lw=.8); ax.set_axisbelow(True); ax.tick_params(length=0)
    ax.set_xlabel("Period of the target pitch wave"); ax.set_ylabel("Follow score (chance 0, maximum 2)")
    fig.tight_layout(); fig.savefig(OUT / "speed_limit.png"); plt.close(fig)


def pct(s):
    return float(s.rstrip("%"))


def cfg_fix():
    txt = (CR / "pianoroll_checks_goa_t256_20261103/report.txt").read_text()
    get = lambda k: re.search(rf"^{k}: n \d+; sounds ([\d.]+)%, top [\d.]+%; no stream ([\d.]+)%", txt, re.M).groups()
    ref = (CR / "pianoroll_newmelody_goa_t256_step2688_20261103/report.txt").read_text()
    fed = 100 * float(re.search(r"the fed pitch sounds anywhere: fed ([\d.]+)", ref).group(1))
    both, ns = get("both"); seed2, _ = get("seed2"); ema, _ = get("ema"); s2, _ = get("s2")
    rows = [("No stream", float(ns), NEUTRAL), ("EMA weights", float(ema), NEUTRAL), ("Notes in both CFG branches", float(both), ORANGE), ("Zeros in the unconditional branch", fed, BLUE),
            ("Same, another render seed", float(seed2), BLUE), ("Same, second training seed", float(s2), BLUE)][::-1]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    y = np.arange(len(rows))
    ax.barh(y, [r[1] for r in rows], color=[r[2] for r in rows], height=.62)
    for i, r in enumerate(rows):
        ax.text(r[1] + 1.2, i, f"{r[1]:.1f}%" if r[1] < 10 else f"{r[1]:.0f}%", va="center", color=INK, fontsize=10)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], color=INK); ax.set_xlim(0, 100); ax.tick_params(length=0)
    ax.spines["left"].set_visible(False); ax.grid(axis="x", color=GRID, lw=.8); ax.set_axisbelow(True)
    ax.set_xlabel("Frames where the fed pitch sounds, invented melodies, cfg 7")
    fig.tight_layout(); fig.savefig(OUT / "cfg_fix.png"); plt.close(fig)


def strength_grid():
    txt = (CR / "pianoroll_strength_goa_t256_step2688_20261103/report.txt").read_text()
    cfgs, strengths, M, G = [], ["x0.5", "x1", "x1.5", "x2"], {}, {}
    for block in re.finditer(r"^cfg (\d+) .*?(?=^cfg |\Z)", txt, re.M | re.S):
        c = int(block.group(1)); cfgs.append(c)
        for s, a, f in re.findall(r"(x[\d.]+): (\d+)% / \d+% / \d+%; (\d+)/12", block.group(0)):
            M[c, s], G[c, s] = int(a), int(f)
    A = np.array([[M[c, s] for s in strengths] for c in cfgs], float)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    from matplotlib.colors import LinearSegmentedColormap
    cm = LinearSegmentedColormap.from_list("b", ["#e8f0fb", "#7fb0ea", "#2a78d6", "#134a8f"])
    ax.imshow(A, cmap=cm, vmin=0, vmax=100, aspect="auto")
    for i, c in enumerate(cfgs):
        for j, s in enumerate(strengths):
            ax.text(j, i, f"{M[c, s]}%\ngate {G[c, s]}/12", ha="center", va="center", fontsize=9.5, color="white" if A[i, j] >= 60 else INK)
    ax.set_xticks(range(4)); ax.set_xticklabels(strengths); ax.set_yticks(range(len(cfgs))); ax.set_yticklabels([f"cfg {c}" for c in cfgs]); ax.tick_params(length=0)
    for k in ax.spines.values():
        k.set_visible(False)
    ax.set_xticks(np.arange(-.5, 4), minor=True); ax.set_yticks(np.arange(-.5, len(cfgs)), minor=True); ax.grid(which="minor", color=SURF, lw=2); ax.tick_params(which="minor", length=0)
    ax.set_xlabel("Note strength")
    fig.tight_layout(); fig.savefig(OUT / "strength_grid.png"); plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    gain_ladder(); speed_limit(); cfg_fix(); strength_grid()
    print(sorted(p.name for p in OUT.iterdir()))
