#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-20)
"""build_mixtape_clamp_page.py -> ~/evals_aac/mixtape_clamp.html. Blind same-playhead A/B(/C/D) page for the latent-norm clamp test.
Reads Mantu/sa3_lora_runs/mixtape_z0_clamp_2026-10-20/cells.jsonl; per clip the arms are orig, c1.4, c1.15 (clamped z0, std ceiling) and lim (soft-limited original).
Arm order is shuffled per clip (fixed seed) and labels are hidden until 'reveal'. Ratings 1-5 per arm kept in localStorage; 'export' copies JSON for kim_feedback.
RUN: python3 Misc/build_mixtape_clamp_page.py   (needs ffmpeg; encodes AAC 256k into ~/evals_aac/mixtape_clamp/)"""
import json, os, random, subprocess, html
SRC = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_z0_clamp_2026-10-20"
OUT = os.path.expanduser("~/evals_aac/mixtape_clamp"); os.makedirs(OUT, exist_ok=True)
rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl")]
rows.sort(key=lambda r: -r["z0_std"])
rnd = random.Random(20261020); clips = []
for r in rows:
    arms = [k for k in ("orig", "c1.4", "c1.15", "lim") if k in r]
    for k in arms:
        o = f"{OUT}/{r['id']}__{k}.m4a"
        if not os.path.exists(o):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{SRC}/{r['id']}__{k}.wav", "-c:a", "aac", "-b:a", "256k", o], check=True)
    order = arms[:]; rnd.shuffle(order)
    clips.append(dict(id=r["id"], std=r["z0_std"], order=order, m={k: r[k] for k in arms}))
page = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Latent Norm Clamp A/B</title>
<style>:root{--bg:#f3f1ee;--fg:#1d2326;--mut:#5d676b;--card:#fff;--line:#d6d2cc;--acc:#0b6e6e}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15191b;--fg:#e6e9ea;--mut:#9aa5a8;--card:#1d2326;--line:#343c3f;--acc:#5fc4c0}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;padding:16px;max-width:980px;margin-inline:auto}
h1{font-size:22px;margin:.2em 0}.ex{background:var(--card);border:1px solid var(--line);padding:12px 14px;border-radius:4px;margin:12px 0;color:var(--mut)}
.clip{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:10px 12px;margin:10px 0}.hd{display:flex;gap:10px;flex-wrap:wrap;align-items:baseline;font-size:13px;color:var(--mut)}
.arms{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.arm{border:1px solid var(--line);padding:6px 10px;border-radius:4px;cursor:pointer;min-width:120px}
.arm.on{border-color:var(--acc);outline:2px solid var(--acc)}.arm b{font-size:16px}.lab{font-size:12px;color:var(--mut);display:none}.rev .lab{display:block}
select{font:inherit;margin-top:4px}button{font:inherit;cursor:pointer}</style></head><body>
<h1>Latent Norm Clamp A/B</h1>
<div class="ex"><b>What this tests.</b> The clips you rated 5 run a hotter latent than a healthy render (std median 1.37 against about 1.13). Each row is one clip decoded four ways from the same latent: unchanged, capped at std 1.4, capped at 1.15, and the unchanged one with a soft limiter on the loud peaks. Click A/B/C/D to switch; the playhead stays put. Rate each 1-5 (3 = same as the best of the others). A pair that sounds identical is a real result: it means the norm is not the cause. Labels are hidden until Reveal.<br><b>For engineers.</b> Clamp = whole-latent scale by cap/std when std &gt; cap (eval/mixtape_z0_clamp.py). Source: eval/mixtape_audit_kim_shortlist_2026-09-15.json, z0 from model_matrix. AAC 256k.</div>
<div><button onclick="document.body.classList.toggle('rev')">Reveal labels</button> <button onclick="exp()">Copy ratings JSON</button></div><div id="L"></div>
<script>const C=%s;const R=JSON.parse(localStorage.getItem('mclamp')||'{}');let cur=null;
function pl(id,k,box){const a=document.getElementById('au');const t=cur&&cur.id==id?a.currentTime:(cur?cur.t:0);const was=!a.paused;a.src='mixtape_clamp/'+id+'__'+k+'.m4a';a.currentTime=t;if(was||!cur||cur.id!=id)a.play();cur={id:id,k:k,t:t};document.querySelectorAll('.arm.on').forEach(e=>e.classList.remove('on'));box.classList.add('on')}
function rate(id,k,v){R[id+'|'+k]=v;try{localStorage.setItem('mclamp',JSON.stringify(R))}catch(e){}}
function exp(){navigator.clipboard.writeText(JSON.stringify(R,null,1))}
const L=document.getElementById('L');C.forEach(c=>{const d=document.createElement('div');d.className='clip';let h='<div class="hd"><b>'+c.id.slice(0,70)+'</b><span>z0 std '+c.std+'</span></div><div class="arms">';
c.order.forEach((k,i)=>{const m=c.m[k];h+='<div class="arm" onclick="pl(\\''+c.id+'\\',\\''+k+'\\',this)"><b>'+'ABCD'[i]+'</b><div class="lab">'+k+' · rms '+m.rms_db+' dB · crest '+m.crest+' · hf '+m.hf_ratio+'</div><select onclick="event.stopPropagation()" onchange="rate(\\''+c.id+'\\',\\''+k+'\\',this.value)"><option value="">rate</option>'+[1,2,3,4,5].map(v=>'<option'+(R[c.id+'|'+k]==v?' selected':'')+'>'+v+'</option>').join('')+'</select></div>'});
d.innerHTML=h+'</div>';L.appendChild(d)});setInterval(()=>{const a=document.getElementById('au');if(cur)cur.t=a.currentTime},300)</script>
<audio id="au" controls style="position:sticky;bottom:0;width:100%%;margin-top:12px"></audio></body></html>""" % json.dumps(clips)
open(os.path.expanduser("~/evals_aac/mixtape_clamp.html"), "w").write(page)
json.dump({"purpose": "blind A/B of latent-norm clamp (1.4, 1.15) and soft limiter vs original on the Kim shortlist 5-star clips", "script": "Misc/build_mixtape_clamp_page.py", "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"))
print(len(clips), "clips -> ~/evals_aac/mixtape_clamp.html")
