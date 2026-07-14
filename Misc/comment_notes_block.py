"""Shared comment-widget block for eval-page generators (Kim: "build once,
drop everywhere", 2026-07-14; W's model_matrix Notes panel is the reference
implementation, this is its generator-side reusable twin).

Gives a page two things:
  1. a static page-level comment box (data-page=<page_id>);
  2. a context-aware "Notes" panel that re-scopes to the clip/ckpt/model the
     user last clicked — the page sets the context via `noteSet({model, ckpt,
     clip})` (all strings, empty = not applicable) from its own click handler.

Scope contract (= merge_comments.py resolution, clip > ckpt > model > page):
only the fields for the chosen level are set on the widget div; the rest are
empty strings. `model` must be a canonical run-dir label under sa3_lora_runs/
or sa3_control_runs/ (the collect_models label space) so the nightly merge
routes it; the red-❗ clears at the matching level only.

comments.js / comment.php live on aavepyora; the absolute URL keeps the block
working if a page copy is served from another origin (GitHub Pages mirrors) —
posting from there additionally needs CORS on comment.php (W's side).

Usage in a generator:
    from comment_notes_block import notes_block
    html = template.replace("__NOTES__", notes_block(
        "onset_eval", levels=[("clip", "this clip"), ("model", "this eval run"),
                              ("page", "whole page")]))
    # + page JS calls noteSet({model: d.name, ckpt: '', clip: fname}) on click.
"""

COMMENTS_SRC = "https://aavepyora.online/files/comments.js"


def notes_block(page_id: str, levels=None,
                hint: str = "click a clip above to comment on it") -> str:
    levels = levels or [("clip", "this clip"), ("model", "this run"),
                        ("page", "whole page")]
    radios = "".join(
        f'<label><input type="radio" name="nlvl" value="{v}"'
        f'{" checked" if i == 0 else ""}> {lab}</label>'
        for i, (v, lab) in enumerate(levels))
    return f"""
<div class="cmts" data-page="{page_id}" style="max-width:1000px;margin:14px 12px"></div>
<script src="{COMMENTS_SRC}"></script>
<style>
.notes{{max-width:1000px;margin:14px 12px;padding:10px 12px;border:1px solid #2a2a30;border-radius:6px;background:#141418;font:13px system-ui;color:#e0e0e0}}
.notes-hd{{font-size:12px;color:#9cf;margin-bottom:6px}}.notes-scope{{color:#7ed}}.notes-hint{{color:#667;font-style:italic}}
.notes-lvl{{display:flex;gap:14px;margin-bottom:8px;font-size:12px;color:#bbb}}.notes-lvl label{{cursor:pointer}}
</style>
<div class="notes">
 <div class="notes-hd">Notes &mdash; <span id="nscope" class="notes-hint">{hint}</span></div>
 <div class="notes-lvl">{radios}</div>
 <div id="notebox" class="cmts"></div>
</div>
<script>
let noteCtx=null;
function setNoteScope(){{
 const box=document.getElementById('notebox');const sc=document.getElementById('nscope');
 const lvl=(document.querySelector('input[name=nlvl]:checked')||{{}}).value||'clip';
 if((!noteCtx||!noteCtx.model)&&lvl!=='page'){{sc.textContent='{hint}';sc.className='notes-hint';box.innerHTML='';return;}}
 box.dataset.page='{page_id}';
 box.dataset.model=(lvl==='page')?'':(noteCtx&&noteCtx.model||'');
 box.dataset.ckpt=(lvl==='clip'||lvl==='ckpt')?(noteCtx&&noteCtx.ckpt||''):'';
 box.dataset.clip=(lvl==='clip')?(noteCtx&&noteCtx.clip||''):'';
 sc.className='notes-scope';
 const parts=[];
 if(lvl==='page')parts.push('{page_id} (page)');
 else{{parts.push(noteCtx.model);
   if((lvl==='clip'||lvl==='ckpt')&&noteCtx.ckpt)parts.push(noteCtx.ckpt);
   if(lvl==='clip'&&noteCtx.clip)parts.push(noteCtx.clip.replace(/\\.(m4a|mp3|wav)$/,''));}}
 sc.textContent=parts.join(' \\u25b8 ');
 if(window.CommentWidget)CommentWidget.init(box);
}}
function noteSet(ctx){{noteCtx=ctx;setNoteScope();}}
document.querySelectorAll('input[name=nlvl]').forEach(r=>r.addEventListener('change',setNoteScope));
</script>"""
