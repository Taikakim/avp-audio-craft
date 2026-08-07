#!/usr/bin/env python
"""build_clarity_audit_page.py — self-contained audit page for the codec clarity ladder
(hf_clarity_diagnosis.py). Places the frozen SA3 SAME round-trip on the SAME axis as real
MP3 and our audition-serving m4a/AAC, in producer units, with a hold-the-moment /
switch-the-codec same-playhead player (spec §12/§14 three-audience: TOOL + RESOURCE +
LEARNING). Public-safe: no absolute paths, no plumbing — only the science (codec, bitrate,
metric defs) and commercial track titles.

Run (any venv):  python eval/build_clarity_audit_page.py
Reads   OUT/results.json (+ OUT/audio/) ; writes OUT/index.html
Then W rsyncs the OUT dir to /files/audit/codec-clarity/ (relative audio paths resolve).
"""
import json
from pathlib import Path

OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/hf_clarity")

# display order + human labels; SAME first (the subject), then the codec anchors low->high
VORDER = ["original", "SAME", "mp3_128", "m4a_128", "m4a_192", "mp3_320", "m4a_320"]
VLABEL = {"original": "Original (source)", "SAME": "SAME codec round-trip",
          "mp3_128": "MP3 128k", "m4a_128": "AAC/m4a 128k", "m4a_192": "AAC/m4a 192k",
          "mp3_320": "MP3 320k", "m4a_320": "AAC/m4a 320k"}
VKIND = {"original": "ref", "SAME": "same"}   # else "codec"


def cell(v, good_hi=True, lo=0.0, hi=1.0):
    """colour a metric green(good)->red(bad); good_hi=True means higher is better."""
    if v is None:
        return '<td class="na">–</td>'
    t = max(0.0, min(1.0, (v - lo) / (hi - lo + 1e-9)))
    if not good_hi:
        t = 1.0 - t
    # green (120) at good, red (0) at bad
    h = int(120 * t)
    return f'<td style="background:hsl({h},55%,22%)">{v:.3f}</td>'


def main():
    R = json.loads((OUT / "results.json").read_text())
    S = R["summary"]
    present = [v for v in VORDER if v in S]
    clips = R.get("clips", [])

    # ---- metrics table (air 8-16k is the headline HF band) ----
    rows = []
    for v in present:
        d = S[v]
        air = d.get("air_8-16k", {})
        pres = d.get("presence_4-8k", {})
        kind = VKIND.get(v, "codec")
        rows.append(
            f'<tr class="k-{kind}"><td class="vname">{VLABEL[v]}</td>'
            + cell(air.get("env_corr"), True, 0.4, 1.0)
            + cell(pres.get("env_corr"), True, 0.4, 1.0)
            + cell(air.get("crest_ret"), True, 0.5, 1.5)   # ~1 ideal; >1 = spiky, <1 = smeared
            + cell(air.get("flatness_delta"), False, 0.0, 0.12)
            + f'<td class="roll">{d.get("rolloff_hz","–")}</td></tr>')
    table = "\n".join(rows)

    # ---- same-playhead players (one per exported clip) ----
    players = []
    for i, c in enumerate(clips):
        av = c["audio"]
        btns = "".join(
            f'<button class="vb" data-src="{av[v]}"'
            + (' data-init="1"' if v == "original" else "")
            + f'>{VLABEL[v]}</button>'
            for v in present if v in av)
        players.append(f'''<div class="player" data-clip="{i}">
      <div class="ptitle">{c["label"]}</div>
      <div class="vbtns">{btns}</div>
      <div class="transport">
        <button class="pp">▶</button>
        <div class="scrub"><div class="fill"></div></div>
        <span class="time">0:00</span>
        <span class="now"></span>
      </div>
      <audio preload="none"></audio>
    </div>''')
    # ---- beat-synced 2-minute clips (Kim 2026-08-07), LOCAL ONLY ----------------------
    # Written by eval/hf_clarity_fulltracks.py: whole-bar windows from the 60-70% point of a
    # track, stereo, ~40 MB per variant. They are deliberately NOT rsynced to the public page
    # (spec §4 keeps online eval audio small) -- the local server on :8792 serves them.
    # data-loop="1" makes the player loop them seamlessly, which is why the windows snap to
    # downbeats at BOTH ends.
    longs = []
    lp = OUT / "longclips.json"
    if lp.exists():
        for i, c in enumerate(json.loads(lp.read_text())):
            av = c["audio"]
            btns = "".join(
                f'<button class="vb" data-src="{av[v]}"'
                + (' data-init="1"' if v == "original" else "")
                + f'>{VLABEL[v]}</button>'
                for v in present if v in av)
            longs.append(f'''<div class="player" data-clip="L{i}" data-loop="1">
      <div class="ptitle">{c["label"]}</div>
      <div class="vbtns">{btns}</div>
      <div class="transport">
        <button class="pp">▶</button>
        <div class="scrub"><div class="fill"></div></div>
        <span class="time">0:00</span>
        <span class="now"></span>
      </div>
    </div>''')
    if longs:
        players.append('<h2 style="margin-top:26px">Beat-synced 2-minute clips '
                       '<span class="tag">local only · loops</span></h2>'
                       '<p class="legend">Whole-bar windows from the 60–70% point of each track, '
                       'where the arrangement is usually busiest and HF detail is stressed hardest. '
                       'Stereo, and they loop seamlessly — leave one running and switch codecs or Δ '
                       'while it plays.</p>')
        players.extend(longs)
    players_html = "\n".join(players)

    n = R.get("n_tracks", "?")
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Codec clarity ladder — SAME vs MP3 vs AAC/m4a</title>
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#0d0f12;color:#e6e8ea;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:100%;padding:clamp(14px,3vw,40px)}}
h1{{font-size:clamp(20px,3vw,30px);margin:0 0 .3em}}
h2{{font-size:1.15em;margin:1.8em 0 .5em;color:#9fd0ff}}
.sub{{color:#8b929a;margin:0 0 1.5em}}
.explain{{background:#14181d;border:1px solid #232a31;border-radius:10px;padding:16px 20px;max-width:900px;margin-bottom:1.5em}}
.explain p{{margin:.5em 0}}
.explain b{{color:#cfe6ff}}
.tag{{display:inline-block;font-size:.72em;padding:1px 7px;border-radius:20px;background:#233; color:#9fe;margin-left:6px;vertical-align:middle}}
table{{border-collapse:collapse;width:100%;max-width:1000px;font-variant-numeric:tabular-nums}}
th,td{{padding:8px 12px;text-align:right;border-bottom:1px solid #1c2228}}
th{{color:#9aa2ab;font-weight:600;font-size:.82em;text-align:right;position:sticky;top:0;background:#0d0f12}}
td.vname{{text-align:left;font-weight:600;white-space:nowrap}}
td.na,td.roll{{background:none;color:#7a828b}}
tr.k-same td.vname{{color:#ffb4a2}}
tr.k-ref td.vname{{color:#a9f5c0}}
tr.k-same{{outline:1px solid #5a2a24}}
.legend{{color:#8b929a;font-size:.85em;margin:.6em 0 0;max-width:900px}}
.player{{background:#14181d;border:1px solid #232a31;border-radius:10px;padding:14px 16px;margin:12px 0;max-width:1000px}}
.ptitle{{font-weight:600;margin-bottom:8px;color:#cfe6ff}}
.vbtns{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;align-items:flex-end}}
.vcol{{display:flex;flex-direction:column;gap:3px}}
.db{{font-size:.68em;padding:1px 0;border-radius:5px;border:1px solid #3a2f4a;background:#221b2b;color:#c9a6ff;cursor:pointer}}
.db.on{{background:#6b3fa0;color:#fff;border-color:#8a5cc7}}
.db[disabled]{{opacity:.25;cursor:default}}
.vb{{background:#1c2229;color:#c8ccd1;border:1px solid #2c343d;border-radius:7px;padding:6px 11px;font-size:.85em;cursor:pointer}}
.vb:hover{{background:#252d36}}
.vb.on{{background:#2a6cff;border-color:#2a6cff;color:#fff}}
.transport{{display:flex;align-items:center;gap:12px}}
.pp{{background:#2c343d;color:#fff;border:none;border-radius:50%;width:38px;height:38px;font-size:15px;cursor:pointer;flex:none}}
.scrub{{flex:1;height:8px;background:#232a31;border-radius:6px;cursor:pointer;position:relative}}
.fill{{height:100%;width:0;background:#2a6cff;border-radius:6px;pointer-events:none}}
.time{{color:#8b929a;font-size:.85em;min-width:38px}}
.now{{color:#9fd0ff;font-size:.85em}}
footer{{color:#6b727a;font-size:.8em;margin-top:2.5em;max-width:900px}}
</style></head><body><div class="wrap">
<h1>Codec clarity ladder <span class="tag">HF fidelity audit</span></h1>
<p class="sub">The frozen SA3 <b>SAME</b> codec round-trip, placed on the same axis as real MP3 and
our audition-serving AAC/<b>m4a</b> — in units a producer knows. n = {n} Goa full-mix clips, 8&nbsp;s each, mono.</p>

<div class="explain">
<p><b>What this tests.</b> On our normal eval boards a clip has been through a lossy codec twice:
once when the model's <b>SAME</b> autoencoder compresses audio into its latent and decodes it back,
and again when the render is transcoded to <b>m4a/AAC</b> for the web. This page separates those two
steps and measures how much high-frequency <i>detail</i> each one throws away, against MP3 at
bitrates producers recognise.</p>
<p><b>Nothing on THIS page is served lossily.</b> That would defeat the test — a common m4a layer
over every version would mask the very differences being compared. Each version here is decoded once
(so the codec's damage is baked into the samples) and then delivered as <b>lossless FLAC</b>, which
is bit-exact PCM, not a second encode. The reference is bit-identical to the source track, verified.
It is the only honest way to audition a codec ladder in a browser: the alternative — shipping each
version in its own native format — would put the browser's decoder, and each format's encoder
delay/padding, between you and the comparison, which would also break the sample alignment the
<b>Δ</b> buttons depend on.</p>
<p><b>How to read it.</b> The headline is <b>air-band env&nbsp;corr</b> (8–16&nbsp;kHz): how faithfully
the fine temporal detail — shimmer, cymbal air, transient sparkle — survives. <b>1.0 = perfect,
&lt;&lt;1 = smeared into a wash.</b> Compare each row to the MP3 anchors: if SAME sits below MP3&nbsp;128k,
the codec is doing more damage up top than a late-90s 128k MP3 did. <i>crest&nbsp;ret</i> ≈ transient
sharpness (≈1 ideal), <i>flat&nbsp;Δ</i> &gt; 0 = detail turning to haze. Rolloff is power-weighted and
bass-dominated, so it barely moves — ignore it as an HF discriminator; trust env&nbsp;corr.</p>
<p><b>Why it matters.</b> If the m4a serving step is transparent (env corr ≈ the 320k anchor), then all
the clarity loss you hear is the SAME codec — the thing the HF-recovery work targets — not the download.
Use the player below to <b>hold one musical moment and switch codecs</b>; your ears are the verdict.</p>
</div>

<h2>The ladder — high-frequency detail retention</h2>
<table><thead><tr>
<th style="text-align:left">version</th>
<th>air env&nbsp;corr<br>8–16k ★</th><th>presence env&nbsp;corr<br>4–8k</th>
<th>crest&nbsp;ret<br>8–16k</th><th>flat&nbsp;Δ<br>8–16k</th><th>rolloff&nbsp;Hz</th>
</tr></thead><tbody>
{table}
</tbody></table>
<p class="legend">★ headline. Greener = closer to the original / better detail retention; redder = worse.
The <b>SAME</b> row is outlined; <b>Original</b> is the reference the metrics are measured against
(its own env corr = 1 by definition, shown as reference).</p>

<h2>Listen — hold the moment, switch the codec</h2>
<p class="legend">All versions play in lockstep on one clock; clicking a codec solos it — sample-accurate, no reseek. Press play, then click any codec — playback keeps its
position so you A/B the exact same instant. All versions are delivered <b>losslessly (FLAC)</b> so no
extra codec masks the difference; they're time-aligned so switching doesn't jump.</p>
{players_html}

<footer>
Method: <code>hf_clarity_diagnosis.py</code> — per clip, each version vs original, Hilbert-envelope
correlation per band after envelope-xcorr time alignment. SAME = SA3 medium-base pretransform
encode→decode. MP3 = libmp3lame; m4a = native ffmpeg AAC (our exact serving codec), at the marked
kbps. Values are means over n={n} clips. Reproducible from the script; no checkpoint filenames or
paths are published (spec §4).
</footer>
</div>
<script>
/* Sample-accurate codec A/B (Kim 2026-08-07: "keep all of them playing simultaneously, and only
   solo the one being played").

   WHY THE REWRITE: the old player had ONE <audio> and switched codecs by setting .src + load()
   + re-seeking. That reload is exactly the jump Kim heard -- and even a perfect seek only lands
   on a decoder frame boundary, so an A/B could never be sample-aligned.

   WHY WEB AUDIO, not several <audio> elements playing at once: parallel media elements each run
   their own clock and drift apart within seconds, so "all playing, one unmuted" would still not
   be sample-accurate. Here every variant of a clip is decoded into one AudioContext and all its
   sources are started with a SINGLE start() timestamp and a shared offset, so they stay
   sample-locked by construction; switching only moves gain. 8s mono clips = ~1.4 MB decoded per
   variant, ~10 MB for a clip's seven -- cheap enough to hold them all.

   Decode is lazy (first play of that player) so opening the page still costs nothing. */
document.querySelectorAll('.player').forEach(P=>{{
  const pp=P.querySelector('.pp'), scrub=P.querySelector('.scrub'), fill=P.querySelector('.fill'),
        time=P.querySelector('.time'), now=P.querySelector('.now'),
        btns=[...P.querySelectorAll('.vb')];
  const legacy=P.querySelector('audio'); if(legacy) legacy.remove();   // superseded by Web Audio

  let loadPromise=null;
  const LOOP=P.dataset.loop==='1';        // beat-synced clips loop seamlessly (whole bars)
  let ctx=null, buffers=null, srcs=null, gains=null, dur=0, startedAt=0, offset=0,
      playing=false, active=btns.find(b=>b.dataset.init)||btns[0], loading=false;
  const RAMP=0.008;                       // 8 ms gain ramp -- inaudible, but kills switch clicks
  const DIFF_BOOST=8;                     // +18 dB, applied EQUALLY to every difference so the
                                          // residuals stay comparable to each other by ear
                                          // (mp3_128 really is a louder residual than m4a_320).
  const origIdx=btns.findIndex(b=>b.dataset.init) >= 0 ? btns.findIndex(b=>b.dataset.init) : 0;
  let master=null, diffOn=false;           // diffOn = play (original - active), not the codec
  // Δ buttons, generated so the markup stays in one place (Kim 2026-08-07: 'a difference button
  // above each codec'). The original has no Δ -- its difference with itself is silence.
  const dbtns=btns.map((b,i)=>{{
    const col=document.createElement('div'); col.className='vcol';
    const d=document.createElement('button'); d.className='db'; d.textContent='Δ';
    d.title=(i===origIdx)?'the reference itself — no difference to play'
      :'play ONLY what this codec threw away: original minus this version, sample-aligned and\\n'
       +'boosted +18 dB. Silence = transparent. All Δ share one boost, so louder = worse.';
    if(i===origIdx) d.disabled=true;
    b.parentNode.insertBefore(col,b); col.appendChild(d); col.appendChild(b);
    d.onclick=()=>{{ if(i===origIdx) return; diffOn=!(diffOn&&active===b); active=b; applyGains(); }};
    return d;
  }});                       // 8 ms gain ramp -- inaudible, but kills switch clicks
  const fmt=s=>isFinite(s)?(Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0')):'0:00';
  // looping sources never end, so the readout has to wrap instead of clamping
  const pos=()=> !playing ? offset
    : (LOOP ? (offset + (ctx.currentTime-startedAt)) % dur
            : Math.min(dur, offset + (ctx.currentTime-startedAt)));

  // Concurrent callers must AWAIT the same load, not early-return: a second play-click during the
  // multi-second decode used to return immediately and then hit startAt with buffers still null.
  function load(){{ return loadPromise || (loadPromise = _load()); }}
  async function _load(){{
    if(buffers) return;
    loading=true; now.textContent='loading all versions…';
    ctx=new (window.AudioContext||window.webkitAudioContext)();
    master=ctx.createGain(); master.gain.value=1; master.connect(ctx.destination);
    const bufs=await Promise.all(btns.map(async b=>{{
      const r=await fetch(b.dataset.src);
      if(!r.ok) throw new Error(b.dataset.src+' -> '+r.status);
      return ctx.decodeAudioData(await r.arrayBuffer());
    }}));
    buffers=bufs; dur=Math.max(...bufs.map(b=>b.duration));
    loading=false; now.textContent=active.textContent;
    time.textContent=fmt(0);
  }}

  function stopSources(){{
    if(srcs) srcs.forEach(s=>{{ try{{s.stop();}}catch(e){{}} try{{s.disconnect();}}catch(e){{}} }});
    if(gains) gains.forEach(g=>{{ try{{g.disconnect();}}catch(e){{}} }});
    srcs=null; gains=null;
  }}

  // Every variant starts on the SAME start() call with the SAME offset -> sample-locked.
  function startAt(where){{
    stopSources();
    offset=Math.max(0,Math.min(where,dur-0.001));
    srcs=[]; gains=[];
    const t0=ctx.currentTime+0.03;                 // small lead so all sources arm before t0
    buffers.forEach((buf,i)=>{{
      const s=ctx.createBufferSource(), g=ctx.createGain();
      s.buffer=buf; s.loop=LOOP; s.connect(g); g.connect(master);
      g.gain.value = gainFor(i);                   // solo (or difference) by gain, not by playback
      s.start(t0, offset);
      srcs.push(s); gains.push(g);
    }});
    startedAt=t0; playing=true; pp.textContent='⏸';
    if(!LOOP) srcs[0].onended=()=>{{ if(playing && pos()>=dur-0.05){{ playing=false; pp.textContent='▶'; offset=0; stopSources(); }} }};
  }}

  // In difference mode the ORIGINAL plays at +1 and the selected codec at -1, summing to exactly
  // the codec's error signal. Sample-alignment is what makes this a real null test: verified on
  // disk (identical length, zero lag, xcorr >= 0.9997 across variants).
  function gainFor(i){{
    if(!diffOn) return btns[i]===active ? 1 : 0;
    if(i===origIdx) return 1;
    return btns[i]===active ? -1 : 0;
  }}
  function applyGains(){{
    btns.forEach(x=>x.classList.toggle('on',x===active&&!diffOn));
    dbtns.forEach((d,i)=>d.classList.toggle('on',diffOn&&btns[i]===active));
    now.textContent = loading ? 'loading all versions…'
      : (diffOn ? 'Δ '+active.textContent+' — what it threw away (+18 dB)' : active.textContent);
    if(!gains) return;
    const t=ctx.currentTime;
    gains.forEach((g,i)=>{{ g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(g.gain.value,t);
      g.gain.linearRampToValueAtTime(gainFor(i), t+RAMP); }});
    master.gain.cancelScheduledValues(t); master.gain.setValueAtTime(master.gain.value,t);
    master.gain.linearRampToValueAtTime(diffOn?DIFF_BOOST:1, t+RAMP);
  }}
  function solo(b){{
    active=b; diffOn=false; applyGains();
  }}

  // Every click gets an epoch. Pausing bumps it, so a start that is still waiting on the decode
  // is superseded instead of firing afterwards -- that stale start was audio you could not stop
  // (Kim 2026-08-07: "when I stop one of the shorter clips, some content keeps playing").
  let epoch=0;
  pp.onclick=async()=>{{
    const mine=++epoch;
    try{{
      if(playing){{ offset=pos(); playing=false; pp.textContent='▶'; stopSources(); return; }}
      await load();
      if(mine!==epoch) return;                       // superseded while decoding
      if(ctx.state==='suspended') await ctx.resume();
      if(mine!==epoch) return;
      startAt(offset>=dur-0.05?0:offset);
    }}catch(e){{ now.textContent='audio failed to load'; console.error(e); }}
  }};
  btns.forEach(b=>b.onclick=()=>solo(b));          // switching never touches transport
  scrub.onclick=async e=>{{
    try{{
      await load();
      const r=scrub.getBoundingClientRect(), where=(e.clientX-r.left)/r.width*dur;
      if(playing) startAt(where); else {{ offset=where; fill.style.width=(100*where/dur)+'%'; time.textContent=fmt(where); }}
    }}catch(e){{ console.error(e); }}
  }};

  (function tick(){{
    if(dur){{ const p=pos(); fill.style.width=(100*p/dur)+'%'; time.textContent=fmt(p); }}
    requestAnimationFrame(tick);
  }})();

  btns.forEach(x=>x.classList.toggle('on',x===active));
  if(active) now.textContent=active.textContent;
}});
</script>
</body></html>'''
    (OUT / "index.html").write_text(html)
    print(f"[done] -> {OUT}/index.html  ({len(present)} versions, {len(clips)} players)")


if __name__ == "__main__":
    main()
