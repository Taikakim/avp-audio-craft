#!/usr/bin/env python3
"""
build_model_matrix.py -- THE MODEL MATRIX (Kim 2026-07-11, the overnight priority):
a 4-column preset board where each column = (model, checkpoint) chosen by dropdowns,
and the rows sweep cfg {1,7,16} x DoRA-strength {0.6,1.0,1.5} x a prompt subsample,
every cell a same-playhead player. Checkpoints that already have renders are LIT in
the dropdown; unlit = selectable but marked "not rendered yet" (the coverage map).
Per-(model,ckpt) recipe + training-data block under each header (Kim: "the way
others can learn from all of this").

MANIFEST-DRIVEN (the contract with GHOST-NOTE's renderer, DM 2026-07-11):
  ~/.cache/evals_aac/model_matrix/manifest.jsonl -- one JSON per clip:
  {"model": run-label, "ckpt": "ep4", "cfg": 7, "strength": 1.0,
   "prompt_id": "p03", "prompt_text": "...", "seed": 123, "file": "x.m4a"}
The GUI is generated ENTIRELY from manifest + models-meta; rebuild + reship as
clips land and the board self-populates. Renders fine with an EMPTY manifest
(full model list, all unlit, "awaiting the overnight run").

Models meta: build_model_index.collect_models() (same source as models.html) +
models_index_overrides.json {recipe, training_data, note} per label.
Redaction: run labels only -- no paths, no ckpt filenames.

Run: python3 Misc/build_model_matrix.py  -> ~/.cache/evals_aac/model_matrix.html
"""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_model_index import collect_models, OVERRIDES  # noqa: E402
from build_site import redact  # noqa: E402  (shared redaction; one-way dep, no cycle)

# Commentary-JSON schema fields that ship to the PUBLIC payload (docs/experiment-commentary-spec.md).
# provenance.run_script / provenance.checkpoint are INTERNAL and deliberately absent here — see
# _public_commentary(). Present only on backfilled entries; legacy entries carry none of these.
_COMMENTARY_FIELDS = ("one_liner", "family", "why", "recipe", "compare_against", "verdict", "status")
# Distinctly-new fields that mark an entry as a backfilled commentary (vs a legacy
# {recipe:str, training_data, note} entry). recipe/family also exist in legacy form, so they
# can't be the trigger — a bare legacy recipe STRING renders via the old inline path, not the
# commentary block. A structured (dict) recipe also marks the new schema.
_COMMENTARY_TRIGGERS = ("one_liner", "why", "compare_against", "verdict", "status")
_PROV_PUBLIC = ("created", "by", "commit")  # public-safe provenance keys; run_script/checkpoint dropped


def _redact_deep(v):
    """redact() every string in a str / dict / list, recursively. The model-matrix payload is
    embedded in public HTML, so this runs on everything that ships (same leak class closed on
    the profile path 2026-07-30). Non-str scalars pass through."""
    if isinstance(v, str):
        return redact(v)
    if isinstance(v, dict):
        return {k: _redact_deep(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_redact_deep(x) for x in v]
    return v


def _public_commentary(ov):
    """Build the public commentary block from an overrides entry: redact all strings, keep only
    public-safe provenance (drop the INTERNAL run_script/checkpoint paths). Returns None for a
    legacy entry that carries none of the new fields."""
    is_new = any(k in ov for k in _COMMENTARY_TRIGGERS) or isinstance(ov.get("recipe"), dict)
    if not is_new:
        return None  # legacy entry (bare recipe string / provenance only) — no commentary block
    present = {k: ov[k] for k in _COMMENTARY_FIELDS if k in ov}
    prov = ov.get("provenance")
    out = {k: _redact_deep(v) for k, v in present.items()}
    if isinstance(prov, dict):
        pub = {k: _redact_deep(prov[k]) for k in _PROV_PUBLIC if k in prov}
        if pub:
            out["provenance"] = pub
    return out or None


STAGING = Path.home() / ".cache/evals_aac"
MANIFEST = STAGING / "model_matrix" / "manifest.jsonl"
OUT = STAGING / "model_matrix.html"
CFGS = (1, 7, 16)
# union of the legacy axis (0.6/1.0/1.5, pre-2026-07-20) and the current one
# (1.0/1.5/2.0, Kim 2026-07-20: drop 0.6 from new renders, add 2.0) -- keeps
# old 0.6 cells visible (their columns just render empty on new checkpoints)
# rather than dropping them off the grid.
STRENGTHS = (0.6, 1.0, 1.5, 2.0)


def jsnum(x):
    """Stringify a number the way JS String(Number) does -- drop a trailing .0
    (1.0->"1", 16.0->"16") but keep real fractions (0.6->"0.6"). The manifest
    stores cfg/strength as floats; the embedded-snapshot data keys must match the
    JS-side lookup keys (built from JSON-parsed numbers), or every cell on the
    file:// page misses (Kim 2026-07-11: local board cells had no audio)."""
    f = float(x)
    return str(int(f)) if f == int(f) else repr(f)

CSS = """
body{font:13px system-ui;margin:14px;background:#101012;color:#e0e0e0}
h1{font-size:17px;margin:0 0 4px}a{color:#7cf}
.how{color:#cba;font-size:12px;line-height:1.5;margin:6px 0 12px;max-width:1150px}
#hdr{position:sticky;top:0;z-index:9;background:#16181c;padding:7px 12px;margin:-14px -14px 12px;
border-bottom:1px solid #2a2a30;font-size:13px}#np{color:#cde}#pos{color:#888}
#trans{display:none;align-items:center;gap:8px;margin-left:12px;vertical-align:middle}
#trans.on{display:inline-flex}
#pp{background:none;border:0;color:#7cf;cursor:pointer;font-size:14px;padding:0 2px;line-height:1}
#seek{width:240px;max-width:36vw;accent-color:#7cf;cursor:pointer;height:4px}
#tm{color:#9ab;font-variant-numeric:tabular-nums;font-size:12px;white-space:nowrap}
#dl{color:#7cf;text-decoration:none;font-size:16px;padding:0 4px;line-height:1}#dl:hover{color:#adf}
#cols{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:start}
.col{background:#141417;border:1px solid #242428;border-radius:8px;padding:10px}
select{width:100%;background:#1b1b20;color:#dde;border:1px solid #333;border-radius:4px;
padding:4px;margin:2px 0;font-size:12px}
option.lit{color:#7f7}option.unlit{color:#777}
.recipe{font-size:11px;color:#9ab;line-height:1.45;margin:6px 0;border-left:2px solid #368;
padding-left:7px;height:120px;overflow-y:auto}
.tdata{font-size:11px;color:#a98;line-height:1.4;margin:4px 0;height:34px;overflow-y:auto}
/* commentary block (docs/experiment-commentary-spec.md) — fixed-height + scroll like recipe/tdata
   so it doesn't break the constant-header-height -> aligned-prompt-grid invariant below. NOTE:
   columns WITH commentary are taller than legacy columns during backfill; once every entry carries
   commentary this is uniform again. Final cross-column-alignment polish (reserve the slot in every
   column, or a different placement) is deferred to real-data + Kim's eye. */
.cmt{font-size:11px;line-height:1.5;margin:6px 0;border-left:2px solid #5a4;padding-left:7px}
summary.cmt-one{cursor:pointer;color:#cde;font-weight:600;list-style-position:outside}
summary.cmt-one:hover{color:#eef}
.cmt-body{margin-top:4px;max-height:340px;overflow-y:auto}
.cmt-row{color:#9ba;margin:3px 0}.cmt-row b{color:#8ac}
.cmt-rec{margin:2px 0 2px 14px;padding:0;color:#9ab}.cmt-rec li{margin:1px 0}
.cmt-ax{color:#7a8;font-style:italic}
.cmt-status{color:#778;font-size:10px;text-transform:uppercase;letter-spacing:.03em;margin-top:3px}
.pgrid{margin:8px 0}.plabel{font-size:11px;color:#8a9;margin:8px 0 2px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
table.mini{border-collapse:collapse;width:100%}
.mini td,.mini th{border:1px solid #26262c;text-align:center;font-size:10px;color:#889;padding:2px}
.cell{cursor:pointer;background:#191920}.cell:hover{outline:1px solid #7cf}
.cell.have{background:#1d2b1f;color:#9f9}.cell.miss{color:#555;cursor:default}
.cell.playing{outline:2px solid #5d5 !important}
.cell.loading{outline:2px solid #fa5 !important}
/* Kim 2026-08-14: dim (not hide -- same "grey with a hint, don't remove" convention as the
   no-clips-at-these-settings prompt label above) cells lacking the checked alt-render, so the
   grid itself shows coverage instead of only affecting playback like the native toggle used to. */
body.filter-native .cell.have.no-nat{opacity:.22}
body.filter-ptm .cell.have.no-ptm{opacity:.22}
.cov{font-size:11px;color:#7a7;margin:2px 0}
/* fixed-height meta block: recipe(120)+tdata(34) are already fixed, so pinning the
   variable tail (family / good-fraction / native-cell) makes the whole header a
   constant height -> the prompt grid starts at the same Y in every column, so the
   same prompt lands on the same horizontal line across models (Kim 2026-07-22) */
.covwrap{height:84px;overflow-y:auto}
/* phone readability (Kim 2026-07-30): stack the 4 preset columns to 1 below tablet
   width instead of squashing them to ~90px each; same breakpoint eval_grid.py already
   uses elsewhere on the site. Sticky header + seek bar shrink so the transport controls
   still fit a narrow screen without wrapping. */
@media (max-width:820px){
 #cols{grid-template-columns:1fr}
 body{margin:10px}
 #hdr{margin:-10px -10px 10px;padding:6px 10px}
}
"""


def main():
    models = collect_models()
    overrides = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}
    entries = []
    if MANIFEST.exists():
        for ln in MANIFEST.read_text().splitlines():
            try:
                entries.append(json.loads(ln))
            except Exception:
                pass

    # coverage + data maps
    prompts = {}
    data = {}          # "model|ckpt|cfg|w|pid" -> file
    native = {}        # "model|ckpt" -> {file, duration, prompt_text} (native-training-length cell;
                        # NOT in `data` -- duration isn't part of the cfg/w/pid key, so a native clip
                        # sharing (cfg,w,pid) with a standard 20s cell would silently collide/overwrite
                        # (GHOST-NOTE 2026-07-20, caught before ship)
    ngrid = {}         # "model|ckpt|cfg|w|pid" -> file: the FULL native grid (2026-08-02 length-
                        # variant run renders native at every cfg/w/prompt of a terminal ckpt).
                        # `native` keeps ONE representative per ckpt for the audition line --
                        # preference-picked (kl_* prompt, cfg 7, w 1) instead of last-manifest-
                        # line-wins, which under full grids was effectively random.
    nscore = {}
    cov = {}           # model -> {ckpt: n_clips}
    for e in entries:
        pid = str(e.get("prompt_id"))
        prompts.setdefault(pid, e.get("prompt_text", pid))
        # a cell is playable only when its m4a actually exists in staging --
        # G's manifest runs ahead of his transcode; dead cells are worse than
        # briefly-missing ones (they'd 404-cache in the browser)
        if not (STAGING / "model_matrix" / e["file"]).exists():
            continue
        if e.get("duration_mode") == "native":
            mk = f'{e["model"]}|{e["ckpt"]}'
            ngrid[f'{mk}|{jsnum(e["cfg"])}|{jsnum(e["strength"])}|{pid}'] = e["file"]
            score = (2 if pid.startswith("kl_") else 0) \
                  + (1 if float(e["cfg"]) == 7 else 0) + (1 if float(e["strength"]) == 1 else 0)
            if score >= nscore.get(mk, -1):
                nscore[mk] = score
                native[mk] = {"file": e["file"], "duration": e.get("duration"),
                              "prompt_text": e.get("prompt_text", pid)}
            continue
        key = f'{e["model"]}|{e["ckpt"]}|{jsnum(e["cfg"])}|{jsnum(e["strength"])}|{pid}'
        data[key] = e["file"]
        cov.setdefault(e["model"], {}).setdefault(e["ckpt"], 0)
        cov[e["model"]][e["ckpt"]] += 1

    # labels that exist ONLY in the manifest get a synthetic entry so they still
    # appear in the dropdowns -- e.g. the *_ptm rows (same adapter file rendered on
    # the POST-TRAINED medium instead of medium-base, Kim 2026-07-21): a different
    # base model, not a different run, so there is no run dir to collect.
    known = {m["label"] for m in models}
    for lab in sorted({e["model"] for e in entries} - known):
        models.append({"label": lab,
                       "family": ("post-trained medium (base-trained adapter transplant)"
                                  if lab.endswith("_ptm") else "manifest-only"),
                       "n_ckpts": 0})

    meta = {}
    for m in models:
        ov = overrides.get(m["label"], {})
        # Top-level recipe stays a STRING (legacy JS renders info.recipe inline). The new schema
        # makes recipe a nested object -> that structured form ships under commentary.recipe and
        # renders in the commentary block; the inline string is blanked so it never shows
        # "[object Object]". redact() the public strings (labels-only convention is no longer
        # enough now the schema carries provenance + scale).
        _recipe = ov.get("recipe", "")
        meta[m["label"]] = {
            "family": m["family"], "n_ckpts": m["n_ckpts"],
            "recipe": redact(_recipe) if isinstance(_recipe, str) else "",
            "training_data": redact(ov.get("training_data", "")),
            "note": redact(ov.get("note", "")), "ckpts": sorted(cov.get(m["label"], {}).keys()),
        }
        commentary = _public_commentary(ov)
        if commentary:
            meta[m["label"]]["commentary"] = commentary

    # per-(model,ckpt) GOOD-FRACTION from clip_metrics.db — operationalizes Kim's
    # "verdicts should be distributional, not good/bad" (2026-07-12): fraction of a
    # checkpoint's rendered cells with CE >= 6.0 (an interpretable enjoyment bar;
    # calibratable once Kim's in-place ratings flow). gf["model|ckpt"] = [pct, n].
    gf = {}
    _dbp = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")
    if _dbp.exists():
        import sqlite3
        _con = sqlite3.connect(_dbp)
        _agg = {}
        for _p, _ce in _con.execute("SELECT path, ce FROM metrics WHERE path LIKE '%/model_matrix/%' AND ce IS NOT NULL"):
            _b = _p.split("/model_matrix/")[-1].split("__")
            if len(_b) < 2:
                continue
            _agg.setdefault(f"{_b[0]}|{_b[1]}", []).append(_ce)
        for _k, _v in _agg.items():
            gf[_k] = [round(100 * sum(1 for x in _v if x >= 6.0) / len(_v)), len(_v)]

    n_models_lit = sum(1 for v in cov.values() if v)
    doc = [f'<!doctype html><html><head><meta charset=utf-8>'
           f'<meta name="viewport" content="width=device-width, initial-scale=1">'
           f'<title>Model matrix</title><style>{CSS}</style></head><body>']
    doc.append('<div id=hdr>&#9654; <b id=np>pick a model per column, click a cell to play</b>'
               '<span id=trans><button id=pp title="play / pause">&#9208;</button>'
               '<input type=range id=seek min=0 max=1000 value=0 step=1 title="playhead — drag to seek">'
               '<span id=tm>0:00&#8239;/&#8239;0:00</span>'
               '<a id=dl href="#" download title="download the track playing now">&#8681;</a></span>'
               ' <label style="color:#8b8" title="play each cell&#39;s native-training-length render '
               '(e.g. 47.5s for T512 models) instead of the 20s comparison clip, where one exists '
               '(terminal checkpoints) -- cells without one keep their 20s clip. Also DIMS cells that '
               'have no native-length twin, so the grid shows coverage even without clicking through.">'
               '<input type=checkbox id=mnative> native</label>'
               ' <label style="color:#88b" title="DIMS cells that have no post-trained (rf_denoiser/'
               'ping-pong base, this column&#39;s adapter applied, cfg1/w1-only) counterpart -- i.e. '
               'no sibling row named this model+_ptm exists at that cell&#39;s cfg/w/prompt. If the '
               'selected column IS already a _ptm model, this has nothing to dim against (you&#39;re '
               'already looking at the post-trained render) and is a no-op, same as unchecking it.">'
               '<input type=checkbox id=mptm> post-trained</label>'
               ' <button id=mspread onclick="spreadCkpts()" title="fill all four columns with an '
               'evenly-spaced sample of the selected model&#39;s checkpoints (first, last, and two '
               'between) -- the useful default for an unscored model, where there are no metrics to '
               'rank checkpoints by and coverage of the training trajectory is what you want."'
               ' style="background:#23252c;border:1px solid #3a3d48;color:#cde;border-radius:4px;'
               'padding:2px 8px;cursor:pointer">spread ckpts</button>'
               ' <button id=mshare onclick="copyShareLink()" title="copy a link to THIS exact '
               'four-column selection -- the address bar already carries it, this just copies it."'
               ' style="background:#23252c;border:1px solid #3a3d48;color:#cde;border-radius:4px;'
               'padding:2px 8px;cursor:pointer">copy link</button>'
               ' <span id=ld style="color:#fa5"></span>'
               ' &nbsp;·&nbsp; <span style="color:#888">same playhead across every cell; loops until stopped; re-click stops; amber outline = loading</span></div>')
    doc.append('<h1>Model matrix — every trained model × checkpoint × cfg × strength, side by side</h1>'
               '<a href=index.html>← evals</a> · <a href=models.html>models index</a>')
    doc.append(f'<div class=how><b>What this is:</b> the listening matrix over the whole model zoo. '
               f'Each of the 4 columns is a preset: pick a MODEL, then a CHECKPOINT (green = rendered, '
               f'grey = not yet). Below, each prompt shows a 3×3 grid — rows cfg 1/7/16 (how hard the '
               f'prompt steers), columns DoRA strength 0.6-2.0 (how strongly the adapter is applied; '
               f'n/a for base; 0.6 is a legacy value kept for older checkpoints, 2.0 added 2026-07-20). '
               f"A native-training-length cell (the checkpoint's actual trained context, not the fixed "
               f'20s grid) appears per checkpoint when known -- look for duration_mode "native" cells. '
               f'All cells share ONE playhead, so switching mid-play A/Bs the exact same '
               f'moment. Recipes + training data under each header — this page doubles as the record of '
               f'how each model was made. Coverage now: <b>{n_models_lit}/{len(models)} models have '
               f'renders</b>{" — awaiting the overnight run" if not entries else ""}.</div>')
    doc.append('<div class=how style="border-left:3px solid #5d9;padding-left:10px"><b>What the numbers say '
               '(see <a href="stats.html">Statistics</a>):</b> <b>rank 128 is the good option</b> — rank-16 '
               'adapters are harsher and lower CE/PQ, and glitch ~6× worse at DoRA weight 1.5. On <b>training '
               'length</b>: for rank-128 the quality sweet spot is <b>early (ep0–4)</b>; more epochs overtrain '
               '(CE/PQ fall), fastest at high LR — unless you <b>augment</b> (the aug10 run keeps improving to '
               'ep74). So when auditioning, prefer the early checkpoints of the un-augmented rank-128 runs.</div>')

    payload = {"models": meta, "data": data, "native": native, "ngrid": ngrid, "prompts": prompts,
               "cfgs": list(CFGS), "strengths": list(STRENGTHS), "gf": gf}
    # manifest_live.jsonl = only entries whose m4a exists in staging (my sync loop
    # ships it beside the clips). The page fetches it at LOAD TIME and rebuilds MM
    # client-side -> the served board self-updates on every data rsync, no html
    # rebuild (Kim 2026-07-11: "UI reads JSON manifests automatically"). The
    # embedded snapshot below is the fallback for plain file:// (Chrome blocks
    # file fetch) and for fetch failures.
    live_lines = [json.dumps({**e}) for e in entries
                  if (STAGING / "model_matrix" / e["file"]).exists()]
    (STAGING / "model_matrix" / "manifest_live.jsonl").write_text("\n".join(live_lines))
    doc.append(f'<script>let MM = {json.dumps(payload)};</script>')
    doc.append("""<script>
async function refreshMM(){
 try{
  const r = await fetch('model_matrix/manifest_live.jsonl', {cache:'no-store'});
  if(!r.ok) return;
  const txt = await r.text();
  const data={}, native={}, ngrid={}, nscore={}, prompts={}, cov={};
  for(const ln of txt.split('\\n')){ if(!ln.trim()) continue;
   let e; try{e=JSON.parse(ln)}catch(_){continue}
   const pid=String(e.prompt_id); if(!(pid in prompts)) prompts[pid]=e.prompt_text||pid;
   if(e.duration_mode==='native'){const mk=e.model+'|'+e.ckpt;
    ngrid[mk+'|'+e.cfg+'|'+e.strength+'|'+pid]=e.file;
    const sc=(pid.startsWith('kl_')?2:0)+(e.cfg==7?1:0)+(e.strength==1?1:0);
    if(sc>=(nscore[mk]??-1)){nscore[mk]=sc;native[mk]={file:e.file,duration:e.duration,prompt_text:e.prompt_text||pid};}
    (cov[e.model]=cov[e.model]||{})[e.ckpt]=1; continue}
   data[e.model+'|'+e.ckpt+'|'+e.cfg+'|'+e.strength+'|'+pid]=e.file;
   (cov[e.model]=cov[e.model]||{})[e.ckpt]=1; }
  MM.data=data; MM.native=native; MM.ngrid=ngrid; MM.prompts=prompts;
  for(const m of Object.keys(MM.models)) MM.models[m].ckpts=Object.keys(cov[m]||{}).sort();
  render();
 }catch(_){/* file:// or offline -> embedded snapshot stands */}
}
setInterval(refreshMM, 90000);  // live page self-updates every 90 s
window.addEventListener('load', refreshMM);
</script>""")
    doc.append('<div id=cols></div>')

    doc.append("""<audio id="pl"></audio><script>
let cur=null,ph=0,curCoord=null;const a=document.getElementById('pl');
a.loop=true;
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}ph=0;curCoord=null});
a.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';if(cur)cur.classList.add('loading')});
a.addEventListener('playing',()=>{document.getElementById('ld').textContent='';if(cur)cur.classList.remove('loading')});
// transport: play/pause + seekable playhead + time readout + download link (Kim 2026-07-20)
const pp=document.getElementById('pp'),seek=document.getElementById('seek'),tm=document.getElementById('tm'),dl=document.getElementById('dl'),trans=document.getElementById('trans');
const fmt=s=>{s=Math.max(0,s|0);return (s/60|0)+':'+String(s%60).padStart(2,'0')};
let seeking=false;
pp.addEventListener('click',()=>{if(a.paused){if(a.src)a.play()}else a.pause()});
a.addEventListener('play',()=>pp.innerHTML='&#9208;');
a.addEventListener('pause',()=>pp.innerHTML='&#9654;');
a.addEventListener('timeupdate',()=>{if(seeking||!a.duration)return;seek.value=Math.round(a.currentTime/a.duration*1000);tm.textContent=fmt(a.currentTime)+' / '+fmt(a.duration)});
a.addEventListener('durationchange',()=>{if(a.duration)tm.textContent=fmt(a.currentTime)+' / '+fmt(a.duration)});
seek.addEventListener('input',()=>{seeking=true;if(a.duration)tm.textContent=fmt(seek.value/1000*a.duration)+' / '+fmt(a.duration)});
seek.addEventListener('change',()=>{if(a.duration){a.currentTime=seek.value/1000*a.duration;ph=a.currentTime}seeking=false});
function seekAndPlay(pos){
 const go=()=>{try{const d=a.duration||1e9;a.currentTime=(pos>d-1)?0:Math.min(pos,d-0.05)}catch(e){}a.play()};
 if(a.readyState>=3){go();return}
 let done=false;const fire=()=>{if(done)return;done=true;go()};
 a.addEventListener('canplay',fire,{once:true});setTimeout(fire,1200)}
function startCell(el,f){
 document.getElementById('ld').textContent='loading…';el.classList.add('loading');
 a.pause();a.src='model_matrix/'+f;seekAndPlay(ph);cur=el;el.classList.add('playing');
 dl.href='model_matrix/'+f;dl.setAttribute('download',f);trans.classList.add('on');
 curCoord={col:el.dataset.col,cf:el.dataset.cf,w:el.dataset.w,pid:el.dataset.pid};
 if(window.metricsFromCell)metricsFromCell(el);}
// native-length overlay (Kim 2026-08-02 spec): with the header checkbox on, a cell click
// plays its native-training-length twin from MM.ngrid when one exists (terminal ckpts),
// else the 20s clip. The single per-ckpt audition line (data-cf="native") is untouched.
function effSrc(el){
 const f=el.dataset.src;
 if(!window.mnative||!mnative.checked||!MM.ngrid||el.dataset.cf==='native')return f;
 const st=colState[el.dataset.col];if(!st||!st.model||!st.ckpt)return f;
 return MM.ngrid[st.model+'|'+st.ckpt+'|'+el.dataset.cf+'|'+el.dataset.w+'|'+el.dataset.pid]||f;}
function play(el){const f=effSrc(el);if(!el.dataset.src)return;
 if(cur===el){a.pause();el.classList.remove('playing','loading');cur=null;curCoord=null;document.getElementById('ld').textContent='';return}
 if(cur)cur.classList.remove('playing','loading');
 startCell(el,f)}
// After any re-render (checkpoint/model switch OR the 90s auto-refresh) re-bind the
// playing state to the SAME (column,cfg,strength,prompt) cell. If that cell now points
// at a different file (i.e. the checkpoint changed), switch to it and CONTINUE from the
// same playhead — A/B the same moment across checkpoints (Kim 2026-07-12).
function reattach(){
 if(!curCoord)return;
 const q='.cell.have[data-col="'+curCoord.col+'"][data-cf="'+curCoord.cf+'"][data-w="'+curCoord.w+'"][data-pid="'+CSS.escape(curCoord.pid)+'"]';
 const el=document.querySelector(q);
 if(!el){cur=null;return}                       // analogous cell gone -> leave audio as-is
 cur=el;el.classList.add('playing');
 const ef=effSrc(el);
 if(!a.src.endsWith('/'+ef)){               // different clip => checkpoint (or native toggle) switched
  a.pause();a.src='model_matrix/'+ef;seekAndPlay(ph)}}
// Kim 2026-08-14: dim cells lacking the checked alt-render (grid-wide, not a re-render --
// pure CSS class toggle on <body> so it's instant and doesn't disturb the playing cell's DOM
// node/reattach()). Called on checkbox change AND after every render()/applyURL(), since
// setting .checked programmatically (restoring a shared link) does not fire 'change'.
function syncFilterClasses(){
 const nb=document.getElementById('mnative'),pb=document.getElementById('mptm');
 document.body.classList.toggle('filter-native',!!(nb&&nb.checked));
 document.body.classList.toggle('filter-ptm',!!(pb&&pb.checked));}
// toggling native mid-play swaps the current cell's clip in place, same playhead
window.addEventListener('load',()=>{const nb=document.getElementById('mnative');
 if(nb)nb.addEventListener('change',()=>{
  syncFilterClasses();
  if(!cur)return;const ef=effSrc(cur);
  if(!a.src.endsWith('/'+ef)){a.pause();a.src='model_matrix/'+ef;seekAndPlay(ph);
   dl.href='model_matrix/'+ef;dl.setAttribute('download',ef);}});
 const pb=document.getElementById('mptm');
 if(pb)pb.addEventListener('change',syncFilterClasses);});
const labels=Object.keys(MM.models);
function ckptsFor(m){return MM.models[m]?MM.models[m].ckpts:[]}
function render(){
 const wrap=document.getElementById('cols');wrap.innerHTML='';
 for(let c=0;c<4;c++){
  const st=colState[c];const div=document.createElement('div');div.className='col';
  let h='<select onchange="colState['+c+'].model=this.value;colState['+c+'].ckpt=null;render()">';
  h+='<option value="">— model —</option>';
  for(const m of labels){const lit=ckptsFor(m).length>0;
   h+='<option class="'+(lit?'lit':'unlit')+'" value="'+m+'"'+(st.model===m?' selected':'')+'>'+m+(lit?' ●':'')+'</option>'}
  h+='</select>';
  if(st.model){const info=MM.models[st.model];const cks=info.ckpts;
   h+='<select onchange="colState['+c+'].ckpt=this.value;render()"><option value="">— checkpoint —</option>';
   for(const k of cks)h+='<option class=lit value="'+k+'"'+(st.ckpt===k?' selected':'')+'>'+k+' ●</option>';
   if(!cks.length)h+='<option disabled>(none rendered yet)</option>';
   h+='</select>';
   const cm=info.commentary;
   if(cm){
    // Schema entry: collapsed-by-default <details>. At rest only the one_liner summary shows
    // (compact, uniform height -> preserves the constant-header / aligned-prompt-grid invariant,
    // Kim 2026-07-22); the reader clicks to expand to full height. The empty legacy recipe/tdata
    // labels are folded IN here (G eyeball 2026-07-30: don't show two empty labels above a real box).
    h+='<details class=cmt><summary class=cmt-one>'+(cm.one_liner||'commentary')+'</summary><div class=cmt-body>';
    if(cm.why)h+='<div class=cmt-row><b>why:</b> '+cm.why+'</div>';
    if(cm.recipe&&typeof cm.recipe==="object"){h+='<div class=cmt-row><b>recipe:</b><ul class=cmt-rec>';
     for(const k in cm.recipe){if(cm.recipe[k])h+='<li><b>'+k+':</b> '+cm.recipe[k]+'</li>';}h+='</ul></div>';}
    else if(info.recipe)h+='<div class=cmt-row><b>recipe:</b> '+info.recipe+'</div>';
    if(info.training_data)h+='<div class=cmt-row><b>training data:</b> '+info.training_data+'</div>';
    if(cm.compare_against&&cm.compare_against.length){h+='<div class=cmt-row><b>compare vs:</b> '+
     cm.compare_against.map(function(c){return c.target+' <span class=cmt-ax>('+(c.axis||'')+')</span>';}).join(', ')+'</div>';}
    if(cm.verdict)h+='<div class=cmt-row><b>verdict:</b> '+cm.verdict+'</div>';
    if(st.ckpt)h+='<div class=cmt-row><b>checkpoint:</b> '+st.ckpt+'</div>';
    if(cm.status)h+='<div class=cmt-status>'+cm.status+'</div>';
    h+='</div></details>';
   }else{
    h+='<div class=recipe><b>recipe:</b> '+(info.recipe||'—')+(st.ckpt?('<br><b>checkpoint:</b> '+st.ckpt):'')+
       (info.note?('<br><i>'+info.note+'</i>'):'')+'</div>';
    h+='<div class=tdata><b>training data:</b> '+(info.training_data||'—')+'</div>';
   }
   h+='<div class=covwrap><div class=cov>'+info.family+' · '+cks.length+' ckpt(s) rendered</div>';
   if(st.ckpt&&MM.gf){const g=MM.gf[st.model+'|'+st.ckpt];
    if(g){const pct=g[0],col=pct>=60?'#5d9':(pct>=40?'#ca7':'#a66');
     h+='<div class=cov style="color:'+col+'" title="fraction of this checkpoint\\'s cells with Audiobox CE>=6.0 — a distributional verdict, not good/bad (Kim 2026-07-12)">&#9733; good-fraction '+pct+'% <span style="color:#778">('+g[1]+' cells, CE&ge;6)</span></div>'}}
   if(st.ckpt&&MM.native){const nv=MM.native[st.model+'|'+st.ckpt];
    if(nv){h+='<div class=cov><span class="cell have" style="display:inline-block;width:auto;padding:1px 6px" '+
     'data-src="'+nv.file+'" data-col="'+c+'" data-cf="native" data-w="native" data-pid="native" '+
     'onclick="play(this)">&#9654;</span> native length ('+nv.duration+'s, '+
     'the size this checkpoint was trained on — vs the fixed 20s grid above/below)</div>'}}
   h+='</div>';  // .covwrap — fixed height so the pgrid starts at the same Y in every column
   if(st.ckpt){h+='<div class=pgrid>';
    // already-a-_ptm column: nothing to dim against for the "post-trained" checkbox --
    // you're already looking at the post-trained render, same suppression logic as
    // dora_table's P marker (mislabeling "the base sibling also has this cell" as "missing
    // post-trained" would be backwards).
    const ptmSib=st.model.endsWith('_ptm')?null:st.model+'_ptm';
    for(const pid of Object.keys(MM.prompts)){
     // Zero coverage at the CURRENT cfg/w settings: GREY the prompt's LABEL with a hint
     // instead of HIDING it — hiding non-bracket prompts at bracket-only settings reads
     // as data loss (Kim 2026-07-13). ALWAYS render the full (all-miss) table too, so a
     // prompt occupies the SAME height in every column and the same prompt lands on the
     // same horizontal line across models (Kim 2026-07-22 alignment fix; supersedes the
     // 07-13 label-only path that made empty rows shorter than populated ones).
     const anyCell=MM.cfgs.some(cf=>MM.strengths.some(w=>(st.model+'|'+st.ckpt+'|'+cf+'|'+w+'|'+pid) in MM.data));
     const hint=anyCell?'':' <span style="color:#a66;font-style:italic">· no clips at these settings</span>';
     h+='<div class=plabel'+(anyCell?'':' style="opacity:.4"')+' title="'+MM.prompts[pid].replace(/"/g,'&quot;')+'">'+pid+' — '+MM.prompts[pid].slice(0,60)+hint+'</div>';
     h+='<table class=mini><tr><th></th>';
     for(const w of MM.strengths)h+='<th>w'+w+'</th>';h+='</tr>';
     for(const cf of MM.cfgs){h+='<tr><th>cfg'+cf+'</th>';
      for(const w of MM.strengths){
       const key=st.model+'|'+st.ckpt+'|'+cf+'|'+w+'|'+pid;const f=MM.data[key];
       if(f){
        const hasNat=!!(MM.ngrid&&MM.ngrid[key]);
        const hasPtm=!ptmSib||!!MM.data[ptmSib+'|'+st.ckpt+'|'+cf+'|'+w+'|'+pid];
        h+='<td class="cell have'+(hasNat?'':' no-nat')+(hasPtm?'':' no-ptm')+'" data-src="'+f+'" data-col="'+c+'" data-cf="'+cf+'" data-w="'+w+'" data-pid="'+pid+'" onclick="play(this)">&#9654;</td>';
       }else h+='<td class="cell miss">·</td>'}
      h+='</tr>'}
     h+='</table>'}
    h+='</div>'}
  }
  div.innerHTML=h;wrap.appendChild(div)}reattach();
 if(window.syncFilterClasses)syncFilterClasses();  // cheap + idempotent; covers any caller that skips the checkbox handlers
 if(window.syncURL)syncURL();}   // every column change re-renders -> URL always shareable
const colState=[{model:null,ckpt:null},{model:null,ckpt:null},{model:null,ckpt:null},{model:null,ckpt:null}];
// ── SHAREABLE SELECTION VIA THE ADDRESS BAR (Kim 2026-08-05) ────────────────────────────────
// The 4-column selection + native toggle live in the URL hash, so any configuration can be
// copied out of the address bar and sent to someone else (or bookmarked). Hash, not query:
// it never round-trips to the server and survives the static host untouched.
// Format: #c=<model>~<ckpt>|<model>~<ckpt>|...  &nat=1
function syncURL(){
 const parts=colState.map(s=>s.model?(encodeURIComponent(s.model)+'~'+encodeURIComponent(s.ckpt||'')):'');
 let h='c='+parts.join('|');
 const nb=document.getElementById('mnative'); if(nb&&nb.checked)h+='&nat=1';
 const pb=document.getElementById('mptm'); if(pb&&pb.checked)h+='&ptm=1';
 // replaceState, not assignment: writing location.hash would push a history entry per click
 // and turn Back into an undo-one-column crawl.
 try{history.replaceState(null,'','#'+h);}catch(e){}}
function applyURL(){
 const h=(location.hash||'').replace(/^#/,''); if(!h)return false;
 const q={}; h.split('&').forEach(kv=>{const i=kv.indexOf('=');if(i>0)q[kv.slice(0,i)]=kv.slice(i+1);});
 if(q.c){q.c.split('|').forEach((seg,i)=>{
   if(i>3||!seg)return; const [m,k]=seg.split('~');
   colState[i].model=decodeURIComponent(m||'')||null;
   colState[i].ckpt=decodeURIComponent(k||'')||null;});}
 if(q.nat==='1'){const nb=document.getElementById('mnative'); if(nb)nb.checked=true;}
 if(q.ptm==='1'){const pb=document.getElementById('mptm'); if(pb)pb.checked=true;}
 return !!q.c;}
// EVEN CHECKPOINT SPREAD (Kim 2026-08-05: "in a lack of the scores ... an evenly sampled
// selection of checkpoints"). Unscored models have no metrics to rank their checkpoints by,
// so the useful default is coverage: first, last, and evenly-spaced middles across the run,
// which is what you want when judging a training trajectory by ear.
function spreadCkpts(){
 const m=(colState.find(s=>s.model)||{}).model; if(!m)return;
 const cks=((MM.models[m]||{}).ckpts)||[]; if(!cks.length)return;
 for(let c=0;c<4;c++){
  colState[c].model=m;
  colState[c].ckpt=cks.length===1?cks[0]
    :cks[Math.round(c*(cks.length-1)/3)];}   // c=0 -> first, c=3 -> last, 1/2 evenly between
 render();}
function copyShareLink(){
 syncURL();
 const u=location.href;
 const done=()=>{const b=document.getElementById('mshare');if(b){const t=b.textContent;b.textContent='copied ✓';setTimeout(()=>b.textContent=t,1400);}};
 if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(u).then(done,done);
 else{const ta=document.createElement('textarea');ta.value=u;document.body.appendChild(ta);ta.select();
      try{document.execCommand('copy');}catch(e){} ta.remove(); done();}}
window.addEventListener('hashchange',()=>{if(applyURL())render();});
applyURL();
render();
</script>""")
    # Notes widget REMOVED 2026-08-04 (Kim): both the page-level box and the context-aware
    # panel moved to dora_table.html, the table he actually auditions from. Public visitors
    # were never going to leave notes on the matrix, so one comment surface -- on the page
    # where listening happens -- beats two. Widget + write-only boundary unchanged; see
    # eval/build_dora_table_page.py ("NOTES scope") and web/comments.js.
    # ── Per-clip METRICS feature (Kim 2026-07-30; data = G's clip_scores.json, directions =
    # F's metric_meta). Panel lives OUTSIDE #cols so the 90s auto-refresh never wipes it.
    # (1) preload button warms the 4 selected columns' clips; (2) a metrics grid = the playing
    # clip's scores + its equivalents (same cfg/w/prompt) across the 4 columns; (3) a popup =
    # ALL board-wide equivalents ranked by a chosen metric; (4) a HYBRID column, min-max
    # normalized PER METRIC across the comparison set, direction-adjusted (lower-better inverted),
    # weighted by user sliders. Scores fetched lazily on first play (14.7 MB / 3.2 MB gzip).
    doc.append("""
<style>
.mpanel{max-width:1000px;margin:14px 0;padding:10px 12px;border:1px solid #2a2a30;border-radius:6px;
  background:#141418;font:13px system-ui;color:#e0e0e0}
.mpanel-hd{font-size:12px;color:#9cf;margin-bottom:8px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.mp-scope{color:#7ed}.mp-hint{color:#667;font-style:italic}
.mp-btn{background:#1d2733;color:#9cf;border:1px solid #356;border-radius:4px;padding:2px 9px;
  font-size:11.5px;cursor:pointer}.mp-btn:hover{background:#24303e}.mp-btn:disabled{opacity:.5;cursor:default}
table.mtab{border-collapse:collapse;width:100%;font-size:11px;margin:2px 0}
.mtab th,.mtab td{border:1px solid #26262c;padding:2px 5px;text-align:center;white-space:nowrap}
.mtab th{color:#8a9;font-weight:500}.mtab td.mlab{text-align:left;color:#cde;max-width:190px;overflow:hidden;text-overflow:ellipsis}
.mtab tr.mplaying td{background:#1d2b1f}.mtab td.mhy{font-weight:600;color:#cde}
.mp-weights{margin:9px 0 2px;display:flex;flex-wrap:wrap;gap:9px 14px;font-size:11px;color:#9ab;align-items:center}
.mp-w{display:flex;align-items:center;gap:4px}.mp-w input{width:74px;accent-color:#7cf}
.mp-w .mp-wl{cursor:help}.mp-w .mp-wv{color:#7cf;width:14px;display:inline-block}
.mp-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:50;align-items:flex-start;justify-content:center}
.mp-overlay.on{display:flex}
.mp-modal{background:#16181c;border:1px solid #333;border-radius:8px;margin-top:5vh;max-height:86vh;width:min(880px,94vw);
  overflow:auto;padding:14px 16px}
.mp-modal h3{font-size:14px;margin:0 0 3px;color:#cde}.mp-modal .mp-sub{color:#899;font-size:12px;margin-bottom:8px}
.mp-close{float:right;cursor:pointer;color:#9cf;font-size:16px;border:0;background:none}
.mp-rank{color:#678}.mp-play{cursor:pointer;color:#7cf}.mp-selrow td{background:#1d2b1f}
</style>
<div class="mpanel" id="mpanel">
 <div class="mpanel-hd">Per-clip metrics &mdash;
  <span id="mscope" class="mp-hint">click a clip cell above to score it against its siblings</span>
  <button class="mp-btn" id="mpre" onclick="preload4()" title="fetch the 4 selected columns' clips into browser cache so switching cells is instant">preload columns</button>
  <button class="mp-btn" id="mpop" onclick="openEquiv()" style="display:none">compare all versions &#9656;</button>
 </div>
 <div id="mgrid"></div>
 <div id="mweights" class="mp-weights"></div>
</div>
<div class="mp-overlay" id="moverlay" onclick="if(event.target===this)closeEquiv()">
 <div class="mp-modal">
  <button class="mp-close" onclick="closeEquiv()">&times;</button>
  <h3 id="mpop-title">All versions</h3>
  <div class="mp-sub">Every rendered clip at this cfg / strength / prompt across the whole zoo, ranked.
   Sort: <select id="mpop-sort" onchange="renderEquiv()"></select> &nbsp; click &#9654; to play any of them.</div>
  <div id="mpop-body"></div>
 </div>
</div>
<script>
let MSC=null,byFile=null,byEquiv=null,MMETA=null,mLoading=false,mWeights={},mCurEl=null;
const SCORE_SHORT={clap_matched:'CLAP',clap_margin_far:'mrg',beats_all_far:'beat',retrieval_rank:'rank',
 ce:'CE',pq:'PQ',cu:'CU',flatness:'flat',crest:'crest'};
async function loadScores(){
 if(MSC||mLoading)return MSC; mLoading=true;
 try{
  const r=await fetch('model_matrix/clip_scores.json',{cache:'force-cache'});
  const j=await r.json(); MMETA=j.metric_meta; const cols=j.columns;
  byFile=new Map(); byEquiv=new Map();
  for(const row of j.clips){const o={}; for(let i=0;i<cols.length;i++)o[cols[i]]=row[i];
   byFile.set(o.file,o);
   const ek=o.cfg+'|'+o.strength+'|'+o.prompt_id;
   let arr=byEquiv.get(ek); if(!arr){arr=[];byEquiv.set(ek,arr);} arr.push(o);}
  MSC=j;
  for(const m in MMETA) mWeights[m]=(MMETA[m].category==='score')?1:0;
  buildWeightUI();
 }catch(e){console.log('[metrics] scores load failed',e);}
 mLoading=false; return MSC;
}
function hybridMetrics(){return Object.keys(MMETA).filter(m=>mWeights[m]>0&&MMETA[m].direction);}
function normFn(clips,m){
 const dir=MMETA[m].direction,vals=clips.map(c=>c[m]).filter(v=>v!=null&&!isNaN(v));
 if(!vals.length)return()=>null; const lo=Math.min(...vals),hi=Math.max(...vals);
 return c=>{let v=c[m]; if(v==null||isNaN(v))return null; let n=(hi>lo)?(v-lo)/(hi-lo):0.5; return dir==='lower'?1-n:n;};}
function hybridScores(clips){
 const ms=hybridMetrics(),norms={}; for(const m of ms)norms[m]=normFn(clips,m);
 const out=new Map();
 for(const c of clips){let s=0,w=0; for(const m of ms){const n=norms[m](c); if(n!=null){s+=mWeights[m]*n;w+=mWeights[m];}} out.set(c,w?s/w:null);}
 return out;}
function heat(n){if(n==null)return'';const h=Math.round(n*120);return'style="color:hsl('+h+',60%,68%)"';}
function fmtv(v){if(v==null||isNaN(v))return'&middot;';return Math.abs(v)>=100?v.toFixed(0):Math.abs(v)>=1?v.toFixed(2):v.toFixed(3);}
function buildWeightUI(){
 const box=document.getElementById('mweights'); if(!MMETA){box.innerHTML='';return;}
 const ms=Object.keys(MMETA).filter(m=>MMETA[m].direction);  // scorable = has a direction
 let h='<b style="color:#8a9">hybrid weights:</b>';
 for(const m of ms){const md=MMETA[m];
  h+='<span class=mp-w><span class=mp-wl title="'+md.label+' ('+md.direction+'-is-better)">'+(SCORE_SHORT[m]||m)+'</span>'
    +'<input type=range min=0 max=3 step=0.5 value="'+(mWeights[m]||0)+'" oninput="setW(\\''+m+'\\',this.value)">'
    +'<span class=mp-wv id="wv-'+m+'">'+(mWeights[m]||0)+'</span></span>';}
 box.innerHTML=h;}
function setW(m,v){mWeights[m]=parseFloat(v);const el=document.getElementById('wv-'+m);if(el)el.textContent=v;
 renderMetrics(); if(document.getElementById('moverlay').classList.contains('on'))renderEquiv();}
function eqKeyOf(el){return el.dataset.cf+'|'+el.dataset.w+'|'+el.dataset.pid;}
function clipAt(model,ckpt,cf,w,pid){const f=MM.data[model+'|'+ckpt+'|'+cf+'|'+w+'|'+pid];return f?(byFile&&byFile.get(f)):null;}
async function metricsFromCell(el){
 if(!el||el.dataset.cf==='native'){return;} mCurEl=el; await loadScores(); renderMetrics();}
function renderMetrics(){
 const el=mCurEl,sc=document.getElementById('mscope'),grid=document.getElementById('mgrid'),pop=document.getElementById('mpop');
 if(!el||!byFile||el.dataset.cf==='native'){return;}
 const cf=el.dataset.cf,w=el.dataset.w,pid=el.dataset.pid,pcol=el.dataset.col;
 sc.className='mp-scope'; sc.textContent='cfg'+cf+' · w'+w+' · '+pid+'  (playing column '+(+pcol+1)+')';
 const rows=[];
 for(let c=0;c<4;c++){const st=colState[c]; if(!st.model||!st.ckpt){rows.push(null);continue;}
  rows.push({col:c,st,o:clipAt(st.model,st.ckpt,cf,w,pid)});}
 const present=rows.filter(r=>r&&r.o).map(r=>r.o);
 const metrics=Object.keys(MMETA).filter(m=>MMETA[m].category==='score');
 const norms={}; for(const m of metrics)norms[m]=normFn(present,m);
 const hy=hybridScores(present);
 let h='<table class=mtab><tr><th class=mlab>column</th>';
 for(const m of metrics)h+='<th title="'+MMETA[m].label+'">'+(SCORE_SHORT[m]||m)+'</th>';
 h+='<th title="min-max normalized per metric across the visible set, direction-adjusted, weighted">HYBRID</th></tr>';
 for(const r of rows){
  if(!r||!r.st.model){h+='<tr><td class=mlab style="opacity:.4">(empty column)</td><td colspan="'+(metrics.length+1)+'"></td></tr>';continue;}
  const playing=(''+r.col===''+pcol);
  h+='<tr class="'+(playing?'mplaying':'')+'"><td class=mlab title="'+r.st.model+' ▸ '+r.st.ckpt+'">'+(playing?'&#9654; ':'')+r.st.model+' <span style="color:#678">'+r.st.ckpt+'</span></td>';
  if(!r.o){h+='<td colspan="'+(metrics.length+1)+'" style="color:#556">no clip at these settings</td></tr>';continue;}
  for(const m of metrics)h+='<td '+heat(norms[m](r.o))+'>'+fmtv(r.o[m])+'</td>';
  const hs=hy.get(r.o); h+='<td class=mhy '+heat(hs)+'>'+(hs==null?'&middot;':(hs*100).toFixed(0))+'</td></tr>';}
 h+='</table>';
 grid.innerHTML=h; pop.style.display='';}
// ── board-wide equivalents popup ────────────────────────────────────────────
function openEquiv(){if(!mCurEl||!byEquiv)return; document.getElementById('moverlay').classList.add('on');
 const sel=document.getElementById('mpop-sort');
 if(!sel.options.length){let o='<option value="__hy">HYBRID</option>';
  for(const m in MMETA)if(MMETA[m].direction)o+='<option value="'+m+'">'+MMETA[m].label+'</option>';
  sel.innerHTML=o;}
 renderEquiv();}
function closeEquiv(){document.getElementById('moverlay').classList.remove('on');}
function renderEquiv(){
 const el=mCurEl; if(!el)return; const ek=eqKeyOf(el);
 const clips=(byEquiv.get(ek)||[]).slice();
 document.getElementById('mpop-title').textContent='All versions · cfg'+el.dataset.cf+' · w'+el.dataset.w+' · '+el.dataset.pid+' ('+clips.length+')';
 const sortm=document.getElementById('mpop-sort').value;
 const hy=hybridScores(clips);
 const val=(sortm==='__hy')?(c=>hy.get(c)):(c=>{const d=MMETA[sortm].direction;const v=c[sortm];return v==null?null:(d==='lower'?-v:v);});
 clips.sort((a,b)=>{const va=val(a),vb=val(b);if(va==null)return 1;if(vb==null)return -1;return vb-va;});
 const show=['ce','pq','cu','clap_matched','retrieval_rank','flatness'];
 let h='<table class=mtab><tr><th class=mp-rank>#</th><th class=mlab>model ▸ ckpt</th>';
 for(const m of show)h+='<th title="'+MMETA[m].label+'">'+(SCORE_SHORT[m]||m)+'</th>';
 h+='<th>HYBRID</th><th></th></tr>';
 const curf=mCurEl.dataset.src;
 clips.forEach((c,i)=>{const isc=(c.file===curf);
  h+='<tr class="'+(isc?'mp-selrow':'')+'"><td class=mp-rank>'+(i+1)+'</td><td class=mlab title="'+c.model+' ▸ '+c.ckpt+'">'+c.model+' <span style="color:#678">'+c.ckpt+'</span></td>';
  for(const m of show)h+='<td>'+fmtv(c[m])+'</td>';
  const hs=hy.get(c); h+='<td class=mhy>'+(hs==null?'&middot;':(hs*100).toFixed(0))+'</td>';
  h+='<td class=mp-play onclick="playFile(\\''+c.file+'\\')" title="play this one">&#9654;</td></tr>';});
 document.getElementById('mpop-body').innerHTML='<table class=mtab>'+h.slice(h.indexOf('<tr>'))+'</table>';}
// play an arbitrary clip by filename (may be outside the 4 selected columns)
function playFile(f){
 if(typeof a==='undefined')return;
 if(cur){cur.classList.remove('playing','loading');} cur=null;
 a.pause(); a.src='model_matrix/'+f; seekAndPlay(ph);
 document.getElementById('dl').href='model_matrix/'+f; document.getElementById('dl').setAttribute('download',f);
 document.getElementById('trans').classList.add('on');}
// ── preload the 4 selected columns' clips ───────────────────────────────────
async function preload4(){
 const btn=document.getElementById('mpre'); const files=new Set();
 for(let c=0;c<4;c++){const st=colState[c]; if(!st.model||!st.ckpt)continue;
  const pfx=st.model+'|'+st.ckpt+'|';
  for(const k in MM.data)if(k.startsWith(pfx))files.add(MM.data[k]);
  const nv=MM.native&&MM.native[st.model+'|'+st.ckpt]; if(nv)files.add(nv.file);}
 const list=[...files]; if(!list.length){btn.textContent='no clips to preload';return;}
 btn.disabled=true; let done=0;
 const batch=6;
 for(let i=0;i<list.length;i+=batch){
  await Promise.all(list.slice(i,i+batch).map(f=>fetch('model_matrix/'+f,{cache:'force-cache'}).catch(()=>{})));
  done=Math.min(i+batch,list.length); btn.textContent='preloading '+done+'/'+list.length;}
 btn.textContent='preloaded '+list.length+' ✓'; btn.disabled=false;}
</script>
""")
    doc.append("<footer style='margin-top:18px;color:#666;font-size:11px'>aavepyora.online · evals · model matrix</footer></body></html>")
    OUT.write_text("".join(doc))
    print(f"wrote {OUT}: {len(models)} models, {len(entries)} clips in manifest, {len(prompts)} prompts")


if __name__ == "__main__":
    main()
