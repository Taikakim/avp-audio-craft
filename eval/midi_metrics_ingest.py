#!/usr/bin/env python
"""midi_metrics_ingest.py -- fold MuScriptor transcription features into clip_metrics.db.

WHY THIS EXISTS (GHOST-NOTE, 2026-09-09). `eval/hook_eval_renders.py` writes rich per-clip
MIDI features to a JSONL beside its .mid files, deliberately touching no database. That kept
the two concerns separate, but it also meant the features were invisible to every eval page,
table and ranking -- they could only be used by whoever knew the JSONL existed.

They are worth joining, because they are ORTHOGONAL to the aesthetic metrics we already have.
Measured on 146 clips of the 2026-09-08 autoscale renders, comparing clips whose transcription
found a lead voice against those where it found none:

    metric      no-lead    lead        d        z
    pq            7.956    7.927    -0.10    -0.61     <- blind
    ce            6.676    6.782    +0.22    +1.27     <- blind
    crest         4.058    4.744    +0.45    +2.62     <- partially sees it
    flatness      0.021    0.026    +0.31    +1.83
    hf_ratio      0.013    0.013    +0.00    +0.00     <- blind

So **whether a render contains a melodic lead at all is not something PQ or CE can see**, and
project guidance is that engaging melodic content is exactly what separates a top rating from a
merely well-produced clip. A metric that cannot see melody cannot model that judgment.

WRITES A SEPARATE TABLE, not new columns on `metrics`: other tools do `SELECT *` and build
tables from the column list, and widening the main table would change their output. `midi_metrics`
is keyed by the same `path`, so a consumer joins explicitly and nothing else changes.

  eval/midi_metrics_ingest.py <hook_metrics.jsonl> [more.jsonl ...] [--db PATH] [--dry-run]

COVERAGE IS THE CATCH -- read it before believing any null. The melodic features
(hook_melodic_ratio, contour_compression, top_motif, ...) are NULL on ~66% of clips, because
they need a lead voice and 40% of these renders have n_lead == 0. `has_lead` and `n_lead` are
defined for every clip; the rest are conditional on `has_lead`. Averaging a melodic feature over
a mixed set silently averages over "no melody" as if it were missing at random -- it is not.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")
STAGE = "/home/kim/evals_aac/model_matrix/"

# (column, sqlite type, source key) -- only the fields that survived the coverage audit as
# either always-present or explicitly conditional. Kept flat so a page can SELECT them directly.
COLS = [
    ("path", "TEXT PRIMARY KEY", None),
    ("clip", "TEXT", "clip"),
    ("has_lead", "INTEGER", None),          # derived: n_lead > 0, defined for EVERY clip
    ("n_notes", "INTEGER", "n_notes"),
    ("n_lead", "INTEGER", "n_lead"),
    ("n_kick", "INTEGER", "n_kick"),
    ("midi_bpm", "REAL", "bpm"),
    ("beat_source", "TEXT", "beat_source"),
    # conditional on has_lead -- NULL is "no lead to measure", NOT "measurement failed"
    ("lead_density_nps", "REAL", "lead_density_nps"),
    ("pitch_range_st", "REAL", "pitch_range_st"),
    ("hook_melodic_ratio", "REAL", "hook_melodic_ratio"),
    ("hook_pedal_ratio", "REAL", "hook_pedal_ratio"),
    ("pedal_occupancy", "REAL", "pedal_occupancy"),
    ("distinct46_grid_ratio", "REAL", "distinct46_grid_ratio"),
    ("contour_compression", "REAL", "contour_compression"),
    ("tonic", "INTEGER", "tonic"),
    ("mode", "TEXT", "mode"),
]


def rows_from(paths):
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="+", help="hook_metrics.jsonl file(s) from hook_eval_renders.py")
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    recs = list(rows_from(a.jsonl))
    if not recs:
        sys.exit("no rows read -- nothing to ingest")

    out = []
    for r in recs:
        clip = r.get("clip")
        if not clip:
            continue
        n_lead = r.get("n_lead")
        vals = {"path": STAGE + clip + ".m4a", "clip": clip,
                "has_lead": None if n_lead is None else int(n_lead > 0)}
        for col, _t, src in COLS:
            if src:
                vals[col] = r.get(src)
        out.append(tuple(vals.get(c) for c, _t, _s in COLS))

    have = sum(1 for r in out if r[2])          # has_lead
    print(f"[midi] {len(out)} clips | has_lead {have} ({100*have/len(out):.0f}%) "
          f"| melodic features defined on {sum(1 for r in recs if r.get('hook_melodic_ratio') is not None)}")
    if a.dry_run:
        print("[midi] DRY RUN -- nothing written")
        return

    con = sqlite3.connect(a.db, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS midi_metrics (%s)" %
                ", ".join(f"{c} {t}" for c, t, _s in COLS))
    con.executemany("INSERT OR REPLACE INTO midi_metrics VALUES (%s)" %
                    ",".join("?" * len(COLS)), out)
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM midi_metrics").fetchone()[0]
    matched = con.execute(
        "SELECT COUNT(*) FROM midi_metrics m JOIN metrics c ON c.path = m.path").fetchone()[0]
    con.close()
    # gate on the JOIN, not the insert: rows that never match `metrics` are invisible to
    # every page that would use them, which is indistinguishable from not ingesting at all.
    print(f"[midi] midi_metrics now {n} rows, {matched} of them joinable to metrics.path")
    if matched == 0:
        sys.exit("[midi] ZERO rows join to metrics -- the clips are not scored/staged under "
                 f"{STAGE}; ingest is useless until they are")


if __name__ == "__main__":
    main()
