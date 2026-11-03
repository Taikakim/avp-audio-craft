#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-14)
"""float_player.py -- the floating transport bar of the old eval pages, for ANY page.

build_evals.PLAYER_JS gives the old pages a fixed bottom bar (play/pause, clip name,
seek, time, download). The standalone pages built by their own scripts (punch_air,
latch_phaseE, latch_onset_compare, ...) have their own players and no bar. This
snippet is page-agnostic: it follows whichever <audio> element (or `new Audio()`)
last played and drives THAT element, so the page's same-playhead logic is untouched.

Use from a builder:   from float_player import inject;  html = inject(html)
Or retrofit pages:    python3 Misc/float_player.py ~/evals_aac/x.html [...]
inject() is idempotent (marker comment), so re-running is safe.
"""
import sys

MARK = "<!-- float-player v1 -->"

SNIPPET = MARK + """
<div id="fpbar" style="display:none"><button id="fppp" title="play / pause">&#9208;</button><span id="fpnp"></span><input type="range" id="fpseek" min="0" max="1000" value="0" title="playhead: drag to seek"><span id="fptm">0:00 / 0:00</span><a id="fpdl" href="#" download title="download this clip">&#8681;</a></div>
<style>#fpbar{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;display:none;align-items:center;gap:10px;background:#f2f3ef;border-top:1px solid #c9d2d0;padding:8px 14px;font:13px 'IBM Plex Mono',ui-monospace,monospace;color:#3b4649;box-sizing:border-box}
#fppp{background:none;border:0;color:#0c807c;cursor:pointer;font-size:15px;line-height:1;min-width:32px;min-height:32px}
#fpnp{color:#2b3538;max-width:32vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#fpseek{flex:1;min-width:60px;accent-color:#0f9e99;cursor:pointer;height:4px}
#fptm{color:#7a8a8e;font-variant-numeric:tabular-nums;white-space:nowrap}
#fpdl{color:#0c807c;text-decoration:none;font-size:17px}#fpdl:hover{color:#0f9e99}
body.fp-on{padding-bottom:56px}</style>
<script>(function(){
const bar=document.getElementById('fpbar'),pp=document.getElementById('fppp'),np=document.getElementById('fpnp'),
 seek=document.getElementById('fpseek'),tm=document.getElementById('fptm'),dl=document.getElementById('fpdl');
const fmt=s=>{s=Math.max(0,s|0);return (s/60|0)+':'+String(s%60).padStart(2,'0')};
let tr=null,dragging=false;
function show(){bar.style.display='flex';document.body.classList.add('fp-on')}
function sync(){if(!tr)return;pp.innerHTML=tr.paused?'&#9654;':'&#9208;';
 const d=tr.duration;if(d&&isFinite(d)){if(!dragging)seek.value=Math.round(tr.currentTime/d*1000);tm.textContent=fmt(tr.currentTime)+' / '+fmt(d)}}
function track(a){if(tr!==a){tr=a;const s=a.currentSrc||a.src||'';const nm=decodeURIComponent(s.split('/').pop().split('?')[0]);
 np.textContent=nm;dl.href=s;dl.setAttribute('download',nm)}show();sync()}
function attach(a){if(a.__fp)return;a.__fp=true;a.addEventListener('play',()=>track(a));
 ['pause','timeupdate','durationchange','ended'].forEach(ev=>a.addEventListener(ev,()=>{if(tr===a)sync()}))}
const NA=window.Audio;function PA(...x){const a=new NA(...x);attach(a);return a}PA.prototype=NA.prototype;window.Audio=PA;
function scan(){document.querySelectorAll('audio').forEach(attach)}
scan();document.addEventListener('DOMContentLoaded',scan);
new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true});
pp.addEventListener('click',()=>{if(!tr)return;tr.paused?tr.play():tr.pause()});
seek.addEventListener('input',()=>{dragging=true;if(tr&&tr.duration)tm.textContent=fmt(seek.value/1000*tr.duration)+' / '+fmt(tr.duration)});
seek.addEventListener('change',()=>{if(tr&&tr.duration)tr.currentTime=seek.value/1000*tr.duration;dragging=false});
})();</script>
"""


def inject(page: str) -> str:
    """Insert the bar before </body> (or append). No-op if already present."""
    if MARK in page:
        return page
    i = page.rfind("</body>")
    return page + SNIPPET if i < 0 else page[:i] + SNIPPET + page[i:]


def main(paths) -> int:
    for p in paths:
        t = open(p, encoding="utf-8").read()
        n = inject(t)
        if n != t:
            open(p, "w", encoding="utf-8").write(n)
        print(("added" if n != t else "present"), p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
