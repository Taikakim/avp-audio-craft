#!/usr/bin/env python
"""audiobox_scan_to_db.py — GHOST-NOTE 2026-09-22: Audiobox Aesthetics (CE/PQ/CU/PC) for an
EXPLICIT clip list, not a staging-dir glob. control/sa3_control/clip_metrics_audiobox.py only
enumerates *.m4a under ~/evals_aac/{model_matrix,control_runs,renders,riffer} -- fine for board
cells, but raw training-time demo clips (e.g. a run's demos/stepN/*.wav) live on Mantu as .wav
with no .m4a sibling and no staging copy, so that glob finds nothing. Same predictor, same DB,
same upsert -- just driven by a path list instead of a directory walk.

Run (mir venv, GPU): mir/bin/python eval/audiobox_scan_to_db.py <clips.json with a "path" field>
"""
import json
import sqlite3
import sys
from pathlib import Path

DB = "/home/kim/Projects/SAO/eval/clip_metrics.db"
KEYMAP = {"ce": "CE", "pq": "PQ", "cu": "CU", "pc": "PC"}


def main():
    clips_json = Path(sys.argv[1])
    clips = json.loads(clips_json.read_text())
    paths = [c["path"] for c in clips]

    sys.path.insert(0, "/home/kim/Projects/mir/src")
    from timbral.audiobox_aesthetics import get_predictor
    predictor = get_predictor()
    if predictor is None:
        print("audiobox predictor unavailable", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS metrics (path TEXT PRIMARY KEY)")
    have = {r[1] for r in con.execute("PRAGMA table_info(metrics)")}
    for c in KEYMAP:
        if c not in have:
            con.execute(f"ALTER TABLE metrics ADD COLUMN {c} REAL")
    con.commit()

    # BATCH + OOM-HALVE (2026-09-22 fix): the original script starts at --batch 8 and halves
    # on OOM down to 1 for exactly this reason -- WavLM OOMs on big batches on the 16GB card.
    # First cut of this script sent all clips in ONE predictor.forward() call and the process
    # died silently (no traceback, no Python exception -- a HIP/ROCm-level abort), leaving an
    # orphaned python process still holding ~15GB VRAM after its setsid parent looked dead.
    def score_batch(batch, bs=8):
        while bs >= 1:
            try:
                out = []
                for i in range(0, len(batch), bs):
                    sub = batch[i:i + bs]
                    out.extend(predictor.forward([{"path": p} for p in sub]))
                return out
            except RuntimeError as e:
                if "out of memory" in str(e).lower() and bs > 1:
                    import torch
                    torch.cuda.empty_cache()
                    bs = max(1, bs // 2)
                    print(f"  OOM -> batch {bs}", flush=True)
                else:
                    raise

    preds = score_batch(paths)
    rows = [(pr.get(KEYMAP["ce"]), pr.get(KEYMAP["pq"]), pr.get(KEYMAP["cu"]),
             pr.get(KEYMAP["pc"]), p) for p, pr in zip(paths, preds)]
    con.executemany("INSERT INTO metrics (ce,pq,cu,pc,path) VALUES (?,?,?,?,?) "
                     "ON CONFLICT(path) DO UPDATE SET ce=excluded.ce, pq=excluded.pq, "
                     "cu=excluded.cu, pc=excluded.pc", rows)
    con.commit()
    con.close()

    for p, pr in zip(paths, preds):
        print(f"  CE={pr.get('CE'):.2f} PQ={pr.get('PQ'):.2f} CU={pr.get('CU'):.2f} "
              f"PC={pr.get('PC'):.2f}  {Path(p).name}", flush=True)
    print(f"[done] {len(paths)} scored -> {DB}", flush=True)


if __name__ == "__main__":
    main()
