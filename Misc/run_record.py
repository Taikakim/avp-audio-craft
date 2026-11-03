#!/usr/bin/env python3
# Owner: THE-FINN (created 2026-11-03)
"""The per-run record: keep the code with the run, append results without overwriting, check a run.

  run_record.py snapshot RUN_DIR SCRIPT [SCRIPT ...]   copy launcher + trainer into RUN_DIR/_code/, note git state
  run_record.py autosnapshot RUN_DIR SCRIPT ...        same, plus any launcher found up the process tree (trainers call this)
  run_record.py append RUN_DIR --kind auto|human --by HANDLE --text "..." [--source PAGE_OR_FILE] [--json FILE]
  run_record.py check RUN_DIR                          what is missing; exit 1 if anything is

Rules live in docs/TRAINING.md D36-D39. Sidecars in the wild hold kim_feedback and result as a string,
a list or a dict, and generators read those keys by name, so nothing here changes an existing value's
meaning: evaluations are appended to a new `evaluations` list, and a human verdict also extends
kim_feedback in whatever shape it already has. Stdlib only, so any venv can run it.
"""
import argparse, fcntl, filecmp, json, os, re, shutil, subprocess, sys, tempfile, time

REPOS = ("/home/kim/Projects/SAO", "/home/kim/Projects/SAO/stable-audio-3", "/home/kim/Projects/SAO/stable-audio-tools", "/home/kim/Projects/mir")
NAME = re.compile(r"^[a-z0-9]+(?:[-.+=][a-z0-9]+)*_[a-z0-9]+(?:[-_.+=][a-z0-9]+)*_\d{8}$")

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%S")

class Locked:
    """Exclusive lock on RUN_DIR/.run_meta.lock for the read-modify-write of run_meta.json."""
    def __init__(s, run_dir): s.p = os.path.join(run_dir, ".run_meta.lock")
    def __enter__(s): s.f = open(s.p, "w"); fcntl.flock(s.f, fcntl.LOCK_EX); return s
    def __exit__(s, *a): fcntl.flock(s.f, fcntl.LOCK_UN); s.f.close()

def load(run_dir):
    p = os.path.join(run_dir, "run_meta.json")
    if not os.path.exists(p): return {}
    with open(p) as f: return json.load(f)   # a corrupt sidecar must stop us, not be replaced

def save(run_dir, meta):
    p = os.path.join(run_dir, "run_meta.json")
    fd, tmp = tempfile.mkstemp(dir=run_dir, prefix=".run_meta.", suffix=".tmp")
    with os.fdopen(fd, "w") as f: json.dump(meta, f, indent=1, ensure_ascii=False); f.write("\n")
    os.replace(tmp, p)

def extend_kim_feedback(old, date, by, text, source):
    entry = {"date": date, "source": source or by, "verdict": text}
    if old in (None, "", [], {}): return [entry]
    if isinstance(old, list): return old + [entry]
    if isinstance(old, dict): return [old, entry]
    return f"{old}\n\n[{date}, {source or by}] {text}"

def append(run_dir, kind, by, text, source=None, data=None):
    if kind not in ("auto", "human"): raise SystemExit("--kind is auto or human")
    with Locked(run_dir):
        m = load(run_dir); date = _now()
        e = {"date": date, "kind": kind, "by": by, "text": text}
        if source: e["source"] = source
        if data is not None: e["data"] = data
        m["evaluations"] = list(m.get("evaluations") or []) + [e]
        if kind == "human": m["kim_feedback"] = extend_kim_feedback(m.get("kim_feedback"), date[:10], by, text, source)
        save(run_dir, m)
    return len(m["evaluations"])

def snapshot(run_dir, scripts):
    code = os.path.join(run_dir, "_code"); os.makedirs(code, exist_ok=True); stamp = time.strftime("%Y%m%d-%H%M%S"); names = []
    for s in scripts:
        if not os.path.isfile(s): raise SystemExit(f"no such script: {s}")
        d = os.path.join(code, os.path.basename(s))
        if os.path.exists(d) and not filecmp.cmp(s, d, shallow=False):   # a resume with changed code keeps both
            b, e = os.path.splitext(d); d = f"{b}.{stamp}{e}"
        if not os.path.exists(d): shutil.copy2(s, d)
        names.append(os.path.relpath(d, run_dir))
    with open(os.path.join(code, f"git_state.{stamp}.txt"), "w") as f:
        f.write(f"{_now()}\nargv: {' '.join(sys.argv)}\npython: {sys.executable}\n")
        for r in REPOS:
            if not os.path.isdir(r): continue
            q = lambda *a: subprocess.run(["git", "-C", r, *a], capture_output=True, text=True).stdout
            f.write(f"\n== {r}\n{q('rev-parse','HEAD').strip()} {q('rev-parse','--abbrev-ref','HEAD').strip()}\n")
            d = q("diff", "--", *[x for x in scripts if os.path.abspath(x).startswith(r + os.sep)]) if any(os.path.abspath(x).startswith(r + os.sep) for x in scripts) else ""
            if d: f.write(d)
    with Locked(run_dir):
        m = load(run_dir); m["code_snapshot"] = list(m.get("code_snapshot") or []) + [{"date": _now(), "files": names}]; save(run_dir, m)
    return names

def find_launchers(pid=None, depth=8):
    """Launch scripts among this process's ancestors: the shell script or sbatch that started the trainer."""
    pid = pid or os.getppid(); out = []
    for _ in range(depth):
        try:
            argv = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0"); cwd = os.readlink(f"/proc/{pid}/cwd")
            ppid = int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError): break
        for a in argv[:4]:
            a = a.decode(errors="replace")
            if a.endswith((".sh", ".sbatch", ".bash")) and "shell-snapshots" not in a:
                p = a if os.path.isabs(a) else os.path.join(cwd, a)
                if os.path.isfile(p) and p not in out: out.append(p)
        if ppid <= 1: break
        pid = ppid
    return out

def check(run_dir):
    m = load(run_dir); miss = []
    for k in ("purpose", "hypothesis", "status"):
        if not m.get(k): miss.append(f"run_meta.{k}")
    code = os.path.join(run_dir, "_code")
    if not (os.path.isdir(code) and any(x.endswith((".py", ".sh", ".sbatch")) for x in os.listdir(code))): miss.append("_code/ with the launch and training scripts")
    name = os.path.basename(os.path.abspath(run_dir))
    note = [] if NAME.match(name) else [f"name {name!r} is not <subject>_<method>_..._<YYYYMMDD> (fine for an arm inside a campaign or an older run)"]
    return miss, note

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("snapshot"); s.add_argument("run_dir"); s.add_argument("scripts", nargs="+")
    a = sp.add_parser("append"); a.add_argument("run_dir"); a.add_argument("--kind", required=True); a.add_argument("--by", required=True); a.add_argument("--text", required=True); a.add_argument("--source"); a.add_argument("--json")
    h = sp.add_parser("autosnapshot", help="what trainers call: snapshot the given scripts plus any launcher found up the process tree"); h.add_argument("run_dir"); h.add_argument("scripts", nargs="+")
    c = sp.add_parser("check"); c.add_argument("run_dir")
    x = ap.parse_args()
    if x.cmd == "autosnapshot":
        os.makedirs(x.run_dir, exist_ok=True); fs = x.scripts + [l for l in find_launchers() if l not in x.scripts]
        print("[run_record] kept with the run:", snapshot(x.run_dir, fs)); return
    if not os.path.isdir(x.run_dir): raise SystemExit(f"no such run dir: {x.run_dir}")
    if x.cmd == "snapshot": print("copied", snapshot(x.run_dir, x.scripts))
    elif x.cmd == "append":
        d = json.load(open(x.json)) if x.json else None
        print("evaluations now", append(x.run_dir, x.kind, x.by, x.text, x.source, d))
    else:
        miss, note = check(x.run_dir)
        for n in note: print("note:", n)
        if miss: print("MISSING:", "; ".join(miss)); sys.exit(1)
        print("ok")

if __name__ == "__main__": main()
