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

STAGING = Path.home() / ".cache/evals_aac"
MANIFEST = STAGING / "model_matrix" / "manifest.jsonl"
OUT = STAGING / "model_matrix.html"
CFGS = (1, 7, 16)
STRENGTHS = (0.6, 1.0, 1.5)

CSS = """
body{font:13px system-ui;margin:14px;background:#101012;color:#e0e0e0}
h1{font-size:17px;margin:0 0 4px}a{color:#7cf}
.how{color:#cba;font-size:12px;line-height:1.5;margin:6px 0 12px;max-width:1150px}
#hdr{position:sticky;top:0;z-index:9;background:#16181c;padding:7px 12px;margin:-14px -14px 12px;
border-bottom:1px solid #2a2a30;font-size:13px}#np{color:#cde}#pos{color:#888}
#cols{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:start}
.col{background:#141417;border:1px solid #242428;border-radius:8px;padding:10px}
select{width:100%;background:#1b1b20;color:#dde;border:1px solid #333;border-radius:4px;
padding:4px;margin:2px 0;font-size:12px}
option.lit{color:#7f7}option.unlit{color:#777}
.recipe{font-size:11px;color:#9ab;line-height:1.45;margin:6px 0;border-left:2px solid #368;
padding-left:7px;min-height:52px}
.tdata{font-size:11px;color:#a98;line-height:1.4;margin:4px 0}
.pgrid{margin:8px 0}.plabel{font-size:11px;color:#8a9;margin:8px 0 2px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
table.mini{border-collapse:collapse;width:100%}
.mini td,.mini th{border:1px solid #26262c;text-align:center;font-size:10px;color:#889;padding:2px}
.cell{cursor:pointer;background:#191920}.cell:hover{outline:1px solid #7cf}
.cell.have{background:#1d2b1f;color:#9f9}.cell.miss{color:#555;cursor:default}
.cell.playing{outline:2px solid #5d5 !important}
.cov{font-size:11px;color:#7a7;margin:2px 0}
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
    cov = {}           # model -> {ckpt: n_clips}
    for e in entries:
        pid = str(e.get("prompt_id"))
        prompts.setdefault(pid, e.get("prompt_text", pid))
        # a cell is playable only when its m4a actually exists in staging --
        # G's manifest runs ahead of his transcode; dead cells are worse than
        # briefly-missing ones (they'd 404-cache in the browser)
        if not (STAGING / "model_matrix" / e["file"]).exists():
            continue
        key = f'{e["model"]}|{e["ckpt"]}|{e["cfg"]}|{e["strength"]}|{pid}'
        data[key] = e["file"]
        cov.setdefault(e["model"], {}).setdefault(e["ckpt"], 0)
        cov[e["model"]][e["ckpt"]] += 1

    meta = {}
    for m in models:
        ov = overrides.get(m["label"], {})
        meta[m["label"]] = {
            "family": m["family"], "n_ckpts": m["n_ckpts"],
            "recipe": ov.get("recipe", ""), "training_data": ov.get("training_data", ""),
            "note": ov.get("note", ""), "ckpts": sorted(cov.get(m["label"], {}).keys()),
        }

    n_models_lit = sum(1 for v in cov.values() if v)
    doc = [f"<!doctype html><html><head><meta charset=utf-8><title>Model matrix</title><style>{CSS}</style></head><body>"]
    doc.append('<div id=hdr>&#9654; <b id=np>pick a model per column, click a cell</b> <span id=pos></span>'
               ' &nbsp;·&nbsp; <span style="color:#888">same playhead across every cell; re-click stops</span></div>')
    doc.append('<h1>Model matrix — every trained model × checkpoint × cfg × strength, side by side</h1>'
               '<a href=index.html>← evals</a> · <a href=models.html>models index</a>')
    doc.append(f'<div class=how><b>What this is:</b> the listening matrix over the whole model zoo. '
               f'Each of the 4 columns is a preset: pick a MODEL, then a CHECKPOINT (green = rendered, '
               f'grey = not yet). Below, each prompt shows a 3×3 grid — rows cfg 1/7/16 (how hard the '
               f'prompt steers), columns DoRA strength 0.6/1.0/1.5 (how strongly the adapter is applied; '
               f'n/a for base). All cells share ONE playhead, so switching mid-play A/Bs the exact same '
               f'moment. Recipes + training data under each header — this page doubles as the record of '
               f'how each model was made. Coverage now: <b>{n_models_lit}/{len(models)} models have '
               f'renders</b>{" — awaiting the overnight run" if not entries else ""}.</div>')

    payload = {"models": meta, "data": data, "prompts": prompts,
               "cfgs": list(CFGS), "strengths": list(STRENGTHS)}
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
  const data={}, prompts={}, cov={};
  for(const ln of txt.split('\\n')){ if(!ln.trim()) continue;
   let e; try{e=JSON.parse(ln)}catch(_){continue}
   const pid=String(e.prompt_id); if(!(pid in prompts)) prompts[pid]=e.prompt_text||pid;
   data[e.model+'|'+e.ckpt+'|'+e.cfg+'|'+e.strength+'|'+pid]=e.file;
   (cov[e.model]=cov[e.model]||{})[e.ckpt]=1; }
  MM.data=data; MM.prompts=prompts;
  for(const m of Object.keys(MM.models)) MM.models[m].ckpts=Object.keys(cov[m]||{}).sort();
  render();
 }catch(_){/* file:// or offline -> embedded snapshot stands */}
}
setInterval(refreshMM, 90000);  // live page self-updates every 90 s
window.addEventListener('load', refreshMM);
</script>""")
    doc.append('<div id=cols></div>')

    doc.append("""<audio id="pl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('pl');
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}ph=0});
function seekAndPlay(pos){
 const go=()=>{try{const d=a.duration||1e9;a.currentTime=(pos>d-1)?0:Math.min(pos,d-0.05)}catch(e){}a.play()};
 if(a.readyState>=3){go();return}
 let done=false;const fire=()=>{if(done)return;done=true;go()};
 a.addEventListener('canplay',fire,{once:true});setTimeout(fire,1200)}
function play(el){const f=el.dataset.src;if(!f)return;
 if(cur===el){a.pause();el.classList.remove('playing');cur=null;return}
 if(cur)cur.classList.remove('playing');
 a.pause();a.src='model_matrix/'+f;seekAndPlay(ph);cur=el;el.classList.add('playing')}
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
   h+='<div class=recipe><b>recipe:</b> '+(info.recipe||'—')+(st.ckpt?('<br><b>checkpoint:</b> '+st.ckpt):'')+
      (info.note?('<br><i>'+info.note+'</i>'):'')+'</div>';
   h+='<div class=tdata><b>training data:</b> '+(info.training_data||'—')+'</div>';
   h+='<div class=cov>'+info.family+' · '+cks.length+' ckpt(s) rendered</div>';
   if(st.ckpt){h+='<div class=pgrid>';
    for(const pid of Object.keys(MM.prompts)){
     h+='<div class=plabel title="'+MM.prompts[pid].replace(/"/g,'&quot;')+'">'+pid+' — '+MM.prompts[pid].slice(0,60)+'</div>';
     h+='<table class=mini><tr><th></th>';
     for(const w of MM.strengths)h+='<th>w'+w+'</th>';h+='</tr>';
     for(const cf of MM.cfgs){h+='<tr><th>cfg'+cf+'</th>';
      for(const w of MM.strengths){
       const key=st.model+'|'+st.ckpt+'|'+cf+'|'+w+'|'+pid;const f=MM.data[key];
       h+=f?'<td class="cell have" data-src="'+f+'" onclick="play(this)">&#9654;</td>':'<td class="cell miss">·</td>'}
      h+='</tr>'}
     h+='</table>'}
    h+='</div>'}
  }
  div.innerHTML=h;wrap.appendChild(div)}}
const colState=[{model:null,ckpt:null},{model:null,ckpt:null},{model:null,ckpt:null},{model:null,ckpt:null}];
render();
</script>""")
    doc.append("<footer style='margin-top:18px;color:#666;font-size:11px'>aavepyora.online · evals · model matrix</footer></body></html>")
    OUT.write_text("".join(doc))
    print(f"wrote {OUT}: {len(models)} models, {len(entries)} clips in manifest, {len(prompts)} prompts")


if __name__ == "__main__":
    main()
