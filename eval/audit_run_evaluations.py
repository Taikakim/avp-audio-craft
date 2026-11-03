#!/usr/bin/env python3
# Owner: THE-FINN (created 2026-11-03)
"""Was this run ever evaluated? Read-only evidence audit, one CSV row per run.

Why: the project's rule is that nothing unaudited gets deleted, and evaluation was never
documented in one place. For every run under the given roots this searches session
transcripts (~/.claude/projects, all projects), repo docs and logs, sidecars, the ratings
exports and clip_metrics.db, then reports what evidence exists.

A false "yes" can green-light a deletion, so it errs towards "no":
  heard = yes    Kim's sidecar feedback, a rating, or a listening statement next to the name
                 that is not negated ("not heard", "unaudited" count against).
  heard = weak   a listening word near the name only in an assistant message; often just talk. Counts as maybe.
  scored         clip_metrics rows exist, so metrics ran, but nobody judged anything. Counts as maybe.
  verdict_found  yes if heard, or if a number sits next to the name in a result-like line;
                 maybe if the only link is indirect: a sidecar or doc section with a listening verdict
                 that reaches this run through a script naming it. Maybe is NOT clearance: read it.
  Tool output in transcripts counts as a mention only, never as a verdict: it just echoes files.
  Generic names (clips, ladder, cmp ...) must appear with their parent to count at all.
  Prune and delete-list chatter is ignored, because it names every run without judging any.
This is a heuristic with the evidence attached. Read `evidence` before relying on a yes.
"""
import argparse, collections, csv, glob, json, os, re, sqlite3, sys, time
HOME = os.path.expanduser("~"); SAO = "/home/kim/Projects/SAO"; MANTU = "/run/media/kim/Mantu"
CK = (".pt", ".ckpt", ".safetensors", ".pth")
SKIPDIR = {"wandb", "__pycache__", "model_matrix", ".git", "_QUARANTINE", "eval_mp"}
GENERIC = re.compile(r"^(clips|clips_\w+|ladder|cmp|soups|bracket|analysis|runs?|seg\d+|ep\d+|eval|logs|_smoke|smoke|C\d|S\d|E\d+|renders?|demos?|checkpoints?|phase[A-Z])$")
EAR = re.compile(r"by[- ]ear|listen|audition|ear verdict|\bheard\b|\bsounds?\b|sounded|favou?rite|kim_feedback|\brated\b|\bverdict\b|\bmy ear", re.I)
NEG = re.compile(r"never (obtained|heard|rendered|listened|ran)|not (yet )?(heard|listened|auditioned|audited|judged)|unheard|unaudited|unaudit|un-?listened|no (listening|verdict|ear)|before (a )?listen|to (be )?(audition|listen)|waiting on|pending|needs? (a |your )?(listen|ear)|haven'?t (heard|listened)|should listen|please listen|listening (card|page) (is )?(staged|ready)|measured, not", re.I)
MEAS = re.compile(r"\b(val(idation)?( loss)?|corr(elation)?|gate|spread|cos(ine)?|si-sdr|CE|PQ|MERT|onsets?/s|authority|f1|rel err|dB)\b[^\n]{0,60}\d|\d[^\n]{0,40}\b(val|corr|onsets?/s|dB|gate)\b|COLLAPSED|diverged|\bNaN\b", re.I)
META = re.compile(r"prune|pruning|delete list|deletion|quarantine|manifest|review list|__MOVED_MAP|keep[- ]set|disk space|reclaim|DELETE_LIST|run_audit|audit script", re.I)
TOK = re.compile(r"[A-Za-z0-9_.+=-]{2,}")
HDR = re.compile(r"(20\d\d-\d\d-\d\d)")

def enum_runs(roots):
    runs = {}
    for root in roots:
        rootp = os.path.join(MANTU, root)
        if not os.path.isdir(rootp): print("missing root", rootp, file=sys.stderr); continue
        for top in sorted(os.listdir(rootp)):
            tp = os.path.join(rootp, top)
            if not os.path.isdir(tp) or top in SKIPDIR or top.startswith("_QUARANTINE"): continue
            theme = top.startswith("__")
            for base in ([os.path.join(tp, x) for x in sorted(os.listdir(tp)) if os.path.isdir(os.path.join(tp, x)) and not x.startswith("_logs")] if theme else [tp]):
                rel = os.path.relpath(base, MANTU); runs[rel] = dict(path=base, name=os.path.basename(base), n_ck=0)
                for dp, dn, fn in os.walk(base):
                    dn[:] = [d for d in dn if d not in SKIPDIR and not d.startswith("onset_eval")]
                    depth = dp[len(base):].count(os.sep)
                    if depth > 3: dn[:] = []; continue
                    cks = [f for f in fn if f.lower().endswith(CK)]
                    if cks and dp != base:
                        r2 = os.path.relpath(dp, MANTU); runs.setdefault(r2, dict(path=dp, name=os.path.basename(dp), n_ck=0))["n_ck"] += len(cks)
                    runs[rel]["n_ck"] += len(cks)
    return runs

class Ev:
    __slots__ = ("mentions","user","first","last","heard","weak","meas","neg","evid","later","sources","epochs")
    def __init__(s): s.mentions=0;s.weak=0;s.user=0;s.first="";s.last="";s.heard=0;s.meas=0;s.neg=0;s.evid=[];s.later=set();s.sources=set();s.epochs=collections.Counter()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--roots", nargs="+", default=["latch_sweep"]); ap.add_argument("--out", default="/home/kim/sao_runs/run_audit/run_audit.csv")
    ap.add_argument("--exclude-session", action="append", default=["de0a3788"]); ap.add_argument("--transcript-before", default="2026-11-03T05:00", help="ignore transcript messages at or after this time: the pruning discussion itself")
    a = ap.parse_args(); t0 = time.time()
    runs = enum_runs(a.roots); byname = collections.defaultdict(list)
    for r, d in runs.items(): byname[d["name"]].append(r)
    E = {r: Ev() for r in runs}; print("runs", len(runs), flush=True)
    def scan(text, date, src, kind):
        """kind: user / assistant / tool / doc / code"""
        if not text: return
        for m in TOK.finditer(text):
            tok = m.group(0).rstrip(".,;:=+-")
            for suf in (".log", ".json", ".sh", ".html", ".nohup", ".tsv", ".txt"):
                if tok.endswith(suf): tok = tok[:-len(suf)]
            if tok not in byname: continue
            before = text[max(0, m.start()-200):m.start()]
            win = text[max(0, m.start()-170):m.end()+170]; line = re.sub(r"\s+", " ", win).strip()
            cands = byname[tok]
            if GENERIC.match(tok) or len(tok) < 5:
                cands = [r for r in cands if os.path.basename(os.path.dirname(r))+"/"+tok in text[max(0,m.start()-len(tok)-80):m.end()]]
            elif len(cands) > 1:
                sp = [r for r in cands if os.path.basename(os.path.dirname(r)) in before]
                cands = sp or cands
            for r in cands:
                e = E[r]; e.mentions += 1; e.sources.add(src.split(":")[0])
                if date and (not e.first or date < e.first): e.first = date
                if date and date > e.last: e.last = date
                if kind == "user": e.user += 1
                if kind == "code": e.later.add(os.path.basename(src.split(":")[0])); continue
                if kind == "tool" or META.search(win): continue
                for ep in re.findall(r"\bep(?:och)?[ =_]?(\d+)\b", win, re.I): e.epochs[ep] += 1
                neg = bool(NEG.search(win)); ear = bool(EAR.search(win)); meas = bool(MEAS.search(win))
                if neg: e.neg += 1
                if ear and not neg:
                    if kind=="assistant": e.weak += 1
                    else: e.heard += 1
                    e.evid.append((0 if kind=="user" else 1 if kind=="doc" else 2, date, f"[ear/{kind}] {src}: {line[:230]}"))
                elif meas: e.meas += 1; e.evid.append((3, date, f"[measured/{kind}] {src}: {line[:230]}"))
    # 1 transcripts
    files = glob.glob(HOME+"/.claude/projects/*/*.jsonl")+glob.glob(HOME+"/.claude/projects/*/*/subagents/*.jsonl")
    n=0
    for f in files:
        if any(x in f for x in a.exclude_session): continue
        sid = os.path.basename(f)[:8]
        try: fh = open(f, errors="replace")
        except OSError: continue
        for ln, l in enumerate(fh, 1):
            if '"content"' not in l: continue
            try: d = json.loads(l)
            except ValueError: continue
            ty = d.get("type"); ts = (d.get("timestamp") or "")[:16]
            if ty not in ("user","assistant") or (ts and ts >= a.transcript_before): continue
            c = (d.get("message") or {}).get("content")
            parts = []
            if isinstance(c, str): parts.append(("user" if ty=="user" else "assistant", c))
            elif isinstance(c, list):
                for b in c:
                    if not isinstance(b, dict): continue
                    if b.get("type")=="text": parts.append(("user" if ty=="user" else "assistant", b.get("text","")))
                    elif b.get("type")=="tool_result":
                        x=b.get("content"); parts.append(("tool", x if isinstance(x,str) else " ".join(i.get("text","") for i in x if isinstance(i,dict)) if isinstance(x,list) else ""))
            for k, t in parts:
                if ty=="user" and k=="user" and (d.get("isCompactSummary") or d.get("isMeta") or d.get("isSidechain") or t.lstrip()[:1]=="<" or t.startswith(("This session is being continued","Another Claude session","Base directory for this skill"))): k="tool"
                scan(t, ts[:10], f"session:{sid}:{ln}", k)
        n+=1
        if n%100==0: print("transcripts",n,"/",len(files),round(time.time()-t0),"s",flush=True)
    print("transcripts done",round(time.time()-t0),"s",flush=True)
    # 2 repo docs and logs, line by line; a date comes from the nearest entry header above
    docs = [p for pat in ("*.md","*.txt","docs/**/*.md","dialogue/*.md","profiles/*.md","*.log","control/**/*.md","latch-notes","track_listening_*","stable-audio-tools/LATCH_RESULTS.txt","papers/knowledge.md") for p in glob.glob(os.path.join(SAO,pat),recursive=True)]
    docs = [p for p in set(docs) if os.path.isfile(p) and "/pruning/" not in p and "/release/" not in p and "superpowers/plans" not in p and not re.search(r"(retry48|run_arch\d|explorer_render_server)\.log$",p) and os.path.getsize(p)<3e7]
    for p in docs:
        rel=os.path.relpath(p,SAO); date=time.strftime("%Y-%m-%d",time.localtime(os.path.getmtime(p)))
        try: fh=open(p,errors="replace")
        except OSError: continue
        for i,l in enumerate(fh,1):
            if l.startswith(("#","- [","- **")):
                h=HDR.search(l[:70]); date=h.group(1) if h else date
            scan(l, date, f"{rel}:{i}", "doc")
    print("docs",len(docs),round(time.time()-t0),"s",flush=True)
    # 3 later scripts and pages: naming only, never a verdict
    code=[p for pat in ("eval/*.py","eval/*.sh","control/**/*.py","control/**/*.sh","latch/*","Misc/*.py","onnx/*.py","eval/presets/*") for p in glob.glob(os.path.join(SAO,pat),recursive=True)]+glob.glob("/home/kim/evals_aac/*.html")+glob.glob("/home/kim/riffer-evals/*.html")
    for p in code:
        if not os.path.isfile(p) or os.path.getsize(p)>3e7 or os.path.basename(p) in ("audit_run_evaluations.py",): continue
        try: scan(open(p,errors="replace").read(), time.strftime("%Y-%m-%d",time.localtime(os.path.getmtime(p))), p, "code")
        except OSError: pass
    print("code",len(code),round(time.time()-t0),"s",flush=True)
    # 3b indirect: script names run; a doc section naming that script, or an eval sidecar, holds a listening verdict
    script_runs=collections.defaultdict(set)
    for r,e in E.items():
        for sc in e.later:
            if sc.endswith((".py",".sh")): script_runs[os.path.splitext(sc)[0]].add(r)
    indirect=collections.defaultdict(list); VERD=re.compile(r"listening verdict|kim_feedback|verdict \(|by ear|\bKim'?s? (ear|listen)|audition of .* found|owner(, |'s )?(listen|ear)",re.I)
    for fn in ("EXPERIMENTS.md","DISCOVERIES.md","docs/training-findings.md"):
        p=os.path.join(SAO,fn)
        if not os.path.isfile(p): continue
        for sec in re.split(r"\n(?=#{2,4} )|\n(?=- \*\*[A-Z]\d)",open(p,errors="replace").read()):
            ve=[l for l in sec.split("\n") if VERD.search(l) and not NEG.search(l)]
            if not ve: continue
            hdr=sec.split("\n")[0][:70]
            for stem in set(TOK.findall(sec)):
                st=stem.split("/")[-1]; st=os.path.splitext(st)[0]
                for r in script_runs.get(st,()):
                    indirect[r].append(f"[indirect/section] {fn} '{hdr}' via {st}: {re.sub(chr(32)+'+',' ',ve[0])[:170]}")
    for m in glob.glob(MANTU+"/sa3_control_runs/**/run_meta.json",recursive=True)+glob.glob(MANTU+"/latch_sweep/**/run_meta.json",recursive=True):
        try: t=open(m,errors="replace").read(); j=json.loads(t)
        except Exception: continue
        if not j.get("kim_feedback"): continue
        for tk in set(x.rstrip(".,") for x in TOK.findall(t)):
            for r in byname.get(tk,()):
                if not GENERIC.match(tk) and not m.startswith(runs[r]["path"]):
                    indirect[r].append(f"[indirect/eval sidecar] {os.path.relpath(m,MANTU)}: {str(j['kim_feedback'])[:170]}")
    # 4 sidecars
    fb=collections.Counter(); 
    for r,d in runs.items():
        for m in glob.glob(d["path"]+"/**/run_meta.json",recursive=True)[:200]:
            try: j=json.load(open(m))
            except Exception: continue
            for key in ("kim_feedback","findings"):
                if j.get(key):
                    fb[r]+=1; E[r].heard+=1; E[r].evid.append((0,"",f"[ear/sidecar {key}] {os.path.relpath(m,MANTU)}: {str(j[key])[:220]}"))
            res=j.get("notes") or j.get("purpose") or ""
            if isinstance(res,str) and EAR.search(res) and not NEG.search(res) and not META.search(res):
                E[r].heard+=1; E[r].evid.append((1,"",f"[ear/sidecar notes] {os.path.relpath(m,MANTU)}: {res[:220]}"))
            if j.get("result"): E[r].meas+=1; E[r].evid.append((2,"",f"[measured/sidecar result] {os.path.relpath(m,MANTU)}: {str(j['result'])[:200]}"))
    # 5 ratings and metrics
    rate=collections.Counter(); text=""
    for f in sorted(glob.glob(SAO+"/eval/ratings_export_*.jsonl"))[-3:]:
        try: text+=open(f,errors="replace").read()
        except OSError: pass
    toks=collections.Counter(TOK.findall(text))
    for name,rs in byname.items():
        if toks.get(name) and not GENERIC.match(name):
            for r in rs: rate[r]+=toks[name]
    db=collections.Counter()
    try:
        con=sqlite3.connect(f"file:{SAO}/eval/clip_metrics.db?mode=ro",uri=True); cur=con.cursor()
        tb=[x[0] for x in cur.execute("select name from sqlite_master where type='table'")]
        for t in tb:
            cols=[c[1] for c in cur.execute(f"pragma table_info({t})")]
            col=next((c for c in cols if c in("path","file","clip","filepath","clip_path")),None)
            if not col: continue
            cnt=collections.Counter()
            for (p,) in cur.execute(f"select {col} from {t}"):
                for part in str(p).split("/"): cnt[part]+=1
            for name,rs in byname.items():
                if cnt.get(name) and not GENERIC.match(name):
                    for r in rs: db[r]=max(db[r],cnt[name])
    except Exception as ex: print("clip_metrics skipped",ex,file=sys.stderr)
    os.makedirs(os.path.dirname(a.out),exist_ok=True)
    with open(a.out,"w",newline="") as o:
        w=csv.writer(o); w.writerow("run,name,n_checkpoints,mentions,kim_typed,first_mention,last_mention,sources,verdict_found,heard,kind,heard_hits,measured_hits,not_heard_hits,ratings,scored_clips,sidecar_feedback,epochs_named,later_code_pages,evidence".split(","))
        c=collections.Counter()
        for r in sorted(runs):
            e=E[r]; heard=e.heard>0 or rate[r]>0; meas=e.meas>0
            ind=indirect.get(r,[])
            kind="ear" if heard else "measured" if meas else "indirect" if ind else "ear_weak" if e.weak else "scored" if db[r] else "none"; v="yes" if heard or meas else "maybe" if kind in("indirect","ear_weak","scored") else "no"
            ev=sorted(e.evid,key=lambda x:(x[0],x[1]))[:4]+[(3,"",x) for x in sorted(set(ind))[:2]]
            c[kind]+=1
            w.writerow([r,runs[r]["name"],runs[r]["n_ck"],e.mentions,e.user,e.first,e.last,len(e.sources),v,"yes" if heard else "weak" if e.weak else "no",kind,e.heard,e.meas,e.neg,rate[r],db[r],fb[r],";".join(k for k,_ in e.epochs.most_common(6)),";".join(sorted(e.later))[:200]," || ".join(x[2] for x in ev)])
    print("wrote",a.out,dict(c),round(time.time()-t0),"s"); print("ALLDONE")
if __name__=="__main__": main()
