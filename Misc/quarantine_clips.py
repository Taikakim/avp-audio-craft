#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""quarantine_clips.py -- take model-matrix clips off the boards for a stated reason, and keep the flag that says so.

The flag file is ~/evals_aac/model_matrix/quarantined.jsonl, one JSON per removed clip: its board coordinates, the reason, the date. model_matrix.html and
dora_table.html fetch it, so a flagged cell shows N/A and clicking it says "Clip quarantined"; a cell that was never rendered stays blank. A live clip at the same
coordinates always wins, so re-rendering a cell clears its N/A with no other step. Published publicly: no paths in it.

  add --list files.txt --reason "..." --tag dc [--apply]   move the clip's m4a, wav and latent to Mantu/sa3_lora_runs/model_matrix_QUARANTINE_<date>_<tag>/, strip manifest.jsonl, delete its clip_metrics rows, flag it
  register --dir <old quarantine dir> --reason "..." --date YYYY-MM-DD [--apply]   flag clips an earlier quarantine already removed (coordinates parsed from the file name)
  unflag --list files.txt [--apply]                         remove flags only; the cell goes back to blank
Without --apply nothing changes. After a change run Misc/stage_matrix_clips.sh, then rebuild and publish (RUNBOOK). The files are moved, not deleted; deleting the quarantine dir is a separate decision.
"""
import argparse
import json
import re
import shutil
import sqlite3
from pathlib import Path

STAGE = Path.home() / "evals_aac/model_matrix"
RENDER = Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix")
QROOT = RENDER.parent
MANIFEST = STAGE / "manifest.jsonl"
FLAGS = STAGE / "quarantined.jsonl"
DB = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")
NAME = re.compile(r"^(?P<model>.+)__(?P<ckpt>(?:(?!__).)+)__cfg(?P<cfg>[\d.]+)__w(?P<w>\d+)__(?P<pid>.+?)__s(?P<seed>\d+)(?:__d(?P<d>\d+))?\.m4a$")
KEEP = ("model", "ckpt", "cfg", "strength", "prompt_id", "seed", "duration_mode", "file")


def read_jsonl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def write_atomic(p, lines):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text("".join(l + "\n" for l in lines))
    tmp.replace(p)


def parse(name):
    m = NAME.match(name)
    if not m:
        return None
    g = m.groupdict()
    r = dict(model=g["model"], ckpt=g["ckpt"], cfg=float(g["cfg"]), strength=int(g["w"]) / 100, prompt_id=g["pid"], seed=int(g["seed"]), file=name)
    if g["d"]:
        r["duration_mode"] = "native"
    return r


def coord(e):
    return (e["model"], e["ckpt"], float(e["cfg"]), float(e["strength"]), str(e["prompt_id"]), e.get("duration_mode") == "native")


def add_flags(new, apply):
    """Merge by coordinates. An older flag for the same cell stays unless the new one is for a different file."""
    cur = {coord(e): e for e in read_jsonl(FLAGS)}
    before = len(cur)
    for e in new:
        cur[coord(e)] = e
    print(f"flags: {before} -> {len(cur)}")
    if apply:
        write_atomic(FLAGS, [json.dumps(e, sort_keys=True) for e in cur.values()])


def cmd_add(a):
    names = sorted({Path(l.strip()).name for l in Path(a.list).read_text().splitlines() if l.strip()})
    rows = read_jsonl(MANIFEST)
    by = {}
    for e in rows:
        by.setdefault(e["file"], []).append(e)
    q = QROOT / f"model_matrix_QUARANTINE_{a.date}_{a.tag}"
    flags, moves, unknown = [], [], []
    for n in names:
        ents = by.get(n)
        if not ents:
            unknown.append(n)
            continue
        flags += [{**{k: e[k] for k in KEEP if k in e}, "reason": a.reason, "date": a.date} for e in ents]
        stem = n[:-4]
        for suffix in (".m4a", ".wav", ".z0.npy"):
            s = RENDER / (stem + suffix)
            if s.exists():
                moves.append((s, q / s.name))
        if (STAGE / n).exists():
            moves.append((STAGE / n, q / ("staged__" + n)))
    drop = set(names) - set(unknown)
    print(f"clips {len(names)}, not in the manifest {len(unknown)} {unknown[:3]}, manifest rows to strip {sum(len(by[n]) for n in drop)}, files to move {len(moves)}, to {q}")
    add_flags(flags, a.apply)
    if not a.apply:
        print("dry run, nothing changed")
        return
    q.mkdir(exist_ok=True)
    write_atomic(MANIFEST, [json.dumps(e) for e in rows if e["file"] not in drop])
    for s, d in moves:
        shutil.move(str(s), str(d))
    db = sqlite3.connect(DB)
    n_db = 0
    for n in drop:
        for p in (STAGE / n, RENDER / n, RENDER / (n[:-4] + ".wav")):
            n_db += db.execute("delete from metrics where path=?", (str(p),)).rowcount
    db.commit()
    with (q / "README.md").open("a") as f:
        f.write(f"# Quarantine {a.date} ({a.tag})\n\nReason: {a.reason}\n\n{len(drop)} clips moved by Misc/quarantine_clips.py. Manifest rows stripped, {n_db} clip_metrics rows deleted, flagged in quarantined.jsonl so the boards show N/A. staged__*.m4a = the staging copy.\n\n")
        f.write("\n".join(sorted(drop)) + "\n")
    print(f"done: moved {len(moves)}, metrics rows deleted {n_db}")


def cmd_register(a):
    live = {coord(e) for e in read_jsonl(MANIFEST)}
    names = {p.name.removeprefix("staged__") for p in Path(a.dir).glob("*.m4a")}
    flags, bad, relive = [], [], 0
    for n in sorted(names):
        e = parse(n)
        if not e:
            bad.append(n)
        elif coord(e) in live:
            relive += 1
        else:
            flags.append({**e, "reason": a.reason, "date": a.date})
    print(f"{a.dir}: {len(names)} clips, flagged {len(flags)}, since re-rendered {relive}, name not parsed {len(bad)} {bad[:3]}")
    add_flags(flags, a.apply)


def cmd_unflag(a):
    names = {Path(l.strip()).name for l in Path(a.list).read_text().splitlines() if l.strip()}
    cur = read_jsonl(FLAGS)
    keep = [e for e in cur if e["file"] not in names]
    print(f"flags: {len(cur)} -> {len(keep)}")
    if a.apply:
        write_atomic(FLAGS, [json.dumps(e, sort_keys=True) for e in keep])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--list", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--date", default="2026-11-03")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("register")
    p.add_argument("--dir", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_register)
    p = sub.add_parser("unflag")
    p.add_argument("--list", required=True)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_unflag)
    args = ap.parse_args()
    args.fn(args)
