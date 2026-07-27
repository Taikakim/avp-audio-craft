#!/usr/bin/env python3
"""Audiobox aesthetics (CE/PQ/CU/PC) over all eval clips — the neural/GPU metric.

The companion GPU pass to clip_metrics.py (CPU). Writes the SAME SQLite DB. Kim's GPU-
batching idea (2026-07-12): most matrix clips are the same length, so we bucket by rounded
duration and batch same-length clips through one predictor.forward() call. WavLM OOMs on big
batches on the 16GB card (CLAUDE.md), so we start at --batch 8 and HALVE on OOM down to 1.
Resumable: skips clips that already have a CE score.

Run (mir venv, GPU): mir/bin/python control/sa3_control/clip_metrics_audiobox.py [--batch 8]
"""
import argparse
import glob
import os
import sqlite3
import sys
import time
from collections import defaultdict

STAGE = "/home/kim/evals_aac"
DB = "/home/kim/Projects/SAO/eval/clip_metrics.db"
AB_COLS = ["ce", "pq", "cu", "pc"]
# predictor.forward returns uppercase short keys (verified 2026-07-12)
KEYMAP = {"ce": "CE", "pq": "PQ", "cu": "CU", "pc": "PC"}
ROOT_PRIORITY = {"model_matrix": 0, "riffer": 1, "control_runs": 2, "renders": 3}


def ensure_cols(con):
    con.execute("CREATE TABLE IF NOT EXISTS metrics (path TEXT PRIMARY KEY)")
    have = {r[1] for r in con.execute("PRAGMA table_info(metrics)")}
    for c in AB_COLS:
        if c not in have:
            con.execute(f"ALTER TABLE metrics ADD COLUMN {c} REAL")
    con.commit()


def enumerate_clips(roots):
    paths = []
    for r in roots:
        paths += glob.glob(f"{STAGE}/{r}/**/*.m4a", recursive=True)
        paths += glob.glob(f"{STAGE}/{r}/*.m4a")
    return sorted(set(paths))


def dur_bucket(path):
    import soundfile as sf
    try:
        info = sf.info(path)
        return round(info.duration)
    except Exception:
        try:
            import librosa
            return round(librosa.get_duration(path=path))
        except Exception:
            return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--roots", default="model_matrix,control_runs,renders,riffer")
    args = ap.parse_args()

    sys.path.insert(0, "/home/kim/Projects/mir/src")
    from timbral.audiobox_aesthetics import get_predictor
    predictor = get_predictor()
    if predictor is None:
        print("audiobox predictor unavailable", file=sys.stderr); sys.exit(1)

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    ensure_cols(con)
    done = {r[0] for r in con.execute("SELECT path FROM metrics WHERE ce IS NOT NULL")}
    # skip clips >60s: WavLM OOMs on multi-minute audio, and one aesthetic score over
    # an 8-min a2a/longform clip is not meaningful (Audiobox is designed for ~10-30s).
    # dur is already in the DB from the CPU pass.
    too_long = {r[0] for r in con.execute("SELECT path FROM metrics WHERE dur > 60")}
    clips = [c for c in enumerate_clips(args.roots.split(",")) if c not in done and c not in too_long]
    print(f"audiobox: {len(clips)} clips to score (batch {args.batch})", flush=True)
    if not clips:
        return

    # priority order: model_matrix first (the main listening surface Kim audits), then
    # riffer/control/renders; same-length clips adjacent. Resumable, so an incomplete
    # overnight run still covers the most valuable set first.
    # dur for the same-length grouping comes from the DB (the CPU pass already computed it) —
    # NOT dur_bucket(), which re-decodes each .m4a via librosa/audioread (libsndfile can't read
    # AAC headers) and left the GPU IDLE under the lock for ~20 min re-deriving known durations.
    dur_map = {r[0]: r[1] for r in con.execute("SELECT path, dur FROM metrics WHERE dur IS NOT NULL")}
    def prio(c):
        root = c.split("/evals_aac/")[-1].split("/")[0]
        d = dur_map.get(c)
        if d is None:
            d = dur_bucket(c)          # rare fallback: clip not yet CPU-metered
        return (ROOT_PRIORITY.get(root, 9), d)
    clips.sort(key=prio)

    def score_batch(batch):
        """predictor.forward on a list of paths; halve on OOM down to 1."""
        bs = len(batch)
        while bs >= 1:
            try:
                out = []
                for i in range(0, len(batch), bs):
                    sub = batch[i:i + bs]
                    preds = predictor.forward([{"path": p} for p in sub])
                    out.extend(preds)
                return out
            except RuntimeError as e:
                if "out of memory" in str(e).lower() and bs > 1:
                    import torch
                    torch.cuda.empty_cache()
                    bs = max(1, bs // 2)
                    print(f"  OOM -> batch {bs}", flush=True)
                else:
                    raise
        return None

    t0 = time.time(); n = 0
    for i in range(0, len(clips), args.batch):
        batch = clips[i:i + args.batch]
        try:
            preds = score_batch(batch)
        except Exception as e:
            print(f"  ! batch failed: {e}", flush=True); continue
        if not preds:
            continue
        rows = [(pr.get(KEYMAP["ce"]), pr.get(KEYMAP["pq"]), pr.get(KEYMAP["cu"]),
                 pr.get(KEYMAP["pc"]), p) for p, pr in zip(batch, preds)]
        con.executemany("INSERT INTO metrics (ce,pq,cu,pc,path) VALUES (?,?,?,?,?) "
                        "ON CONFLICT(path) DO UPDATE SET ce=excluded.ce, pq=excluded.pq, "
                        "cu=excluded.cu, pc=excluded.pc", rows)
        con.commit()
        n += len(batch)
        if n % 200 < args.batch:
            rate = n / (time.time() - t0)
            print(f"  {n}/{len(clips)} ({rate:.1f}/s, ETA {int((len(clips)-n)/max(rate,1e-6)/60)}min)", flush=True)
    print(f"audiobox DONE: {n} scored in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
