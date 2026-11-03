#!/usr/bin/env python3
# Owner: THE-FINN (created 2026-11-03)
"""Sort sa3_lora_runs and latch_sweep into __theme folders and repoint what names them. Dry run unless --apply.

Holds back anything touched in the last --active-hours, anything a live process has in its args, and model_matrix.
Moves are renames on one drive and never overwrite. Writes __MOVED_MAP.json in each root. Scripts executing right
now are not rewritten, since editing a running shell script corrupts it; they are listed for their owners.
"""
import argparse, json, os, re, subprocess, sys, time, glob, collections
M = "/run/media/kim/Mantu"; S = "/home/kim/Projects/SAO"
KEEP = re.compile(r"^(model_matrix.*|_conventions|lightning_logs|__.*|DELETE_LIST.*|README.*|tunableop.*)$")
RULES = {
 "sa3_lora_runs": [(r"mixtape", "__mixtape"), (r"fp32cmp|bf16cmp", "__precision_compare"), (r"fullft|goa5k_fullft", "__fullft"), (r"(dora|goa3_|goa5k_|sa3-goa|newcap|longctx|modular|fusion_autoscale|lion|adamw_|subloss|x0eq|lreq|wfleet|melodychroma|e2_phm|muscriptor)", "__finetunes"), (r"chroma_|concept_steering", "__chroma"), (r"a2a_|breathing|dual_lora|layered_lora|promptarc|phase|stereo", "__a2a_longform"), (r"avp_board|avp_cfg|board|audition|demo_ingest|mp_crossmodel|cu_reward", "__auditions"), (r"genre_fusion", "__genre_style"), (r"^hf_|length_hf|corruption|transitions", "__hf_corruption"), (r".", "__misc")],
 "latch_sweep": [(r"^air_", "__air"), (r"^bass_", "__bass"), (r"^chroma_", "__chroma"), (r"^mood_", "__mood"), (r"^f0_", "__f0"), (r"^modular_|kuang_plan", "__onsets"), (r"^(clips|clips_g512|ladder|skew|sweep|measure|_test|_raw|_g\d|ema)", "__sweep_2026-06"), (r".", "__misc")],
}
def active(p, cut):
    if os.path.isfile(p): return os.path.getmtime(p) > cut
    for dp, dn, fn in os.walk(p):
        dn[:] = [d for d in dn if d != "wandb"]
        for x in fn[:400]:
            try:
                if os.path.getmtime(os.path.join(dp, x)) > cut: return True
            except OSError: pass
    return False
def procs():
    out = []
    for p in os.listdir("/proc"):
        if p.isdigit() and int(p) != os.getpid():
            try: out.append(open(f"/proc/{p}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace"))
            except OSError: pass
    for p in os.listdir("/proc"):
        if p.isdigit():
            try: out += [os.readlink(f"/proc/{p}/fd/{x}") for x in os.listdir(f"/proc/{p}/fd")]
            except OSError: pass
    return [c for c in out if "shell-snapshots" not in c and "sort_run_roots" not in c and "/.claude/" not in c]
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--active-hours", type=float, default=6); ap.add_argument("--roots", nargs="+", default=list(RULES)); a = ap.parse_args()
    cut = time.time() - a.active_hours * 3600; live = procs(); names = {}
    for root in a.roots:
        R = f"{M}/{root}"; mv = collections.defaultdict(list); held = []
        for n in sorted(os.listdir(R)):
            if KEEP.match(n) or n == "__pycache__": continue
            p = f"{R}/{n}"
            if active(p, cut) if not os.path.islink(p) else False: held.append(n); continue
            if any(f"{root}/{n}" in c for c in live): held.append(n); continue
            mv[next(t for r, t in RULES[root] if re.search(r, n))].append(n)
        print(f"== {root}: moving {sum(map(len, mv.values()))}, held back (recent or live): {held[:14]}")
        for t in sorted(mv): print(f"  {t} ({len(mv[t])}): {' '.join(mv[t])[:230]}")
        if a.apply:
            for t, L in mv.items():
                os.makedirs(f"{R}/{t}", exist_ok=True)
                for n in L:
                    if not os.path.lexists(f"{R}/{t}/{n}"): os.rename(f"{R}/{n}", f"{R}/{t}/{n}")
            m = {n: t for t in os.listdir(R) if t.startswith("__") and os.path.isdir(f"{R}/{t}") and t != "__pycache__" for n in os.listdir(f"{R}/{t}")}
            json.dump(m, open(f"{R}/__MOVED_MAP.json", "w"), indent=0, sort_keys=True); names[root] = m
    if not a.apply: return
    alt = {r: re.compile(rf"{r}/(" + "|".join(re.escape(n) for n in sorted(m, key=len, reverse=True)) + r")(?![A-Za-z0-9_.+=-])") for r, m in names.items() if m}
    def fix(t):
        for r, pat in alt.items(): t = pat.sub(lambda x: f"{r}/{names[r][x.group(1)]}/{x.group(1)}", t)
        return t
    n = 0
    for root in (f"{M}/sa3_control_runs", f"{M}/latch_sweep", f"{M}/sa3_lora_runs", f"{S}/.render_root_aliases"):
        for dp, dn, fn in os.walk(root):
            if "model_matrix" in dp: dn[:] = []; continue
            for x in dn + fn:
                p = os.path.join(dp, x)
                if os.path.islink(p):
                    t = os.readlink(p); u = fix(t)
                    if u != t: os.remove(p); os.symlink(u, p); n += 1
    print("symlinks repointed", n)
    running = {os.path.abspath(w) for c in live for w in c.split() if w.endswith((".sh", ".py"))}
    T = [f"{S}/{x}" for x in ("eval", "control", "latch", "onnx", "scripts", "Misc", "lumi", "stable-audio-3/scripts", "stable-audio-3/stable_audio_3", "latent-forge/src", "latent-forge/serve", "RUNBOOK.md")] + ["/home/kim/Projects/mir/plots", "/home/kim/Projects/mir/src"] + glob.glob("/home/kim/build_*.py") + glob.glob(os.path.expanduser("~/.claude/skills/*/SKILL.md"))
    ch = {}; skipped = []
    def scan(p):
        if not p.endswith((".py", ".sh", ".md", ".ts", ".svelte", ".mjs", ".yaml", ".toml", ".json", ".sbatch")) or os.path.basename(p) in ("sort_run_roots.py", "model_census.json"): return
        try:
            if os.path.getsize(p) > 3e6: return
            t = open(p, encoding="utf-8").read()
        except Exception: return
        u = fix(t)
        if u == t: return
        if os.path.abspath(p) in running: skipped.append(p); return
        if p.endswith((".py", ".sh", ".sbatch")) and "/.claude/" not in p:
            L = u.split("\n"); i = 1 if L and L[0].startswith("#!") else 0; L.insert(i, "# Last edited: THE-FINN 2026-11-03 — paths updated for the __theme sorting of sa3_lora_runs and latch_sweep"); u = "\n".join(L)
        open(p, "w", encoding="utf-8").write(u); ch[p] = 1
    for t in T:
        if os.path.isfile(t): scan(t); continue
        for dp, dn, fn in os.walk(t):
            dn[:] = [d for d in dn if d not in ("__pycache__", "node_modules", "musicology", "top100_work") and not d.endswith("venv")]
            for f in fn: scan(os.path.join(dp, f))
    json.dump(sorted(ch), open("/home/kim/sao_runs/june_prune/rewrite_files_2.json", "w"), indent=0)
    print("files rewritten", len(ch), "| running, NOT rewritten:", skipped)
if __name__ == "__main__": main()
