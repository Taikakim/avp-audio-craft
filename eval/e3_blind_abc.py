#!/usr/bin/env python3
# Owner: THE-FINN (created 2026-10-15)
# Last edited: THE-FINN 2026-10-15 -- blind A/B/C listening page for the E3 metrical bracket
"""e3_blind_abc.py -- blind A/B/C listening test for the E3 metrical-position bracket.

Question (docs/superpowers/specs/2026-07-31-metrical-tree-pe-design.md, KIM-TASKLIST "E3 metrical-position
bracket pairs"): does the `real` adapter SOUND like it has phrase-level structure (a section returning
after a few bars) compared with the `shuffled` collapse baseline and the `base` model?

Each trial = one (prompt, seed): three clips (base / real / shuffled), same prompt and seed, shown as
A / B / C in a random order. You pick the one with the clearest phrase return / structure, and may pick
the weakest. The model behind each letter lives only on the server until you press "Reveal results".

    SAO/.venv/bin/python eval/e3_blind_abc.py                # serves http://127.0.0.1:8071/
    SAO/.venv/bin/python eval/e3_blind_abc.py --port 8071 --bracket <dir>

Inputs : <bracket>/results.json + <bracket>/<model>/<model>__p<i>__s<seed>.wav  (from e3_structure_bracket.py render)
Outputs: eval/e3_blind_votes.jsonl (one line per vote, with the resolved model names; append-only,
         last vote per trial wins). Stdlib server; reads audio with soundfile for the loudness match.
Clips are level-matched to the quietest of each trial (gain <= 1) so loudness cannot give the answer away.
"""
import argparse, json, os, random, re, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BRACKET = "/run/media/kim/Mantu/sa3_control_runs/e3_metrical/bracket"
VOTES = os.path.join(HERE, "e3_blind_votes.jsonl")
MODELS = ("base", "real", "shuffled")
LOCK = threading.Lock()


def build_trials(bracket, seed):
    meta = json.load(open(os.path.join(bracket, "results.json")))
    prompts = {}
    by_key = {}
    for c in meta["clips"]:
        by_key.setdefault((c["prompt_idx"], c["seed"]), {})[c["model"]] = c
        prompts[c["prompt_idx"]] = c["prompt"]
    rng = random.Random(seed)
    trials = []
    for (pi, sd), models in sorted(by_key.items()):
        if not all(m in models for m in MODELS):
            continue
        order = list(MODELS)
        rng.shuffle(order)
        clips = []
        for letter, m in zip("ABC", order):
            path = os.path.join(bracket, m, models[m]["clip"] + ".wav")
            if not os.path.exists(path):
                break
            clips.append({"letter": letter, "model": m, "path": path})
        else:
            trials.append({"id": f"p{pi}_s{sd}", "prompt_idx": pi, "seed": sd, "prompt": prompts[pi], "clips": clips})
    rng.shuffle(trials)
    return trials


def loudness_gains(trials):
    """Per-trial gain so every clip matches the quietest one's RMS (gain <= 1, no clipping)."""
    for t in trials:
        rms = []
        for c in t["clips"]:
            x, _ = sf.read(c["path"], dtype="float32", always_2d=True)
            rms.append(float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) + 1e-9)
        lo = min(rms)
        for c, r in zip(t["clips"], rms):
            c["gain"] = round(lo / r, 4)


def load_votes():
    votes = {}
    if os.path.exists(VOTES):
        for line in open(VOTES):
            try:
                v = json.loads(line)
                votes[v["trial"]] = v
            except Exception:
                pass
    return votes


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>E3 Blind Listening</title>
<style>
:root{--bg:#101114;--panel:#171a1f;--line:#2a2e36;--ink:#e4e6ea;--mute:#8a919d;--acc:#6fb4ff;--ok:#5fd08a;--bad:#e8646a}
@media (prefers-color-scheme:light){:root{--bg:#f4f5f7;--panel:#fff;--line:#d7dbe2;--ink:#1c2026;--mute:#667080;--acc:#1f6fd0;--ok:#1b8a4a;--bad:#c23039}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}
h1{font-size:1.15rem;margin:.2rem 0}.mute{color:var(--mute);font-size:.9rem}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}
button{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:10px 14px;font:inherit;cursor:pointer;min-height:44px}
button.on{border-color:var(--acc);background:color-mix(in srgb,var(--acc) 18%,var(--panel))}
button.bad.on{border-color:var(--bad);background:color-mix(in srgb,var(--bad) 18%,var(--panel))}
.clip{display:flex;align-items:center;gap:10px;margin:8px 0}.clip .l{font-size:1.4rem;font-weight:700;width:1.6rem}
.clip button.play{min-width:92px}input[type=range]{flex:1}
textarea{width:100%;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
</style></head><body><main>
<h1>E3 metrical bracket: which one has the clearest phrase structure?</h1>
<div class="mute">Same prompt and seed in A, B and C; loudness matched. Listen for a section or pattern that <b>comes back</b> after a few bars.
Pick the one that sounds most structured, and optionally the weakest. Keys: <b>1 2 3</b> play A/B/C, <b>space</b> pause, <b>Q</b> best&nbsp;A, <b>W</b> best&nbsp;B, <b>E</b> best&nbsp;C, <b>←/→</b> trials.</div>
<div class="card"><div class="bar"><i id="prog" style="width:0"></i></div><div class="mute" id="cnt"></div></div>
<div id="trial"></div>
<div class="row"><button id="prev">&larr; previous</button><button id="next">next &rarr;</button><button id="reveal" style="margin-left:auto">Reveal results</button></div>
<div id="res"></div>
<audio id="au" preload="auto"></audio>
</main>
<script>
let T=[],i=0,V={},cur=null;const $=s=>document.querySelector(s),au=$('#au');
async function load(){const s=await (await fetch('/api/state')).json();T=s.trials;V=s.votes;
 const first=T.findIndex(t=>!V[t.id]);i=first<0?0:first;draw();}
function draw(){const t=T[i];$('#cnt').textContent=`trial ${i+1} of ${T.length}  ·  ${Object.keys(V).length} answered`;
 $('#prog').style.width=(100*Object.keys(V).length/T.length)+'%';
 const v=V[t.id]||{};
 $('#trial').innerHTML=`<div class="card"><div class="mute">prompt: ${t.prompt}</div>`+
 t.clips.map(c=>`<div class="clip"><span class="l">${c.letter}</span>
   <button class="play" data-l="${c.letter}">▶ play</button>
   <input type="range" min="0" max="1000" value="0" data-s="${c.letter}">
   <button class="${v.best===c.letter?'on':''}" data-best="${c.letter}">clearest</button>
   <button class="bad ${v.worst===c.letter?'on':''}" data-worst="${c.letter}">weakest</button></div>`).join('')+
 `<div class="row"><button class="${v.best==='none'?'on':''}" data-best="none">can't tell</button></div>
  <textarea id="note" rows="2" placeholder="notes (optional)">${v.note||''}</textarea></div>`;
 document.querySelectorAll('[data-l]').forEach(b=>b.onclick=()=>play(b.dataset.l));
 document.querySelectorAll('[data-best]').forEach(b=>b.onclick=()=>vote('best',b.dataset.best));
 document.querySelectorAll('[data-worst]').forEach(b=>b.onclick=()=>vote('worst',b.dataset.worst));
 document.querySelectorAll('[data-s]').forEach(r=>r.oninput=()=>{if(cur===r.dataset.s&&au.duration)au.currentTime=au.duration*r.value/1000});
 $('#note').onchange=()=>vote('note',$('#note').value);
 cur=null;au.pause();}
function play(l){const t=T[i],c=t.clips.find(x=>x.letter===l);const at=(cur===l&&au.duration)?au.currentTime:(cur?au.currentTime:0);
 const same=cur===l;if(!same){const keep=cur?au.currentTime:0;au.src=`/audio/${t.id}/${l}.wav`;au.volume=Math.min(1,c.gain);
  au.onloadedmetadata=()=>{au.currentTime=keep;au.play()};cur=l;au.load()}else{au.paused?au.play():au.pause()}
 document.querySelectorAll('[data-l]').forEach(b=>b.textContent=(b.dataset.l===cur&&!au.paused)?'⏸ playing':'▶ play');}
au.ontimeupdate=()=>{if(!cur||!au.duration)return;const r=document.querySelector(`[data-s=${cur}]`);if(r)r.value=1000*au.currentTime/au.duration};
au.onended=()=>{document.querySelectorAll('[data-l]').forEach(b=>b.textContent='▶ play')};
async function vote(k,val){const t=T[i];const v=Object.assign({},V[t.id]||{});if(k==='best'||k==='worst'){if(v[k]===val)delete v[k];else v[k]=val}else v[k]=val;
 if(v.best&&v.best===v.worst){delete v.worst}
 V[t.id]=v;await fetch('/api/vote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({trial:t.id,best:v.best||null,worst:v.worst||null,note:v.note||''})});draw();}
$('#prev').onclick=()=>{i=Math.max(0,i-1);draw()};$('#next').onclick=()=>{i=Math.min(T.length-1,i+1);draw()};
$('#reveal').onclick=async()=>{const r=await (await fetch('/api/reveal')).json();
 const rows=Object.entries(r.tally).map(([m,x])=>`<tr><td>${m}</td><td>${x.best}</td><td>${x.worst}</td></tr>`).join('');
 $('#res').innerHTML=`<div class="card"><b>${r.answered} of ${r.total} trials answered</b> (${r.cant_tell} "can't tell")
 <table><tr><th>model</th><th>picked clearest</th><th>picked weakest</th></tr>${rows}</table>
 <div class="mute">Chance is one third each. Automated phrase-return gain: real 0.0091, base 0.0037, shuffled 0.0009 (n=12 per model, saturated metric).</div></div>`};
addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA')return;
 if('123'.includes(e.key)&&e.key)play('ABC'[+e.key-1]);else if(e.key===' '){e.preventDefault();cur&&(au.paused?au.play():au.pause())}
 else if('qwe'.includes(e.key.toLowerCase())&&e.key.length===1)vote('best','ABC'['qwe'.indexOf(e.key.toLowerCase())]);
 else if(e.key==='ArrowRight')$('#next').click();else if(e.key==='ArrowLeft')$('#prev').click()});
load();
</script></body></html>"""


def make_handler(trials):
    by_id = {t["id"]: t for t in trials}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            p = urlparse(self.path).path
            if p == "/":
                b = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif p == "/api/state":
                # blind: letters + gains only; the model behind each letter is never sent
                pub = [{"id": t["id"], "prompt": t["prompt"],
                        "clips": [{"letter": c["letter"], "gain": c["gain"]} for c in t["clips"]]} for t in trials]
                votes = {k: {x: v[x] for x in ("best", "worst", "note") if x in v} for k, v in load_votes().items()}
                self._json({"trials": pub, "votes": votes})
            elif p == "/api/reveal":
                votes = load_votes()
                tally = {m: {"best": 0, "worst": 0} for m in MODELS}
                cant = 0
                for tid, v in votes.items():
                    t = by_id.get(tid)
                    if not t:
                        continue
                    L = {c["letter"]: c["model"] for c in t["clips"]}
                    if v.get("best") in L:
                        tally[L[v["best"]]]["best"] += 1
                    elif v.get("best") == "none":
                        cant += 1
                    if v.get("worst") in L:
                        tally[L[v["worst"]]]["worst"] += 1
                self._json({"tally": tally, "answered": len(votes), "total": len(trials), "cant_tell": cant})
            elif p.startswith("/audio/"):
                m = re.fullmatch(r"/audio/([\w\-]+)/([ABC])\.wav", p)
                t = by_id.get(m.group(1)) if m else None
                c = next((x for x in t["clips"] if x["letter"] == m.group(2)), None) if t else None
                if not c:
                    return self._json({"error": "not found"}, 404)
                size = os.path.getsize(c["path"])
                start, end = 0, size - 1
                rng = self.headers.get("Range")
                if rng and (mm := re.match(r"bytes=(\d*)-(\d*)", rng)):
                    if mm.group(1):
                        start = int(mm.group(1))
                    if mm.group(2):
                        end = min(int(mm.group(2)), size - 1)
                self.send_response(206 if rng else 200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(end - start + 1))
                if rng:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                with open(c["path"], "rb") as f:
                    f.seek(start)
                    self.wfile.write(f.read(end - start + 1))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if urlparse(self.path).path != "/api/vote":
                return self._json({"error": "not found"}, 404)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            t = by_id.get(body.get("trial"))
            if not t:
                return self._json({"error": "unknown trial"}, 400)
            L = {c["letter"]: c["model"] for c in t["clips"]}
            rec = {"trial": t["id"], "prompt_idx": t["prompt_idx"], "seed": t["seed"],
                   "best": body.get("best"), "worst": body.get("worst"), "note": body.get("note", ""),
                   "best_model": L.get(body.get("best")), "worst_model": L.get(body.get("worst")),
                   "letters": L}
            with LOCK, open(VOTES, "a") as f:
                f.write(json.dumps(rec) + "\n")
            self._json({"ok": True})

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bracket", default=DEFAULT_BRACKET)
    ap.add_argument("--port", type=int, default=8071)
    ap.add_argument("--seed", type=int, default=20261015, help="fixes letter assignment and trial order across restarts")
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    trials = build_trials(a.bracket, a.seed)
    if not trials:
        sys.exit(f"no complete trials under {a.bracket}")
    loudness_gains(trials)
    print(f"{len(trials)} trials, votes -> {VOTES}\nhttp://{a.host}:{a.port}/", flush=True)
    ThreadingHTTPServer((a.host, a.port), make_handler(trials)).serve_forever()


if __name__ == "__main__":
    main()
