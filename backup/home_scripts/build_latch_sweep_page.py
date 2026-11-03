#!/usr/bin/env python3
"""Generate riffer-evals/latch_sweep.html — an SA3 LatCH-head steering sweep page.

Run in the mir venv:

    /home/kim/Projects/mir/mir/bin/python /home/kim/build_latch_sweep_page.py

Inputs (produced by the measure+analyze pipeline in /run/media/kim/Mantu/latch_sweep):
  * sweep_manifest.json   — per clip generation params incl. raw_target /
                            std_target_first / gain / window  (target distribution).
  * sweep_results.json    — per clip {head, level, pid, ce, pq, pc, cu,
                            mert_mid[1024], mert_upper[1024], measured(float|null)}.
  * analysis_summary.json — per head steering magnitude (MERT Δ low↔high),
                            Δ-vs-baseline, CE-by-level, feature-follow, dead flag,
                            ranking.  If absent it is recomputed inline from results.

Outputs:
  * /home/kim/riffer-evals/latch_sweep.html  — leaderboard + per-head level×prompt
    grids with the same-playhead player (copied from onset_eval.html).
  * /home/kim/riffer-evals/clips_latch_aac/  — a representative AAC subset
    (low+high @ p0 per head, hpcp ephrygdom @ p0, + the 3 baselines), 8-core ffmpeg.

The page references the AAC clip when it exists (online), else the local wav
(works when the html is opened as a file:// for the full 123-clip set).

Idempotent / re-runnable: AAC encodes are skipped when present; the html is rebuilt.
The generator runs cleanly only once sweep_results.json exists; it tolerates a
still-running measure job (rows trickle in) and a missing analysis_summary.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

SWEEP_DIR = Path("/run/media/kim/Mantu/latch_sweep")


def _pick(env: str, g512_name: str, g128_name: str) -> Path:
    """Env override wins; else prefer the gain-512 file when it exists, else gain-128."""
    if os.environ.get(env):
        return Path(os.environ[env])
    g512 = SWEEP_DIR / g512_name
    return g512 if g512.exists() else SWEEP_DIR / g128_name


MANIFEST = _pick("SWEEP_MANIFEST", "sweep_manifest_g512.json", "sweep_manifest.json")
RESULTS = _pick("SWEEP_RESULTS", "sweep_results_g512.json", "sweep_results.json")
SUMMARY = _pick("SWEEP_SUMMARY", "analysis_summary_g512.json", "analysis_summary.json")
# clips dir tracks whichever gain set RESULTS points at (suffix derived from its stem),
# unless explicitly overridden with SWEEP_CLIPS.
if os.environ.get("SWEEP_CLIPS"):
    CLIPS_DIR = Path(os.environ["SWEEP_CLIPS"])
else:
    _suffix = RESULTS.stem.replace("sweep_results", "")  # "" or "_g512"
    _guess = SWEEP_DIR / f"clips{_suffix}"
    CLIPS_DIR = _guess if _guess.exists() else (SWEEP_DIR / "clips")

# Gain-response summary table (perceptual + measured + quality vs guidance gain).
# Written here if absent, then read back so the page renders from the file.
GAIN_RESPONSE = SWEEP_DIR / "gain_response.json"

EVALS_DIR = Path("/home/kim/riffer-evals")
HTML_OUT = EVALS_DIR / "latch_sweep.html"
AAC_DIR = EVALS_DIR / "clips_latch_aac"

DEAD_THRESHOLD = 0.02
LEVEL_ORDER = ["low", "mid", "high"]
PROMPTS = {
    "p0": "aggressive upbeat goa trance",
    "p1": "energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine",
    "p2": "psytrance, 140 bpm",
}
PID_ORDER = ["p0", "p1", "p2"]
HPCP_NOTE = "E Phrygian dominant chroma direction (cosine-steered)"

# ---- EMA reversal experiment (spectral_skewness) — playable grid -------------
# 30 clips: 5 configs × {low,high} × {p0,p1,p2}, same prompts/gain as the page.
EMA_CLIPS_DIR = Path(os.environ.get("SWEEP_EMA_CLIPS",
                                    str(SWEEP_DIR / "skew_ema_eval_clips")))
EMA_ROWS = Path(os.environ.get("SWEEP_EMA_ROWS",
                               str(SWEEP_DIR / "skew_ema_clip_rows.json")))
EMA_CONFIGS = ["original", "ema20", "ema40", "ema80", "ema_ga2"]
EMA_LEVELS = ["low", "high"]

# --------------------------------------------------------------------------- #
# Gain-response finding (perceptual Δ + measured spread + CE quality vs gain)   #
#   mert_delta = MERTmid Δ = perceptual steering magnitude                      #
#   low/high   = measured target-feature spread (null where no scalar, e.g.     #
#                the activation heads)                                          #
#   ce         = Audiobox content-enjoyment (quality holds = steering is clean) #
# --------------------------------------------------------------------------- #
GAIN_RESPONSE_NARRATIVE = (
    "Gain 128 sat in the dead zone — the heads moved their target feature <1 dB "
    "with no audible change. At gain 512 the energy/RMS heads steer hard and "
    "cleanly (CE holds); spectral heads steer moderately; the activation heads "
    "(beat/downbeat/onset) do not respond to LatCH guidance at any weight. "
    "Operating gain for SA3-medium energy heads ≈ 512, not the 48–96 from "
    "the small-model regime."
)
GAIN_RESPONSE_GAINS = [128, 256, 512, 1024]
# feature -> per-gain (mert_delta, feature_low, feature_high, ce); None low/high = no scalar
_GR_RAW = {
    "rms_energy_bass": [
        (0.0008, -19.4, -18.6, 5.40),
        (0.0039, -19.9, -18.3, 5.37),
        (0.0192, -21.4, -17.9, 5.26),
        (0.0339, -24.9, -16.3, 5.08),
    ],
    "rms_energy_mid": [
        (0.0014, -31.6, -30.7, 5.46),
        (0.0048, -32.3, -30.4, 5.41),
        (0.0182, -34.2, -29.8, 5.43),
        (0.0656, -39.6, -28.4, 5.32),
    ],
    "spectral_flatness": [
        (0.0014, 0.3, 0.4, 5.45),
        (0.0028, 0.2, 0.4, 5.47),
        (0.0058, 0.2, 0.5, 5.40),
        (0.0085, 0.1, 0.5, 5.22),
    ],
    "beat_activation": [
        (0.0000, None, None, 5.52),
        (0.0001, None, None, 5.53),
        (0.0015, None, None, 5.40),
        (0.0044, None, None, 5.04),
    ],
}


def build_gain_response() -> dict:
    """Assemble the gain-response object (narrative + per-feature per-gain points)."""
    rows = []
    for feat, pts in _GR_RAW.items():
        points = []
        for gain, (delta, lo, hi, ce) in zip(GAIN_RESPONSE_GAINS, pts):
            points.append({
                "gain": gain, "mert_delta": delta,
                "low": lo, "high": hi, "ce": ce,
            })
        rows.append({"feature": feat, "points": points})
    return {
        "narrative": GAIN_RESPONSE_NARRATIVE,
        "gains": GAIN_RESPONSE_GAINS,
        "rows": rows,
    }


def load_gain_response() -> dict:
    """Write gain_response.json if absent, then read it back (page renders from file)."""
    if not GAIN_RESPONSE.exists():
        GAIN_RESPONSE.write_text(json.dumps(build_gain_response(), indent=2))
        print(f"[info] wrote {GAIN_RESPONSE}")
    return json.load(open(GAIN_RESPONSE))


# --------------------------------------------------------------------------- #
# inline re-implementation of analyze_sweep.py (used if summary is absent)     #
# --------------------------------------------------------------------------- #
def cosine(a, b) -> float:
    import numpy as np
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def compute_summary(rows: list[dict]) -> dict:
    import numpy as np
    idx: dict = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        if r.get("mert_upper") is None and r.get("measured") is None and r.get("ce") is None:
            continue
        idx[r["head"]][r["level"]][r["pid"]] = r

    base_upper = {}
    for pid, r in idx.get("baseline", {}).get("none", {}).items():
        if r.get("mert_upper") is not None:
            base_upper[pid] = r["mert_upper"]

    heads = [h for h in idx if h != "baseline"]
    per_head = {}
    for head in sorted(heads):
        levels = idx[head]
        lowhigh = []
        if "low" in levels and "high" in levels:
            for pid in set(levels["low"]) & set(levels["high"]):
                lo = levels["low"][pid].get("mert_upper")
                hi = levels["high"][pid].get("mert_upper")
                if lo is not None and hi is not None:
                    lowhigh.append(1.0 - cosine(lo, hi))
        mert_delta_lowhigh = float(np.mean(lowhigh)) if lowhigh else None

        vs_base = {}
        for level, pids in levels.items():
            deltas = []
            for pid, r in pids.items():
                up = r.get("mert_upper")
                bu = base_upper.get(pid)
                if up is not None and bu is not None:
                    deltas.append(1.0 - cosine(up, bu))
            if deltas:
                vs_base[level] = float(np.mean(deltas))
        vs_base_max = max(vs_base.values()) if vs_base else None

        ce_by_level = {}
        for level, pids in levels.items():
            ces = [r["ce"] for r in pids.values() if r.get("ce") is not None]
            if ces:
                ce_by_level[level] = float(np.mean(ces))

        follow = None
        meas_by_level = {}
        for level, pids in levels.items():
            ms = [r["measured"] for r in pids.values() if r.get("measured") is not None]
            if ms:
                meas_by_level[level] = float(np.mean(ms))
        if all(lv in meas_by_level for lv in LEVEL_ORDER):
            lo, mid, hi = (meas_by_level[lv] for lv in LEVEL_ORDER)
            follow = {
                "low": lo, "mid": mid, "high": hi,
                "monotonic_increasing": bool(lo < mid < hi),
                "spread_high_minus_low": float(hi - lo),
            }

        magnitude = mert_delta_lowhigh if mert_delta_lowhigh is not None else vs_base_max
        dead = (mert_delta_lowhigh is not None and mert_delta_lowhigh < DEAD_THRESHOLD)
        per_head[head] = {
            "mert_delta_lowhigh": mert_delta_lowhigh,
            "mert_delta_vs_baseline": vs_base,
            "mert_delta_vs_baseline_max": vs_base_max,
            "ce_by_level": ce_by_level,
            "follow": follow,
            "magnitude": magnitude,
            "dead": dead,
        }
    ranked = sorted(per_head.items(),
                    key=lambda kv: (kv[1]["magnitude"] is None, -(kv[1]["magnitude"] or 0.0)))
    return {
        "dead_threshold": DEAD_THRESHOLD,
        "n_rows": len(rows),
        "ranking": [h for h, _ in ranked],
        "dead_heads": sorted(h for h, d in per_head.items() if d["dead"]),
        "per_head": per_head,
    }


# --------------------------------------------------------------------------- #
# target distribution from the manifest                                        #
# --------------------------------------------------------------------------- #
def target_dists(manifest: list[dict]) -> dict:
    """head -> {mean, sigma, gain, raw_by_level{level:raw}, std_by_level, note}.

    Derived from raw_target = mean + std_target_first * sigma. With low/high levels
    sigma = (raw_hi - raw_lo)/(std_hi - std_lo); mean = raw at the level whose std
    is closest to 0 (the 'mid' target).  hpcp has no scalar raw_target.
    """
    by_head: dict = defaultdict(dict)
    gain_by_head: dict = {}
    for e in manifest:
        head = e.get("head") or e.get("feature")
        lvl = e.get("level")
        by_head[head][lvl] = (e.get("std_target_first"), e.get("raw_target"))
        if e.get("gain"):
            gain_by_head[head] = e.get("gain")

    out = {}
    for head, lv in by_head.items():
        if head == "baseline":
            continue
        raw_by_level = {k: v[1] for k, v in lv.items()}
        std_by_level = {k: v[0] for k, v in lv.items()}
        mean = sigma = None
        # sigma from any two distinct-std levels with a raw value
        pts = [(s, r) for (s, r) in lv.values() if s is not None and r is not None]
        if len(pts) >= 2:
            pts.sort()
            (s0, r0), (s1, r1) = pts[0], pts[-1]
            if abs(s1 - s0) > 1e-9:
                sigma = (r1 - r0) / (s1 - s0)
            # mean = raw at std closest to 0
            s_zero, r_zero = min(pts, key=lambda p: abs(p[0]))
            if sigma is not None:
                mean = r_zero - s_zero * sigma
        note = ""
        if head == "hpcp":
            note = HPCP_NOTE
        elif head == "spectral_kurtosis":
            note = "raw targets hand-clamped to 3 / 15 / 60 (heavy-tailed dist; mean±2σ is indicative)"
        out[head] = {
            "mean": mean, "sigma": sigma,
            "gain": gain_by_head.get(head),
            "raw_by_level": raw_by_level,
            "std_by_level": std_by_level,
            "note": note,
        }
    return out


def verdict(head: str, d: dict, td: dict | None) -> str:
    """Human steering verdict from the analysis row."""
    if d is None:
        return "not yet measured"
    if d.get("dead"):
        return (f"DEAD — barely moved (Δlow→high="
                f"{_fmt(d.get('mert_delta_lowhigh'))} < {DEAD_THRESHOLD}); "
                f"needs higher guidance gain or is structurally unsteerable at gain "
                f"{int(td['gain']) if td and td.get('gain') else '?'}.")
    mag = d.get("magnitude")
    lh = d.get("mert_delta_lowhigh")
    parts = []
    if lh is not None:
        strength = "strong" if lh >= 0.06 else ("moderate" if lh >= 0.03 else "weak")
        parts.append(f"{strength} steering (MERT Δlow→high={_fmt(lh)})")
    elif mag is not None:
        parts.append(f"moved {_fmt(mag)} off baseline (no low/high pair)")
    f = d.get("follow")
    if f is not None:
        mono = "monotonic low<mid<high" if f["monotonic_increasing"] else "NON-monotonic"
        parts.append(f"measured feature {mono}, spread {f['spread_high_minus_low']:+.2f}")
    elif head == "hpcp":
        parts.append("chroma direction (no scalar follow metric)")
    else:
        parts.append("no cheap full-mix scalar — judged by MERT + Audiobox CE")
    return "; ".join(parts) + "."


def _fmt(x, nd=4):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else "·"


# --------------------------------------------------------------------------- #
# AAC subset                                                                    #
# --------------------------------------------------------------------------- #
def subset_clips(heads: list[str]) -> list[str]:
    """Representative subset: low+high @ p0 per scalar head, hpcp ephrygdom @ p0,
    + the 3 baselines.  Returns clip *stems* (no extension)."""
    want = []
    for head in heads:
        if head == "baseline":
            continue
        if head == "hpcp":
            want.append(f"hpcp_ephrygdom_p0")
        else:
            want.append(f"{head}_low_p0")
            want.append(f"{head}_high_p0")
    want += ["baseline_none_p0", "baseline_none_p1", "baseline_none_p2"]
    # keep only those that actually have a source wav
    return [s for s in want if (CLIPS_DIR / f"{s}.wav").exists()]


def _encode(args) -> tuple[str, bool, str]:
    stem, src, dst = args
    if Path(dst).exists():
        return stem, True, "exists"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             "-c:a", "aac", "-b:a", "96k", dst],
            check=True,
        )
        return stem, True, "encoded"
    except Exception as exc:
        return stem, False, str(exc)


def encode_subset(stems: list[str]) -> dict[str, str]:
    """Encode subset to AAC in parallel. Returns stem -> aac relative path (online)."""
    AAC_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    for s in stems:
        src = str(CLIPS_DIR / f"{s}.wav")
        dst = str(AAC_DIR / f"{s}.m4a")
        jobs.append((s, src, dst))
    online = {}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for stem, ok, msg in ex.map(_encode, jobs):
            if ok:
                online[stem] = f"clips_latch_aac/{stem}.m4a"
            else:
                print(f"[warn] encode failed {stem}: {msg}", flush=True)
    return online


def encode_ema(stems: list[str]) -> dict[str, str]:
    """AAC-encode the EMA clips (from EMA_CLIPS_DIR) into AAC_DIR, skip-if-present.
    Same naming/encoder as the other sets. Returns stem -> aac relative path."""
    AAC_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    for s in stems:
        src = str(EMA_CLIPS_DIR / f"{s}.wav")
        if not Path(src).exists():
            print(f"[warn] ema source missing: {src}", flush=True)
            continue
        dst = str(AAC_DIR / f"{s}.m4a")
        jobs.append((s, src, dst))
    online = {}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for stem, ok, msg in ex.map(_encode, jobs):
            if ok:
                online[stem] = f"clips_latch_aac/{stem}.m4a"
            else:
                print(f"[warn] ema encode failed {stem}: {msg}", flush=True)
    return online


def build_ema(online_ema: dict[str, str]) -> dict | None:
    """Assemble the playable EMA grid (5 configs × {low,high} × 3 prompts).

    Cell value = measured spectral_skewness; colour scales across the set; the
    clip ref is the online AAC when encoded, else a file:// local-wav fallback.
    """
    if not EMA_ROWS.exists():
        print(f"[info] {EMA_ROWS} absent — skipping EMA playable grid")
        return None
    rows = json.load(open(EMA_ROWS))
    idx = {(r["config"], r["level"], r["pid"]): r for r in rows}
    measured = [r["measured"] for r in rows if r.get("measured") is not None]
    mmin = min(measured) if measured else None
    mmax = max(measured) if measured else None
    grid = []
    for cfg in EMA_CONFIGS:
        for lv in EMA_LEVELS:
            cells = []
            for pid in PID_ORDER:
                r = idx.get((cfg, lv, pid))
                stem = f"{cfg}_{lv}_{pid}"
                f = online_ema.get(stem)
                if f is None:
                    wav = EMA_CLIPS_DIR / f"{stem}.wav"
                    f = os.path.relpath(wav, EVALS_DIR) if wav.exists() else None
                cells.append({
                    "pid": pid,
                    "measured": (r or {}).get("measured"),
                    "ce": (r or {}).get("ce"),
                    "f": f,
                })
            grid.append({"config": cfg, "level": lv, "cells": cells})
    return {
        "configs": EMA_CONFIGS, "levels": EMA_LEVELS, "pids": PID_ORDER,
        "grid": grid, "mmin": mmin, "mmax": mmax,
    }


# --------------------------------------------------------------------------- #
# build the page data                                                          #
# --------------------------------------------------------------------------- #
def clip_ref(stem: str, online: dict[str, str]) -> str | None:
    """Served AAC path if this stem was encoded, else None (local-only, not linked).

    Never fall back to a filesystem path: CLIPS_DIR lives on the local drive
    (/run/media/kim/Mantu/...), and this generator builds the page that gets served
    publicly — a raw path there is a leak AND a broken link once served (caught
    2026-07-04, WINTERMUTE). The page already has a "local only" note for clips
    outside the online AAC subset; None is what that note is for."""
    return online.get(stem)


def build_data(manifest, rows, summary, online, gain_response, ema=None) -> dict:
    td = target_dists(manifest)
    per_head = summary["per_head"]
    ranking = summary["ranking"]

    # index measured + ce per clip
    rowidx = {}
    for r in rows:
        rowidx[(r["head"], r["level"], r["pid"])] = r

    # baseline reference row
    baselines = []
    for pid in PID_ORDER:
        r = rowidx.get(("baseline", "none", pid))
        stem = f"baseline_none_{pid}"
        baselines.append({
            "pid": pid, "prompt": PROMPTS[pid],
            "ce": (r or {}).get("ce"),
            "f": clip_ref(stem, online),
        })

    # leaderboard rows (ranked)
    board = []
    for head in ranking:
        d = per_head[head]
        ce = d.get("ce_by_level", {})
        f = d.get("follow")
        board.append({
            "head": head,
            "magnitude": d.get("magnitude"),
            "lowhigh": d.get("mert_delta_lowhigh"),
            "vsbase": d.get("mert_delta_vs_baseline_max"),
            "ce_low": ce.get("low"), "ce_mid": ce.get("mid"), "ce_high": ce.get("high"),
            "follow": (None if f is None else
                       {"mono": f["monotonic_increasing"], "spread": f["spread_high_minus_low"]}),
            "dead": d.get("dead", False),
        })

    # per-head sections (levels x prompts grids)
    sections = []
    for head in ranking:
        d = per_head[head]
        t = td.get(head, {})
        # which levels exist for this head?
        levels = sorted({lv for (h, lv, p) in rowidx if h == head},
                        key=lambda x: (LEVEL_ORDER.index(x) if x in LEVEL_ORDER else 99))
        grid = []  # one dict per (level)
        measured_vals = [rowidx[k].get("measured") for k in rowidx
                         if k[0] == head and rowidx[k].get("measured") is not None]
        mmin = min(measured_vals) if measured_vals else None
        mmax = max(measured_vals) if measured_vals else None
        for lv in levels:
            cells = []
            for pid in PID_ORDER:
                r = rowidx.get((head, lv, pid))
                stem = f"{head}_{lv}_{pid}"
                cells.append({
                    "pid": pid,
                    "measured": (r or {}).get("measured"),
                    "ce": (r or {}).get("ce"),
                    "f": clip_ref(stem, online),
                })
            grid.append({"level": lv, "cells": cells,
                         "raw": t.get("raw_by_level", {}).get(lv),
                         "std": t.get("std_by_level", {}).get(lv)})
        sections.append({
            "head": head,
            "mean": t.get("mean"), "sigma": t.get("sigma"),
            "gain": t.get("gain"), "note": t.get("note", ""),
            "verdict": verdict(head, d, t),
            "dead": d.get("dead", False),
            "magnitude": d.get("magnitude"),
            "grid": grid,
            "mmin": mmin, "mmax": mmax,
        })

    # representative gain for the header (most common non-null gain across heads)
    gains = [t.get("gain") for t in td.values() if t.get("gain")]
    gain_label = None
    if gains:
        gain_label = int(max(set(gains), key=gains.count))

    return {
        "prompts": PROMPTS,
        "pid_order": PID_ORDER,
        "gain_label": gain_label,
        "n_rows": summary.get("n_rows"),
        "n_clips_total": len(list(CLIPS_DIR.glob("*.wav"))),
        "n_online": len(online),
        "dead_threshold": DEAD_THRESHOLD,
        "gain_response": gain_response,
        "ema": ema,
        "baselines": baselines,
        "board": board,
        "sections": sections,
    }


# --------------------------------------------------------------------------- #
# HTML                                                                          #
# --------------------------------------------------------------------------- #
HTML_TMPL = r"""<!doctype html><html><head><meta charset=utf-8>
<title>LatCH head sweep — SA3 steering</title><style>
body{font:12px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#hdr{position:sticky;top:0;z-index:9;background:#16181c}
#bar{padding:8px 12px;border-bottom:1px solid #2a2a30}
#wrap{padding:12px;max-width:1320px}
h1{font-size:16px;color:#9cf;margin:10px 0 2px}
h2{font-size:14px;color:#9cf;margin:20px 0 2px;border-top:1px solid #26262c;padding-top:10px}
.note{color:#9aa;font-size:11px;margin:4px 0}
.legend{color:#8aa;font-size:11px;margin:4px 0 10px}
table{border-collapse:collapse;font-size:11px;margin:4px 0}
td,th{border:1px solid #26262c;padding:3px 7px;text-align:center}
th{background:#1c1c22;color:#aaa}
td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:1px solid #7cf}
.play{outline:2px solid #5d5 !important}.no{color:#555;cursor:default}
.dead{color:#f88;font-weight:bold}.ok{color:#7d7}
.on{color:#5d9}.off{color:#666}.muted{color:#666}a{color:#7cf}
.verdict{color:#cde;font-size:12px;margin:3px 0}
.tdist{color:#9aa;font-size:11px;margin:2px 0}
.lead td{cursor:default}.lead .c{cursor:pointer}
.barhd{font-size:13px;color:#9ec;margin:2px 0}
.gr{margin:12px 0 6px;padding:10px 12px;background:#15171c;border:1px solid #2a4a3a;border-radius:5px}
.grhd{font-size:15px;color:#7ed;font-weight:bold;margin:0 0 4px}
.grnarr{color:#cde;font-size:12px;line-height:1.5;margin:4px 0 10px;max-width:1000px}
.grtab td,.grtab th{vertical-align:top}
.grtab td:first-child{font-weight:bold;color:#bcd}
.grsub{color:#9aa;font-size:10px;margin-top:2px;line-height:1.3}
</style></head><body>
<div id=hdr><div id=bar>&#9654; <b id=np>click a cell to play</b>
 <span id=pos class=muted></span> &nbsp;·&nbsp;
 <span class=muted>switching cells keeps the playhead; re-click stops ·
 <span class=on>green border = online AAC</span></span></div></div>
<div id=wrap></div>
<script>const D=__DATA__;
const au=new Audio(); let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function cell(id,f,lbl){
  if(!f){return;}
  if(cur===id){au.pause();cur=null;mark();document.getElementById('np').textContent='stopped';return;}
  const pos=(cur!==null&&!au.paused)?au.currentTime:0;
  cur=id;mark();document.getElementById('np').textContent='▶ '+lbl;
  au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
  if(au.readyState>=1)go(); else au.addEventListener('loadedmetadata',go,{once:true});
}
function nf(x,nd){return (x==null)?'·':(+x).toFixed(nd==null?2:nd);}
// CE colour: 4..8 -> red..green
function ceCol(m){if(m==null)return'#1a1a1f';const t=Math.max(0,Math.min(1,(m-4)/4));return`hsl(${Math.round(t*130)},45%,22%)`;}
// magnitude colour: 0..maxMag -> grey..green
let MAXMAG=0.001;D.board.forEach(b=>{if(b.magnitude!=null)MAXMAG=Math.max(MAXMAG,b.magnitude);});
function magCol(m){if(m==null)return'#1a1a1f';const t=Math.max(0,Math.min(1,m/MAXMAG));return`hsl(${Math.round(t*130)},50%,${14+Math.round(t*18)}%)`;}
// measured colour within a head's [mmin,mmax]
function measCol(v,mn,mx){if(v==null||mn==null||mx==null||mx<=mn)return null;const t=Math.max(0,Math.min(1,(v-mn)/(mx-mn)));return`hsl(${Math.round(t*230+10)},45%,22%)`;}

let safe=s=>(''+s).replace(/[^A-Za-z0-9_]/g,'');
let h='';
h+=`<h1>SA3 LatCH head sweep — 14 heads × target extremes × 3 prompts</h1>`;
h+=`<div class=note>Full ${D.n_clips_total}-clip set is <b>local only</b>; this online page carries a representative AAC subset (${D.n_online} clips). Measured rows so far: ${D.n_rows}. Guidance gain ${D.gain_label==null?'?':D.gain_label}, 30 steps, cfg 7.</div>`;
h+=`<div class=legend>Prompts: `+D.pid_order.map(p=>`<b>${p}</b>=${D.prompts[p]}`).join(' &nbsp;·&nbsp; ')+`</div>`;

// ---- gain-response finding (prominent, near top) ----
if(D.gain_response){
  const GR=D.gain_response;
  h+=`<div class=gr>`;
  h+=`<div class=grhd>Gain response — how steering scales with guidance weight</div>`;
  h+=`<div class=grnarr>${GR.narrative}</div>`;
  h+='<table class=grtab><tr><th>feature</th>'+GR.gains.map(g=>`<th>gain ${g}</th>`).join('')+'</tr>';
  // colour MERTmid Δ across the whole table (0..max -> grey..green)
  let GMAX=1e-6;GR.rows.forEach(r=>r.points.forEach(p=>{if(p.mert_delta!=null)GMAX=Math.max(GMAX,p.mert_delta);}));
  const gcol=m=>{if(m==null)return'#1a1a1f';const t=Math.max(0,Math.min(1,m/GMAX));return`hsl(${Math.round(t*130)},50%,${14+Math.round(t*18)}%)`;};
  GR.rows.forEach(r=>{
    h+=`<tr><td>${r.feature}</td>`;
    r.points.forEach(p=>{
      const spread=(p.low!=null&&p.high!=null)?`${(+p.low).toFixed(1)}→${(+p.high).toFixed(1)}`:'—';
      h+=`<td style="background:${gcol(p.mert_delta)}"><b>Δ${(+p.mert_delta).toFixed(4)}</b>`+
         `<div class=grsub>${spread}<br>CE ${(+p.ce).toFixed(2)}</div></td>`;
    });
    h+='</tr>';
  });
  h+='</table>';
  h+=`<div class=note>Δ = MERTmid perceptual steering magnitude · low→high = measured target-feature spread (— = activation head, no scalar) · CE = Audiobox content-enjoyment quality.</div>`;
  h+=`</div>`;
}

// ---- spectral_skewness LR/batch optimizer sweep (static finding) ----
h+=`<div class=gr style="border-color:#4a3a2a">`;
h+=`<div class=grhd style="color:#edb">spectral_skewness — LR/batch optimizer sweep (no win; head is at a ceiling)</div>`;
// ---- REVERSAL BOX (EMA experiment overturns the conclusion below) ----
h+=`<div style="margin:10px 0;padding:12px 14px;border:2px solid #6fcf6f;border-radius:6px;background:#13231a">`;
h+=`<div style="color:#9fe89f;font-weight:700;font-size:1.04em;margin-bottom:8px">UPDATE — EMA(+grad-accum) reverses this: the head was damping-limited, not architecture-limited.</div>`;
h+='<table class=grtab style="margin-bottom:8px">';
h+='<tr><th>config</th><th>MERT-mid Δ</th><th>skew lo&rarr;hi</th><th>CE</th></tr>';
[
  ['original',              '0.0086','+1.57','5.51', false],
  ['ema20',                 '0.0237','+2.40','5.50', false],
  ['ema40',                 '0.0248','+2.40','5.51', false],
  ['ema80',                 '0.0197','+1.72','5.47', false],
  ['ema_ga2 (eff batch 64)','0.0271','+2.36','5.59', true],
].forEach(r=>{
  const b=r[4];
  h+=`<tr><td>${b?`<b>${r[0]}</b>`:r[0]}</td>`+
     `<td style="font-variant-numeric:tabular-nums">${b?`<b>Δ${r[1]}</b>`:`Δ${r[1]}`}</td>`+
     `<td>${r[2]}</td><td>${b?`<b>${r[3]}</b>`:r[3]}</td></tr>`;
});
h+='</table>';
h+=`<div class=grnarr style="margin:0 0 8px">All four EMA heads beat the original ~2.3&ndash;3.1&times; at equal/better CE. Best = <b>ema_ga2</b> (EMA 0.999 + grad-accum 2 + 20 ep). It's the <b>averaging</b> (noise-reduction), not displacement, that buys control &mdash; the best head moved the <b>least</b> from init. New default control-head recipe: <b>EMA(+grad-accum) + early-stop</b>.</div>`;
// ---- EMA playable grid (audition the heads) ----
if(D.ema){
  const E=D.ema;
  h+=`<div style="color:#9fe89f;font-weight:600;margin:6px 0 2px">Audition the EMA heads</div>`;
  h+=`<div class=note style="margin:0 0 6px">Click a cell to play (same playhead as the rest of the page — switching cells keeps position, re-click stops). Cell = measured spectral_skewness; <span class=on>green border = online AAC</span>.</div>`;
  h+='<table class=grtab><tr><th>config ＼ prompt</th>'+E.pids.map(p=>`<th>${p}</th>`).join('')+'</tr>';
  E.grid.forEach(row=>{
    const lvcol=row.level=='high'?'#d9b':'#9bd';
    h+=`<tr><td>${row.config} <span style="color:${lvcol}">${row.level}</span></td>`;
    row.cells.forEach(c=>{
      const id='ema_'+safe(row.config+'_'+row.level+'_'+c.pid);
      let bg=measCol(c.measured,E.mmin,E.mmax); if(bg==null)bg=ceCol(c.ce);
      const val=(c.measured!=null)?(+c.measured).toFixed(2):'·';
      if(!c.f){h+=`<td class=no style="background:${bg}">${val}</td>`;}
      else{
        const online=c.f.indexOf('clips_latch_aac/')===0;
        const ob=online?';outline:1px solid #2a5a2a':'';
        h+=`<td class=c id="${id}" style="background:${bg}${ob}" onclick="cell('${id}','${c.f}','${row.config} ${row.level} ${c.pid} → skew ${val}')">${val}</td>`;
      }
    });
    h+='</tr>';
  });
  h+='</table>';
  h+=`<div class=note>low target ≈ −2σ, high ≈ +2σ skewness; colour scales with measured skewness across the 30 clips.</div>`;
}
h+=`</div>`;
h+=`<div class=grnarr>Six training configs — LR 2&times;/4&times;/8&times; at batch 32, and batch 0.5&times;/0.25&times;/single at 2&times; LR — versus the original recipe (AdamW lr 3e-4, bs 32, 20 ep), all evaluated at gain 512. MERT-mid Δ = perceptual steering; skewness lo&rarr;hi = how far the target feature actually follows; CE = Audiobox quality; dist-init = total &Vert;ΔW&Vert; moved from initialization.</div>`;
h+='<table class=grtab>';
h+='<tr><th>config</th><th>MERTmid Δ</th><th>skew lo&rarr;hi (Δ)</th><th>CE</th><th>dist-init</th></tr>';
[
  ['original',  '0.0083','0.56→2.18 (+1.63)','5.52','30',  'hsl(130,50%,32%)'],
  ['lr4x_bs32', '0.0082','0.66→1.69 (+1.03)','5.51','77',  'hsl(128,50%,32%)'],
  ['lr2x_bs32', '0.0076','0.58→2.25 (+1.68)','5.58','48',  'hsl(119,50%,30%)'],
  ['lr2x_bs1',  '0.0074','0.52→2.05 (+1.53)','5.57','229', 'hsl(116,50%,30%)'],
  ['lr2x_bs16', '0.0050','0.49→1.71 (+1.22)','5.60','63',  'hsl(78,50%,25%)'],
  ['lr2x_bs8',  '0.0047','0.51→1.67 (+1.16)','5.59','96',  'hsl(74,50%,24%)'],
  ['lr8x_bs32', '0.0046','0.55→2.04 (+1.49)','5.61','121', 'hsl(72,50%,24%)'],
].forEach(r=>{
  h+=`<tr><td>${r[0]}</td><td style="background:${r[5]};font-variant-numeric:tabular-nums"><b>Δ${r[1]}</b></td>`+
     `<td>${r[2]}</td><td>${r[3]}</td><td>${r[4]}</td></tr>`;
});
h+='</table>';
h+=`<div class=grnarr style="margin-top:8px">`+
   `<b>Verdict.</b> <i style="color:#cda">(superseded by the EMA result above)</i><br>`+
   `&bull; No config beats the original; the best merely ties (lr4x 0.0082 &asymp; orig 0.0083).<br>`+
   `&bull; The winner moved the <b>least</b> (dist-init 30 vs 48&ndash;229) &mdash; every config diverged away from the original's low-movement basin and never returned.<br>`+
   `&bull; The drift hypothesis broke: lr4x moved a lot yet tied; bs1 moved most (229) yet landed mid-pack.<br>`+
   `&bull; Train loss is blind to control (0.0530&ndash;0.0554 while movement spans 7.6&times;).<br>`+
   `&bull; <b>Conclusion:</b> spectral_skewness control is <b>architecture/target-limited, not optimizer-limited</b> &mdash; optimizer tuning for this head is done. Levers: EMA / late-checkpoint soup (small upside), a different head architecture/target, or the energy heads (rms_energy_bass/mid steer 2&ndash;10&times; harder).`+
   `</div>`;
h+=`<img src="skew_layer_heatmap.png" style="max-width:100%;margin-top:10px;border:1px solid #2a2a30;border-radius:4px">`;
h+=`<div class=note>config &times; layer &Vert;ΔW&Vert; per-layer movement, plus grad-noise / path-efficiency.</div>`;
h+=`</div>`;

// ---- leaderboard ----
h+=`<div class=barhd>Leaderboard — ranked by MERT steering magnitude (Δ low↔high)</div>`;
h+='<table class=lead><tr><th>#</th><th>head</th><th>magnitude</th><th>Δlow→high</th><th>Δvs&nbsp;base</th><th>CE@low</th><th>CE@mid</th><th>CE@high</th><th>feature-follow</th><th>tier</th></tr>';
D.board.forEach((b,i)=>{
  let fol='—';
  if(b.follow){fol=(b.follow.mono?'<span class=ok>inc</span>':'<span class=dead>no</span>')+' '+(b.follow.spread>=0?'+':'')+(+b.follow.spread).toFixed(2);}
  h+=`<tr><td class=muted>${i+1}</td><td><a href="#h_${safe(b.head)}">${b.head}</a></td>`+
     `<td style="background:${magCol(b.magnitude)};font-variant-numeric:tabular-nums">${nf(b.magnitude,4)}</td>`+
     `<td>${nf(b.lowhigh,4)}</td><td>${nf(b.vsbase,4)}</td>`+
     `<td style="background:${ceCol(b.ce_low)}">${nf(b.ce_low)}</td>`+
     `<td style="background:${ceCol(b.ce_mid)}">${nf(b.ce_mid)}</td>`+
     `<td style="background:${ceCol(b.ce_high)}">${nf(b.ce_high)}</td>`+
     `<td>${fol}</td><td>${b.magnitude>=0.012?'<span class=ok>STRONG</span>':b.magnitude>=0.005?'<span style="color:#d4c44a">MODERATE</span>':b.magnitude>=0.002?'<span class=muted>weak</span>':'<span class=dead>DEAD</span>'}</td></tr>`;
});
h+='</table>';

// ---- baselines reference row ----
h+=`<div class=barhd style="margin-top:14px">Unguided baselines (reference)</div>`;
h+='<table><tr><th>prompt</th><th>CE</th><th>▶</th></tr>';
D.baselines.forEach((b,i)=>{
  const id='base_'+b.pid;
  const cellhtml=b.f?`<td class=c id="${id}" style="outline:1px solid #2a4a2a" onclick="cell('${id}','${b.f}','baseline ${b.pid}')">▶</td>`:'<td class=muted>·</td>';
  h+=`<tr><td><b>${b.pid}</b> ${b.prompt}</td><td style="background:${ceCol(b.ce)}">${nf(b.ce)}</td>${cellhtml}</tr>`;
});
h+='</table>';

// ---- per head sections ----
D.sections.forEach(s=>{
  h+=`<h2 id="h_${safe(s.head)}">${s.head} ${s.dead?'<span class=dead>· DEAD</span>':''}</h2>`;
  // target distribution
  let tline='Target: ';
  if(s.mean!=null&&s.sigma!=null){
    tline+=`mean ${(+s.mean).toFixed(3)} ± 2σ [${(s.mean-2*s.sigma).toFixed(3)}, ${(s.mean+2*s.sigma).toFixed(3)}]`;
  }else if(s.head=='hpcp'){tline+='E Phrygian dominant chroma direction';}
  else{tline+='(no scalar target)';}
  if(s.gain!=null)tline+=` · gain ${Math.round(s.gain)}`;
  if(s.note)tline+=` · <i>${s.note}</i>`;
  h+=`<div class=tdist>${tline}</div>`;
  h+=`<div class=verdict><b>Verdict:</b> ${s.verdict}</div>`;
  // grid: rows = levels, cols = prompts
  h+='<table><tr><th>level ＼ prompt</th>'+D.pid_order.map(p=>`<th>${p}</th>`).join('')+'</tr>';
  s.grid.forEach(g=>{
    let rowlbl=g.level;
    if(g.std!=null)rowlbl+=` <span class=muted>(σ${(+g.std).toFixed(1)}`+(g.raw!=null?`, raw ${(+g.raw).toFixed(2)}`:'')+`)</span>`;
    h+=`<tr><td>${rowlbl}</td>`;
    g.cells.forEach(c=>{
      const id=safe(s.head+'_'+g.level+'_'+c.pid);
      // colour by measured if available, else CE
      let bg=measCol(c.measured,s.mmin,s.mmax); if(bg==null)bg=ceCol(c.ce);
      const val=(c.measured!=null)?(+c.measured).toFixed(2):(c.ce!=null?nf(c.ce):'·');
      if(!c.f){h+=`<td class=no style="background:${bg}">${val}</td>`;}
      else{
        const online=c.f.indexOf('clips_latch_aac/')===0;
        const ob=online?';outline:1px solid #2a5a2a':'';
        h+=`<td class=c id="${id}" style="background:${bg}${ob}" onclick="cell('${id}','${c.f}','${s.head} ${g.level} ${c.pid} → ${val}')">${val}</td>`;
      }
    });
    h+='</tr>';
  });
  h+='</table>';
});
document.getElementById('wrap').innerHTML=h;
</script></body></html>
"""


def main() -> int:
    if not RESULTS.exists():
        print(f"[abort] {RESULTS} not found — the measure job has not produced rows yet.")
        print("        Re-run this generator once sweep_results.json exists.")
        return 2
    manifest = json.load(open(MANIFEST)) if MANIFEST.exists() else []
    rows = json.load(open(RESULTS))
    if SUMMARY.exists():
        summary = json.load(open(SUMMARY))
        print(f"[info] using analysis_summary.json ({len(summary.get('ranking', []))} heads)")
    else:
        print("[info] analysis_summary.json absent — computing leaderboard inline")
        summary = compute_summary(rows)

    heads = summary["ranking"]
    print(f"[info] {len(rows)} measured rows, {len(heads)} heads ranked")

    stems = subset_clips(heads + ["baseline"])
    print(f"[info] encoding AAC subset: {len(stems)} clips -> {AAC_DIR}")
    online = encode_subset(stems)
    print(f"[info] {len(online)} AAC clips available online")

    ema_stems = [f"{c}_{lv}_{p}" for c in EMA_CONFIGS for lv in EMA_LEVELS for p in PID_ORDER]
    print(f"[info] encoding EMA AAC: {len(ema_stems)} clips -> {AAC_DIR}")
    online_ema = encode_ema(ema_stems)
    print(f"[info] {len(online_ema)} EMA AAC clips available online")
    ema = build_ema(online_ema)

    gain_response = load_gain_response()
    data = build_data(manifest, rows, summary, online, gain_response, ema)
    html = HTML_TMPL.replace("__DATA__", json.dumps(data))
    HTML_OUT.write_text(html)
    print(f"[done] wrote {HTML_OUT} ({len(html)} bytes)")
    print(f"[done] AAC subset: {len(online)} clips in {AAC_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
