#!/usr/bin/env python
"""dsp_scan_to_db.py — GHOST-NOTE 2026-09-23: CPU-only DSP metrics (flatness/zcr/hf) for an
explicit clip list, via eval/disintegration_metrics.py::measure() (librosa, no GPU), persisted
into clip_metrics.db by path. Same explicit-file-list pattern as corruption_scan_to_db.py and
audiobox_scan_to_db.py -- for filling in board cells that were rendered but never metered,
without needing the GPU (parked for an overnight training run, 2026-09-23).

Usage: dsp_scan_to_db.py <clips.json with a "path" field per entry>
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from disintegration_metrics import measure  # noqa: E402

DB = "/home/kim/Projects/SAO/eval/clip_metrics.db"


def main():
    clips = json.loads(Path(sys.argv[1]).read_text())

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    have = {r[1] for r in con.execute("PRAGMA table_info(metrics)")}
    for c in ("flatness", "zcr", "hf_ratio"):
        if c not in have:
            con.execute(f"ALTER TABLE metrics ADD COLUMN {c} REAL")
    con.commit()

    n_ok, n_err = 0, 0
    for c in clips:
        p = Path(c["path"])
        try:
            m = measure(p)
        except Exception as e:
            print(f"[error] {p.name}: {e}", flush=True)
            n_err += 1
            continue
        fields = {"flatness": m["flatness"], "zcr": m["zcr"], "hf_ratio": m["hf"]}
        con.execute("SELECT 1 FROM metrics WHERE path=?", (str(p),))
        if con.execute("SELECT 1 FROM metrics WHERE path=?", (str(p),)).fetchone():
            con.execute("UPDATE metrics SET flatness=?, zcr=?, hf_ratio=? WHERE path=?",
                        [fields["flatness"], fields["zcr"], fields["hf_ratio"], str(p)])
        else:
            con.execute("INSERT INTO metrics (path, flatness, zcr, hf_ratio) VALUES (?,?,?,?)",
                        [str(p), fields["flatness"], fields["zcr"], fields["hf_ratio"]])
        n_ok += 1
        if n_ok % 50 == 0:
            print(f"  {n_ok}/{len(clips)}", flush=True)
    con.commit()
    con.close()
    print(f"[done] {n_ok} scanned, {n_err} errors -> {DB}", flush=True)


if __name__ == "__main__":
    main()
