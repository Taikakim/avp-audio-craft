#!/usr/bin/env python3
# Owner: THE-FINN (created 2026-11-03)
"""Second pass after the __theme sorting: fix run paths built from a root variable, which a literal-path rewrite misses.

Only touches a file that assigns a variable to a run root, and only `{VAR}/name`, `$VAR/name`, `${VAR}/name`,
`VAR / "name`, `VAR + "/name` and `join(VAR, "name`, where name is a directory in that root's __MOVED_MAP.json.
Skips scripts executing now. Dry run unless --apply. Dynamic paths (`{RUNS}/{name}`) cannot be fixed here: listed.
"""
import json, os, re, sys, glob
M = "/run/media/kim/Mantu"; apply = "--apply" in sys.argv
maps = {}
for r in ("sa3_lora_runs", "latch_sweep", "sa3_control_runs"):
    maps[r] = {n: t for n, t in json.load(open(f"{M}/{r}/__MOVED_MAP.json")).items() if os.path.isdir(f"{M}/{r}/{t}/{n}") and not n.startswith("_logs")}
ROOTV = re.compile(r'''^\s*(?:export\s+|(?:readonly\s+))?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:Path\(|os\.path\.join\()?[frb]?["']?[^"'\n#]*?/?(sa3_lora_runs|latch_sweep|sa3_control_runs)/?["']?\)?\s*(?:#.*)?$''', re.M)
live = set()
for p in os.listdir("/proc"):
    if p.isdigit():
        try: live |= {os.path.abspath(w) for w in open(f"/proc/{p}/cmdline", "rb").read().decode(errors="replace").split("\0") if w.endswith((".sh", ".py"))}
        except OSError: pass
T = []
for d in ("eval", "control", "latch", "onnx", "scripts", "Misc", "stable-audio-3/scripts", "/home/kim/Projects/mir/plots", "/home/kim/Projects/mir/src"):
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in ("__pycache__", "node_modules", "musicology", "top100_work")]
        T += [os.path.join(dp, f) for f in fn if f.endswith((".py", ".sh", ".sbatch"))]
T += glob.glob("/home/kim/build_*.py")
ch = {}; dyn = {}; skip = []
for p in T:
    if os.path.basename(p) in ("repoint_piecewise_paths.py", "sort_run_roots.py", "control_runs_repoint.py", "audit_run_evaluations.py"): continue
    try: s = open(p, encoding="utf-8").read()
    except Exception: continue
    vs = {m.group(1): m.group(2) for m in ROOTV.finditer(s)}
    if not vs: continue
    new = s; n = 0
    for v, r in vs.items():
        names = "|".join(re.escape(x) for x in sorted(maps[r], key=len, reverse=True))
        if not names: continue
        pre = rf'(\{{{v}\}}/|\${v}/|\$\{{{v}\}}/|\b{v}\s*/\s*["\']|\b{v}\s*\+\s*["\']/|join\(\s*{v}\s*,\s*["\'])'
        def rep(m):
            nonlocal_n[0] += 1; return f"{m.group(1)}{maps[r][m.group(2)]}/{m.group(2)}"
        nonlocal_n = [0]
        new = re.sub(pre + rf'({names})(?![A-Za-z0-9_.+=-])', rep, new); n += nonlocal_n[0]
        d = re.findall(rf'(?:\{{{v}\}}/\{{|\b{v}\s*/\s*[a-zA-Z_(]|\${v}/\$|\$\{{{v}\}}/\$|join\(\s*{v}\s*,\s*[a-zA-Z_])', s)
        if d: dyn[p] = dyn.get(p, 0) + len(d)
    if n:
        if os.path.abspath(p) in live: skip.append(p); continue
        ch[p] = n
        if apply:
            L = new.split("\n"); i = 1 if L and L[0].startswith("#!") else 0
            L.insert(i, "# Last edited: THE-FINN 2026-11-03 — root-variable paths updated for the __theme sorting"); open(p, "w", encoding="utf-8").write("\n".join(L))
print("files", len(ch), "refs", sum(ch.values()), "| running, skipped:", skip)
for p, n in sorted(ch.items(), key=lambda x: -x[1])[:14]: print(f"  {n:3} {p}")
print("dynamic root paths, not fixable here:", len(dyn))
json.dump(dict(changed=sorted(ch), dynamic=sorted(dyn), skipped=skip), open("/home/kim/sao_runs/june_prune/piecewise.json", "w"), indent=0)
