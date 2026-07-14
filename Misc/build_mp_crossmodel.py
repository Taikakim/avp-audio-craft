#!/usr/bin/env python3
"""
build_mp_crossmodel.py -- append the cross-model checkpoint-pulldown section to mp.html.

CONTINUITY's mp_crossmodel/ dataset (48 clips: 8 checkpoints x 6 prompts, uniform
seed1234/st10/steps16/cfg5/dur47) is a fundamentally different shape than mp.html's
existing content (gain x density grids per optimizer run) -- so this is a NEW
self-contained section appended before </body>, not a merge into the existing
`D.sets` structure. Own CSS/JS namespace (xm* prefix) to avoid colliding with the
page's existing cell()/el()/mark()/up() functions.

Kim's UI rule (2026-07-09): prompts + recipe params must be visible at a glance,
not hover/click-only -- so the 6-prompt legend is always-visible static HTML, and
the per-checkpoint training-recipe line updates with the pulldown (not hidden
behind a tooltip).

Leak discipline (CONTINUITY's heads-up, 2026-07-10): mp_checkpoint_recipes.json +
mp_crossmodel/run_meta.json carry absolute Mantu paths + ckpt filenames (needed
locally, e.g. by a human reading the raw JSON) -- this script emits NEITHER into
the HTML. Script provenance shows as a relative repo path (text, not a file://
link -- an absolute file:// URL would itself leak the local directory structure).

Run: python3 Misc/build_mp_crossmodel.py
"""
import html
import json
import re
from pathlib import Path

MANTU_RUN_META = Path("/run/media/kim/Mantu/sa3_lora_runs/mp_crossmodel/run_meta.json")
RECIPES = Path("/home/kim/Projects/SAO/eval/mp_checkpoint_recipes.json")
MP_HTML = Path("/home/kim/riffer-evals/mp.html")
CLIPS_DIR = Path("/home/kim/riffer-evals/clips_mp_crossmodel")

FRIENDLY_LABEL = {
    "base": "Base (no adapter)",
    "orig_ep02": "Originals r16 — ep2 (early)",
    "orig_ep06f": "Originals r16 — ep6 (dense-window ladder)",
    "orig_ep31": "Originals r16 — ep31 (sweet-spot island)",
    "armG_ep14": "Arm G r128-adj — ep14 (low-LR)",
    "r64tiered_ep7": "r64-tiered — ep7 (caption-diversity cure)",
    "newstack_ep7": "Goa newstack r16 — ep7",
    "everything_ep7": "Everything r128 (evr1x) — ep7",
}

CKPT_PATH_RE = re.compile(r"^.*/(?P<run>[^/]+)/epoch=(?P<epoch>\d+)-step=(?P<step>\d+)\.ckpt$")

# free-text fields (note/script_note) can embed a raw ckpt filename inline (e.g.
# "...(epoch=7-step=12216.ckpt)") -- caught 2026-07-10 by leak-scan on the everything
# recipe's note. Structured fields (rank/lr/corpus/etc) are science and stay as-is;
# only prose needs this scrub.
_CKPT_FILENAME_RE = re.compile(r"epoch=\d+-step=\d+\.ckpt")


def redact_prose(s):
    return _CKPT_FILENAME_RE.sub("[checkpoint]", s)


def recipe_line(label, ckpt_path, recipes):
    if label == "base":
        return "medium-base, no adapter (upstream checkpoint)"
    m = CKPT_PATH_RE.match(ckpt_path)
    if not m:
        return "recipe not recovered"
    run_key = m["run"]
    r = recipes.get(run_key)
    if not r:
        return f"recipe not recovered (run key {run_key!r} not in mp_checkpoint_recipes.json)"
    parts = [
        f"rank {r['rank']}/α{r['lora_alpha']}",
        f"{r['optimizer']} lr {r['lr']}",
        f"epoch {m['epoch']} of {r['epochs']} (step {m['step']})",
        f"corpus: {r['corpus']}",
        f"base: {r['base_model']}",
    ]
    if r.get("note"):
        parts.append(redact_prose(r["note"]))
    line = " · ".join(parts)
    script = r.get("script_path")
    if script:
        line += f" · script: {script}"
    else:
        line += " · script: not committed (scratchpad chain, recipe reconstructed)"
    conf = r.get("confidence")
    if conf and conf != "found":
        line += f" [{conf}]"
    return line


def main():
    meta = json.load(open(MANTU_RUN_META))
    recipes = json.load(open(RECIPES))
    prompts = meta["prompts"]
    checkpoints = meta["checkpoints"]
    gen = meta["gen"]

    ckpt_order = ["base", "orig_ep02", "orig_ep06f", "orig_ep31", "armG_ep14",
                  "r64tiered_ep7", "newstack_ep7", "everything_ep7"]
    ckpt_order = [c for c in ckpt_order if c in checkpoints]

    prompt_order = ["goa1", "psy", "upbeat", "trig", "tstyle", "kimlong"]
    prompt_order = [p for p in prompt_order if p in prompts]

    data = {
        "prompts": prompts,
        "prompt_order": prompt_order,
        "checkpoints": {
            c: {
                "label": FRIENDLY_LABEL.get(c, c),
                "recipe": recipe_line(c, checkpoints[c], recipes),
                "clips": {
                    p: f"clips_mp_crossmodel/{c}__{p}__s{int(gen['seed'])}__st{int(gen['strength']*10)}.m4a"
                    for p in prompt_order
                }
            }
            for c in ckpt_order
        },
        "ckpt_order": ckpt_order,
        "gen": gen,
    }

    for c in ckpt_order:
        for p in prompt_order:
            f = MP_HTML.parent / data["checkpoints"][c]["clips"][p]
            if not f.exists():
                raise SystemExit(f"missing clip: {f}")

    prompt_legend = "".join(
        f'<div class=xmp><b>{html.escape(p)}</b>: {html.escape(prompts[p])}</div>'
        for p in prompt_order
    )

    css = (
        "#xmwrap{margin-top:22px;border-top:1px solid #2a2a30;padding-top:12px}"
        ".xmp{color:#9ec;font-size:12px;margin:2px 0}"
        ".xmp b{color:#7cf}"
        "#xmrecipe{background:#11161c;border:1px solid #243;border-left:3px solid #5d9;"
        "padding:7px 11px;font-size:12px;margin:8px 0;max-width:900px;color:#cde}"
        ".xmgrid{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}"
        ".xmcell{background:#18181b;border:1px solid #2a2a2e;border-radius:6px;padding:8px 12px;"
        "cursor:pointer;min-width:150px}"
        ".xmcell:hover{outline:1px solid #7cf}"
        ".xmcell.xmplay{outline:2px solid #5d5 !important}"
        ".xmcell b{color:#9ec;display:block;font-size:12px}"
    )

    body = (
        '<div id=xmwrap>'
        '<h2>Cross-model compare — 6 prompts x 8 checkpoints</h2>'
        f'<div class=tip>Uniform gen: steps {int(gen["steps"])}, cfg {gen["cfg"]}, '
        f'duration {gen["dur"]}s, seed {int(gen["seed"])}, DoRA strength {gen["strength"]}. '
        'Same 6 prompts rendered through every checkpoint below — pick a checkpoint, '
        'compare across prompts, or flip checkpoints to compare the same prompt across training.</div>'
        f'<div id=xmlegend>{prompt_legend}</div>'
        '<div class=ctl><span>checkpoint <select id=xmset></select></span></div>'
        '<div id=xmrecipe></div>'
        '<div id=xmgrid class=xmgrid></div>'
        '</div>'
    )

    js = (
        f'const XM={json.dumps(data, ensure_ascii=False)};'
        'let xmCur=null,xmAu=new Audio();'
        "function xmSafe(s){return ('' + s).replace(/[^A-Za-z0-9_]/g,'_');}"
        'function xmPlay(id,f,lbl){'
        # comment-scope hook (Kim: build once, drop everywhere): model = the
        # mp_crossmodel run dir, ckpt = pulldown key, clip = file — no-op until
        # the page carries the shared Notes panel (comment_notes_block)
        "if(window.noteSet)noteSet({model:'mp_crossmodel',"
        "ckpt:document.getElementById('xmset').value,clip:f.split('/').pop()});"
        "document.querySelectorAll('.xmcell').forEach(e=>e.classList.remove('xmplay'));"
        'if(xmCur===id){xmAu.pause();xmCur=null;'
        "document.getElementById('np').textContent='stopped';return;}"
        'const pos=(xmCur!==null&&!xmAu.paused)?xmAu.currentTime:0;'
        "xmCur=id;document.getElementById(id).classList.add('xmplay');"
        "document.getElementById('np').textContent='▶ '+lbl;"
        'xmAu.src=f;const go=()=>{try{xmAu.currentTime=((xmAu.duration&&pos>xmAu.duration-1)?0:Math.min(pos,(xmAu.duration||1e9)-0.05));}'
        'catch(e){}xmAu.play();};'
        "if(xmAu.readyState>=1)go();else xmAu.addEventListener('loadedmetadata',go,{once:true});"
        '}'
        'function xmUp(){'
        "const c=document.getElementById('xmset').value;const info=XM.checkpoints[c];"
        "document.getElementById('xmrecipe').innerHTML="
        "'<b>'+info.label+'</b><div style=\"margin-top:3px;color:#9aa\">'+info.recipe+'</div>';"
        "let h='';XM.prompt_order.forEach(p=>{const id='xm_'+xmSafe(c)+'_'+xmSafe(p);"
        "const f=info.clips[p];const lbl=info.label+' · '+p;"
        "h+='<div class=xmcell id=\"'+id+'\" onclick=\"xmPlay(\\''+id+'\\',\\''+f+'\\',\\''+"
        "lbl.replace(/'/g,'')+'\\')\"><b>'+p+'</b>click to play</div>';});"
        "document.getElementById('xmgrid').innerHTML=h;"
        '}'
        "function xmInit(){const sel=document.getElementById('xmset');"
        "sel.innerHTML=XM.ckpt_order.map(c=>'<option value=\"'+c+'\">'+XM.checkpoints[c].label+"
        "'</option>').join('');sel.onchange=xmUp;xmUp();}"
        'xmInit();'
    )

    page = MP_HTML.read_text()
    if "id=xmwrap" in page:
        raise SystemExit("mp.html already has an xmwrap section -- re-run needs a removal step first")
    marker = "</style></head><body>"
    assert page.count(marker) == 1
    page = page.replace(marker, f"{css}{marker}")
    assert page.count("</body></html>") == 1
    page = page.replace("</body></html>", f"{body}<script>{js}</script></body></html>")
    MP_HTML.write_text(page)
    print(f"appended cross-model section: {len(ckpt_order)} checkpoints x {len(prompt_order)} prompts "
          f"({MP_HTML}, {len(page)} bytes)")


if __name__ == "__main__":
    main()
