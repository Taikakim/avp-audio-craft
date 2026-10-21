#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-21)
"""Figures for the blog post "Muon and derivatives: a DIY survival guide" -> blog/assets/muon-survival-guide/*.png.

Every curve is read from a run's own logs (train.log, opt_groups.jsonl) or optimizer state; nothing is typed in except
the bf16 rounding probe (TRAINING.md F21, CPU probe) and the per-group step arithmetic, which are labelled as such.
Run (CPU only, needs torch + matplotlib):
  cd /tmp && /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python /home/kim/Projects/SAO/Misc/build_muon_guide_figures.py
"""
import json
import re
import sys
from pathlib import Path

# Misc/ holds our own filelock.py, which would shadow the pip package that unpickling the checkpoint pulls in
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent]

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path("/home/kim/Projects/SAO/blog/assets/muon-survival-guide")
UUID = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow")
B = UUID / "kuang_plan_B_20261021"
UNIT = UUID / "unit_matched_20261021"
P0 = Path("/run/media/kim/Mantu/latch_sweep/kuang_plan_P_20261017/P0_E05_anchor")

C_SPEC, C_SCAL, C_COL, C_ADAM = "#3b6ea8", "#c0504d", "#8a8a8a", "#d9a441"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 130})


def vals(log):
    return [float(v) for v in re.findall(r"val=([0-9.]+|nan)", Path(log).read_text())]


def groups(path):
    return [json.loads(line) for line in open(path)]


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / name)


def fig_routing():
    """Which optimizer handles which parameter, in one transformer block."""
    rows = [
        ("Input projection / embedding", "2-D", "AdamW (original rule)", C_ADAM, "ours: colnorm, or Muon if not named 'embed'"),
        ("Attention Q, K, V", "2-D, often fused [3d, d]", "Muon, Q, K, V separately", C_SPEC, "ours: DiT to_qkv split; LatCH attn.qkv not split"),
        ("Attention output projection", "2-D", "Muon", C_SPEC, ""),
        ("MLP up / down", "2-D", "Muon", C_SPEC, ""),
        ("AdaLN / modulation emitter", "2-D, fused [k*d, d]", "AdamW (scale-sensitive)", C_ADAM, "ours: DiT sign + split; LatCH adaLN_mod Muon, whole"),
        ("Biases, norm gains, DoRA magnitudes", "1-D", "AdamW", C_ADAM, "ours: sign step at full lr (old) / Adam (new)"),
        ("Output head", "2-D, tiny (256 -> 1)", "AdamW (original rule)", C_ADAM, "ours: sign step at lr/16 (old) / Adam (new)"),
    ]
    fig, ax = plt.subplots(figsize=(13, 4.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, len(rows) + 1)
    ax.axis("off")
    xs = [0.1, 3.5, 6.0, 9.0]
    for j, h in enumerate(["parameter", "shape", "recommended (Muon post)", "what our trainers did"]):
        ax.text(xs[j], len(rows) + 0.45, h, weight="bold", fontsize=9)
    for i, (name, shape, opt, col, ours) in enumerate(rows):
        y = len(rows) - i - 0.3
        ax.text(xs[0], y, name, fontsize=9, va="center")
        ax.text(xs[1], y, shape, fontsize=8, va="center", color="#444")
        ax.add_patch(FancyBboxPatch((xs[2] - 0.05, y - 0.32), 2.8, 0.64, boxstyle="round,pad=0.02", fc=col, ec="none", alpha=0.9))
        ax.text(xs[2] + 0.05, y, opt, fontsize=8.5, va="center", color="white", weight="bold")
        ax.text(xs[3], y, ours, fontsize=8, va="center", color="#444")
    save(fig, "routing.png")


def fig_steps():
    """Per-weight step size per group (arithmetic)."""
    labels = ["weight matrices\n(width 256)", "biases / gains", "256->1 output layer"]
    old = [1e-2 / 16, 1e-2, 1e-2 / 16]          # unscaled Muon + sign group, lr 1e-2
    ADAM = 0.3                                  # Adam update RMS ~0.2-0.4 x lr (Moonlight, 2502.16982, measured)
    new = [0.2 * 3e-3, ADAM * 3e-3, ADAM * 3e-3]  # rms0.2 + Adam scalars, lr 3e-3
    adamw = [ADAM * 3e-4] * 3                   # AdamW lr 3e-4
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for k, (v, c, lab) in enumerate([(adamw, "#999", "AdamW, lr 3e-4"), (old, C_SCAL, "Muon + sign step, lr 1e-2 (our old recipe)"),
                                     (new, C_SPEC, "Muon x0.2 RMS + Adam, lr 3e-3 (unit-matched)")]):
        ax.bar(x + (k - 1) * 0.27, v, 0.26, color=c, label=lab)
    ax.set_yscale("log")
    ax.set_xticks(x, labels)
    ax.set_ylabel("approx. change per weight per step")
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=1)
    ax.set_title("One learning rate, three step sizes (arithmetic; Adam taken as 0.3 x lr per weight)", fontsize=10)
    save(fig, "step_sizes.png")


def fig_b2_b3():
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    for run, ls in (("B2", "-"), ("B3", "--")):
        rows = groups(B / run / "opt_groups.jsonl")
        steps = [r["step"] for r in rows]
        for key, col, lab in (("g0_spectral", C_SPEC, "weight matrices"), ("g2_sign", C_SCAL, "biases / gains")):
            y = [r.get(f"comp/{key}/weight_rms", np.nan) for r in rows]
            axs[0].plot(steps, y, ls, color=col, label=f"{run} {lab}")
    axs[0].set_yscale("log")
    axs[0].set_xlabel("optimizer step")
    axs[0].set_ylabel("weight RMS of the group")
    axs[0].set_title("lr 3e-2: B2 caps the biases/gains at 2e-3, B3 does not", fontsize=9)
    axs[0].legend(frameon=False, fontsize=8)
    b0 = vals(P0 / "train.log") if (P0 / "train.log").exists() else []
    for run, col, lab in (("B0", "#999", "B0 lr 1e-2"), ("B1", "#6a9", "B1 lr 1e-2, biases 2e-3"),
                          ("B2", C_SPEC, "B2 lr 3e-2, biases 2e-3"), ("B3", C_SCAL, "B3 lr 3e-2, shared")):
        v = b0 if run == "B0" else vals(B / run / "train.log")
        if v:
            axs[1].plot(range(1, len(v) + 1), v, color=col, label=lab, marker=".")
    axs[1].set_xlabel("epoch")
    axs[1].set_ylabel("held-out loss")
    axs[1].set_ylim(0.17, 1.0)
    axs[1].set_yscale("log")
    axs[1].set_title("held-out loss (B3 goes NaN in epoch 13)", fontsize=9)
    axs[1].legend(frameon=False, fontsize=8)
    save(fig, "b2_b3.png")


def fig_air():
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    for run, col, lab in (("AIRS_O1_signcap", C_SCAL, "old recipe, lr 5e-2, biases capped (NaN)"),
                          ("AIR_U3", C_SPEC, "unit-matched, lr 3e-3"), ("AIR_U10", "#6a9", "unit-matched, lr 1e-2")):
        d = (B if run.startswith("AIRS") else UNIT) / run
        if not (d / "opt_groups.jsonl").exists():
            continue
        rows = [r for r in groups(d / "opt_groups.jsonl") if np.isfinite(r.get("comp/g0_spectral/weight_rms", np.nan))]
        axs[0].plot([r["step"] for r in rows], [r["comp/g0_spectral/weight_rms"] for r in rows], color=col, label=lab)
        v = vals(d / "train.log")
        axs[1].plot(range(1, len(v) + 1), v, color=col, marker=".", label=lab)
    axs[0].set_xlabel("optimizer step")
    axs[0].set_ylabel("weight RMS, weight matrices")
    axs[0].set_title("air-band head: weight size of the matrices", fontsize=9)
    axs[0].legend(frameon=False, fontsize=8)
    axs[1].set_xlabel("epoch")
    axs[1].set_ylabel("held-out loss")
    axs[1].set_yscale("log")
    axs[1].set_title("held-out loss", fontsize=9)
    save(fig, "air_head.png")


def fig_bf16():
    lrs = ["3e-4", "1e-3", "3e-3"]
    kept = [29, 64, 92]
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    ax.bar(lrs, kept, color=C_SPEC)
    for i, k in enumerate(kept):
        ax.text(i, k + 2, f"{k}%", ha="center", fontsize=9)
    ax.set_ylim(0, 110)
    ax.set_xlabel("learning rate")
    ax.set_ylabel("weight change kept (% of fp32)")
    ax.set_title("bf16 parameter storage rounds small steps away\n(CPU probe, one 768x768 matrix, 600 steps)", fontsize=9)
    save(fig, "bf16_rounding.png")


def fig_newton_schulz():
    import torch
    ck = torch.load(P0 / "latch_sa3_onset_per_beat_ts_ep2.pt", map_location="cpu", weights_only=False)
    st, pg = ck["optimizer_state"]["state"], ck["optimizer_state"]["param_groups"][0]
    name = "blocks.3.mlp.0.weight"
    idx = pg["param_names"].index(name)
    M = st[pg["params"][idx]]["momentum"].float()
    s_before = torch.linalg.svdvals(M)
    X = M / (M.norm() + 1e-7)
    tall = X.shape[0] > X.shape[1]
    if tall:
        X = X.T
    a, b, c = 3.4445, -4.7750, 2.0315
    for _ in range(5):
        A = X @ X.T
        X = a * X + (b * A + c * A @ A) @ X
    s_after = torch.linalg.svdvals(X.T if tall else X)
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
    k = np.arange(1, len(s_before) + 1)
    axs[0].semilogy(k, (s_before / s_before[0]).numpy(), color=C_SCAL)
    axs[0].set_title(f"momentum of one MLP matrix ({tuple(M.shape)}), epoch 2:\nsingular values / largest", fontsize=9)
    axs[0].set_xlabel("direction rank")
    axs[1].plot(k, s_after.numpy(), color=C_SPEC)
    axs[1].set_ylim(0, 1.5)
    axs[0].axhline(1e-3, color="#999", lw=0.8, ls=":")
    axs[1].axhspan(0.7, 1.3, color="#ddd", zorder=0)
    axs[1].set_title("after 5 Newton-Schulz steps (plain Muon, fp32): strong directions\npulled into ~0.7-1.3 (grey band), the weakest stay small", fontsize=9)
    axs[1].set_xlabel("direction rank")
    save(fig, "newton_schulz.png")


if __name__ == "__main__":
    fig_routing()
    fig_steps()
    fig_b2_b3()
    fig_air()
    fig_bf16()
    fig_newton_schulz()
