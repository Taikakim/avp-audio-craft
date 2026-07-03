#!/usr/bin/env python3
"""build_evals.py — turn the served eval dumps into described, playable pages.

Reads the AAC staging (~/.cache/evals_aac/{control_runs,renders}) + the run
descriptions (riffer-evals/run_purposes.json), and writes a MIRROR under
site/evals/ containing ONLY index.html files (+ one CSS), self-contained
(inline CSS derived from edg3.css, so it survives any served layout):

  site/evals/index.html                         — the landing: every run/set described
  site/evals/control_runs/<run>/index.html       — same-playhead player for that folder
  site/evals/renders/<set>/index.html            — same-playhead player for that folder

Each per-folder index.html references its sibling *.m4a by filename, so WINTERMUTE
rsyncs the mirror over /files/evals/ (merging index.html into the existing clip
folders — clips untouched) and every folder becomes a player instead of a dump.

Same-playhead behaviour (MASTER §4): click a cell to play from the shared playhead;
switching cells keeps the position; re-click stops.
"""
import os, glob, json, html, shutil, re

HOME = os.path.expanduser("~")
STAGING = f"{HOME}/.cache/evals_aac"
# Write the players + landing INTO the staging, colocated with the clips, so
# WINTERMUTE's existing rsync of ~/.cache/evals_aac -> /files/evals brings them
# live automatically. index.html/evals.css are additive; clips are never touched.
# Run AFTER the transcode (or fold into that pipeline) so a rebuild doesn't clobber.
OUT = STAGING
PURP = {}
try:
    PURP = json.load(open(f"{HOME}/riffer-evals/run_purposes.json"))
except Exception:
    pass

# ── redaction seam (CONTINUITY, SPEC §4) — sidecars carry ckpt names/paths/configs
# and stay LOCAL; anything rendered into PUBLIC html is scrubbed here at render time.
_ABS  = re.compile(r'/(?:home|run|opt|mnt|root|var|tmp|Users)/[^\s"<>]*')
_CKPT = re.compile(r'\b[\w.\-/]+\.(?:pt|ckpt|safetensors|pth)\b')
_ADDR = re.compile(r'\b(?:(?:\d{1,3}\.){3}\d{1,3}|localhost)(?::\d+)?\b')
_VENV = re.compile(r'[\w.\-/]*\.venv[\w.\-/]*')
def redact(s):
    s = _ABS.sub('…', str(s)); s = _CKPT.sub('[checkpoint]', s)
    s = _ADDR.sub('[addr]', s); s = _VENV.sub('[venv]', s)
    return s

CSS = """:root{--paper:#fafaf7;--paper-dim:#f2f3ef;--ink:#2b3538;--body:#3b4649;
--dim:#7a8a8e;--faint:#9aa7a9;--rule:#c9d2d0;--rule-light:#e2e6e2;--edge:#0f9e99;--edge-ink:#0c807c;
--mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}
*{box-sizing:border-box}html{background:var(--paper)}
body{margin:0;color:var(--body);font-family:var(--mono);font-size:13px;line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:34px 28px 72px}
a{color:var(--edge-ink);text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px}
a:hover{text-decoration-style:solid}
.over{margin:0;font-size:11px;letter-spacing:.45em;color:var(--faint)}
h1{font-size:20px;line-height:1.3;color:var(--ink);margin:18px 0 6px}
h2{font-size:12px;letter-spacing:.3em;text-transform:uppercase;color:var(--ink);
margin:40px 0 14px;padding-bottom:6px;border-bottom:1px solid var(--rule)}
h2 .mark{color:var(--edge)}
.lede{font-size:14px;color:var(--ink)}.dim{color:var(--dim)}.faint{color:var(--faint)}
.nav{margin:14px 0 0;padding-bottom:10px;border-bottom:1px solid var(--rule);font-size:11.5px;color:var(--dim)}
.nav a{color:var(--dim);text-decoration:none;margin-right:16px}.nav a:hover{color:var(--edge-ink)}
code{background:var(--paper-dim);border:1px solid var(--rule-light);padding:1px 5px;font-size:12px}
.run{border:1px solid var(--rule);border-top:3px solid var(--edge);padding:12px 16px;margin:0 0 12px;background:#fff}
.run .name{font-size:13px;font-weight:600;color:var(--ink)}
.run .desc{font-size:11.5px;color:var(--body);margin:3px 0 6px}
.run .meta{font-size:11px;color:var(--faint)}
.grid{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0}
.cell{font-family:var(--mono);font-size:11px;color:var(--body);background:var(--paper-dim);
border:1px solid var(--rule);padding:6px 10px;cursor:pointer;border-radius:2px}
.cell:hover{border-color:var(--edge)}
.cell.playing{background:var(--edge);color:#fff;border-color:var(--edge)}
footer{margin-top:48px;padding-top:14px;border-top:1px solid var(--rule);font-size:11px;color:var(--faint)}
"""

PLAYER_JS = """<audio id="pl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('pl');
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}});
function play(el){const s=el.dataset.src;
 if(cur===el){a.pause();el.classList.remove('playing');cur=null;return}
 if(cur)cur.classList.remove('playing');
 a.src=s;a.addEventListener('loadedmetadata',function h(){a.currentTime=Math.min(ph,(a.duration||ph));a.removeEventListener('loadedmetadata',h)});
 a.play();cur=el;el.classList.add('playing')}
</script>"""

def head(title, depth):
    css_ref = "../" * depth + "evals.css" if depth else "evals.css"
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title>'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">'
            f'<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
            f'<link rel="stylesheet" href="{css_ref}"></head><body><div class="wrap">'
            f'<p class="over">VIBE ON THE EDG3 · EVALS</p>')

def desc_for(name, kind):
    """description for a run/set — prefer its self-describing _meta.json sidecar (redacted),
    else run_purposes.json, else a parsed hint. Everything returned is public-safe."""
    meta = f"{STAGING}/{kind}/{name}/_meta.json"
    if os.path.exists(meta):
        try:
            m = json.load(open(meta))
            purpose = m.get("purpose") or m.get("notes") or ""
            extra = " · ".join(f"{kk}={m[kk]}" for kk in ("optimizer","lr","scalar_field") if m.get(kk))
            return redact(purpose).strip(), redact(extra)
        except Exception:
            pass
    for k, v in PURP.items():
        if k == "_doc" or not isinstance(v, dict):
            continue
        if v.get("run") == name or k == name or (v.get("run","") and v["run"] in name):
            extra = " · ".join(f"{kk}={vv}" for kk in ("optimizer","lr","scalar_field") if (vv:=v.get(kk)))
            return redact((v.get("purpose","") or "").strip()), redact(extra)
    return "", redact(name.replace("_"," "))

def clean_label(fn):
    return redact(re.sub(r"\.m4a$","",fn).replace("__"," · ").replace("_"," "))

def build_folder(kind, name):
    d = f"{STAGING}/{kind}/{name}"
    # recurse — some render sets nest clips by ckpt/prompt; data-src is the relative path
    clips = sorted(os.path.relpath(c, d) for c in glob.glob(f"{d}/**/*.m4a", recursive=True))
    if not clips:
        return None
    purpose, extra = desc_for(name, kind)
    doc = head(f"{redact(name)} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(redact(name))}</h1>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    if extra:
        doc += f'<p class="dim">{html.escape(extra)}</p>'
    doc += f'<p class="faint">{len(clips)} clips · click to play (shared playhead; switching keeps position; re-click stops)</p>'
    doc += '<div class="grid">'
    for c in clips:
        doc += f'<span class="cell" data-src="{html.escape(c)}" onclick="play(this)">{html.escape(clean_label(c))}</span>'
    doc += '</div>' + PLAYER_JS
    doc += '<footer>aavepyora.online · evals · same-playhead</footer></div></body></html>'
    od = f"{OUT}/{kind}/{name}"
    os.makedirs(od, exist_ok=True)
    open(f"{od}/index.html","w").write(doc)
    return (name, purpose, len(clips))

def build_landing(control, renders):
    doc = head("Evals — Vibe on The Edg3", depth=0)
    doc += ('<p class="nav"><a href="https://aavepyora.online/files/">← the studio</a>'
            '<a href="https://aavepyora.online/files/AGENT_DIALOGUE.html">dialogue</a></p>')
    doc += ('<h1>Evals</h1><p class="lede">Listening results — what the control heads, adapters, and '
            'renders actually sound like. Each folder is a same-playhead player, not a dump.</p>')
    doc += '<h2><span class="mark">§</span> Curated players</h2>'
    doc += ('<p class="dim">The measured, annotated grids live in the riffer-evals pages '
            '(control-authority, DoRA auditions, LatCH sweep, chroma steer, disentangle) — same-playhead, '
            'with per-run info boxes.</p>')
    for label, kind, items in (("Control runs","control_runs",control),("Renders","renders",renders)):
        doc += f'<h2><span class="mark">§</span> {label} <span class="faint">({len(items)})</span></h2>'
        for name, purpose, n in items:
            doc += (f'<div class="run"><div class="name"><a href="{kind}/{html.escape(name)}/index.html">'
                    f'{html.escape(redact(name))}</a></div>'
                    + (f'<div class="desc">{html.escape(purpose)}</div>' if purpose else '')
                    + f'<div class="meta">{n} clips</div></div>')
    doc += '<footer>aavepyora.online · evals · generated by Misc/build_evals.py</footer></div></body></html>'
    open(f"{OUT}/index.html","w").write(doc)

def main():
    os.makedirs(OUT, exist_ok=True)
    open(f"{OUT}/evals.css","w").write(CSS)
    control, renders = [], []
    for kind, bucket in (("control_runs", control), ("renders", renders)):
        base = f"{STAGING}/{kind}"
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if not os.path.isdir(f"{base}/{name}"):
                continue
            r = build_folder(kind, name)
            if r:
                bucket.append(r)
        # loose top-level clips in the bucket -> a "_demos" player (data-src one level up)
        loose = sorted(os.path.basename(c) for c in glob.glob(f"{base}/*.m4a"))
        if loose:
            doc = head(f"{kind} demos — evals", depth=2)
            doc += '<p class="nav"><a href="../../index.html">← all evals</a></p>'
            doc += f'<h1>{kind} · loose demos</h1><p class="faint">{len(loose)} clips</p><div class="grid">'
            for c in loose:
                doc += f'<span class="cell" data-src="../{html.escape(c)}" onclick="play(this)">{html.escape(clean_label(c))}</span>'
            doc += '</div>' + PLAYER_JS + '<footer>aavepyora.online · evals</footer></div></body></html>'
            os.makedirs(f"{OUT}/{kind}/_demos", exist_ok=True)
            open(f"{OUT}/{kind}/_demos/index.html","w").write(doc)
            bucket.append(("_demos", "loose top-level demo clips", len(loose)))
    build_landing(control, renders)
    print(f"control_runs: {len(control)} playable folders")
    print(f"renders:      {len(renders)} playable folders")
    print(f"landing + {len(control)+len(renders)} folder players -> {OUT}")

if __name__ == "__main__":
    main()
