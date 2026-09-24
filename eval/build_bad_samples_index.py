#!/usr/bin/env python
"""build_bad_samples_index.py — GHOST-NOTE 2026-09-24: dumps clip_metrics.db's n_bad_jumps
column (per-clip amplitude-jump corruption count, incl. the 999999 non-finite-latent
sentinel -- see audio_corruption_scan.py / corruption_scan_to_db.py) as a small basename-keyed
JSON so a browser can look up a SPECIFIC clip's bad-sample count without a server-side DB
query. Consumed by both build_dora_table_page.py's (Kim direct 2026-09-24: "a column with
per-clip bad sample count, per selected clip") and build_bad_samples_page.py's audition board.

Keyed by the .m4a basename (the served-audio filename every eval page's manifest already uses
as its 'file' field), not the full path -- clip_metrics.db has separate .wav/.m4a rows per
clip (corruption_scan_to_db.py writes both), so this dedupes to the one form pages actually
reference and drops the .wav-only rows.

Output: ~/evals_aac/model_matrix/n_bad_by_file.json (served alongside manifest_live.jsonl,
same STAGING dir as model_matrix_gen.py -- see its comment for why: page JS fetches both
relative to the same page URL).
"""
import json
import sqlite3
from pathlib import Path

DB = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")
OUT = Path.home() / "evals_aac/model_matrix/n_bad_by_file.json"


def main():
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cur.execute("SELECT path, n_bad_jumps FROM metrics WHERE n_bad_jumps IS NOT NULL AND path LIKE '%.m4a'")
    out = {Path(p).name: n for p, n in cur.fetchall()}
    con.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"[bad-index] {len(out)} clips -> {OUT}")


if __name__ == "__main__":
    main()
