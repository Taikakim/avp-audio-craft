#!/usr/bin/env python3
"""build_onset_narrative_page.py -- the onset-density control-adapter STORY page
(Kim's ask, relayed via dialogue 2026-07-10ish: "these [onset_* dump pages] are
kind of useless now, coordinate with the team to dig in their memories to
annotate the runs, create a narrative on the landing page about how the
experiments went and where each falls in the timeline. Eventually the user
should easily see which tests are our bpm-controlled, quite good working
versions.")

Source of truth: docs/onset-density-control-narrative.md -- GHOST-NOTE's first-
draft reconstruction (WORKLOG + journals + on-disk run_meta), reviewed by
CONTINUITY (doc SS5) and closed on the metric axis by WINTERMUTE's p95-gated
re-score (doc SS6, eval/onset_rescore_p95.json). The doc's own headline: the
record is CONTESTED, not settled -- the metric picks FusionCC, Kim's dated
07-07 ear-verdict picks plain Fusion, and nobody has ever actually auditioned
them head-to-head on the clip-fixed, doubly-confirmed-accurate pair. This page
doesn't just report that gap -- it puts both checkpoints' full density x gain
grid side by side so a visitor (or Kim) can close it by listening.

Run: python3 Misc/build_onset_narrative_page.py  ->  ~/evals_aac/onset_narrative.html
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path.home() / "evals_aac"
CONTROL_RUNS = STAGE / "control_runs"
RESCORE = ROOT / "eval/onset_rescore_p95.json"
OUT = STAGE / "onset_narrative.html"

CHECKPOINTS = {
    "E": {"dir": "E_fusion_v2", "label": "plain Fusion", "color": "#5cf",
          "run": "onset_Fusion_lr1e-4_randomcrop", "gain": "1.75"},
    "CC": {"dir": "A_cc_v2", "label": "FusionCC", "color": "#f95",
           "run": "onset_FusionCC_lr1e-4_randomcrop", "gain": "1.75"},
}
PROMPTS = ["aggressive upbeat goa trance",
           "energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine",
           "psytrance, 140 bpm"]
SEEDS = [1234, 4242]
GAINS = [1, 2, 3]
DENSITIES = [1, 3, 5, 6, 7, 7.5, 8, 9, 12]


def dnum(x):
    return str(int(x)) if float(x) == int(x) else str(x)


def clip_rel(ck_key, p_idx, seed, gain, dens):
    d = CHECKPOINTS[ck_key]
    fname = f"{d['dir']}_p{p_idx}_s{seed}_g{int(gain)}_d{dnum(dens)}.m4a"
    return f"control_runs/{d['dir']}/{fname}"


def clip_exists(rel):
    return (STAGE / rel).exists()


rescore = json.loads(RESCORE.read_text()) if RESCORE.exists() else {}


CSS = """
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1100px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:19px;margin:0 0 6px}h2{font-size:15px;color:#9cf;margin:26px 0 6px}
h3{font-size:13px;color:#8ac;margin:16px 0 4px}.muted{color:#888}
p{line-height:1.55;max-width:900px}
a{color:#7cf}
#explain{background:#12181c;border:1px solid #263038;border-left:3px solid #5b9;padding:10px 12px;
font-size:12.5px;color:#cde;margin:10px 0;max-width:900px;line-height:1.55}#explain b{color:#8ec}
.verdict{background:#1a1710;border:1px solid #433;border-left:3px solid #d90;padding:12px 14px;
margin:14px 0;max-width:900px}.verdict h2{margin:0 0 8px;color:#fc6}
.verdict .metric{color:#f95}.verdict .ear{color:#5cf}
.contested{background:#141418;border:1px solid #2a2a30;border-radius:6px;padding:8px 10px;margin:8px 0;
font-size:12.5px;color:#ccc;line-height:1.5}
.timeline{border-left:2px solid #2a3a44;margin:10px 0 10px 6px;padding-left:16px}
.phase{margin:14px 0;max-width:900px}.phase h3{margin:0 0 3px}.phase .when{color:#789;font-size:11px}
.phase ul{margin:6px 0;padding-left:18px;font-size:12.5px;line-height:1.55;color:#ddd}
.phase li{margin:3px 0}.phase b{color:#eee}
table.grid{border-collapse:collapse;font-size:12px;margin:6px 0}
.grid td,.grid th{border:1px solid #262a2e;padding:3px 5px;text-align:center}
.grid th{background:#1a1c20;color:#9ab}
.grid td.dens{background:#1a1c20;color:#9ab;text-align:left;font-weight:600}
.grid td.dens.sparse{color:#f95}
.playpair{display:flex;gap:4px;justify-content:center}
.c{cursor:pointer;border-radius:3px;padding:1px 6px;font-size:11px;font-weight:600}
.c.E{background:#173040;color:#7cf}.c.CC{background:#3a2415;color:#fa8}
.c:hover{outline:1px solid #7cf}.c.play{outline:2px solid #5d5 !important}
.c.loading{outline:2px solid #fa5 !important}
.legend{display:flex;gap:16px;align-items:center;margin:6px 0 10px;font-size:12px}
.legend .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
select{background:#1b1b20;color:#dde;border:1px solid #333;border-radius:4px;padding:4px 8px;font-size:12px}
.gaps{font-size:12.5px;line-height:1.6;max-width:900px}
.gaps li{margin:6px 0}.gaps .open{color:#e88}
.src{color:#667;font-size:11px;margin:20px 12px}
"""

PHASES = [
    ("Phase 0 -- Riffer, the false start that pointed the way", "2026-06-19/20",
     ["A reference-audio-conditioned adapter (\"riffer\") worked narrowly at lr1e-4 "
      "but a comprehensive eval showed it does NOT transfer mel/rhythm/timbre at all "
      "(MERIT&asymp;0). <b>Same session, the pivot:</b> swap to an explicit onset-density "
      "scalar head instead -- and it validates immediately: corr +0.90 at gain 1, "
      "requested sparse&rarr;dense maps cleanly to measured onsets/sec. <b>This one "
      "result is the origin of the whole control-adapter line.</b>"]),
    ("Phase 1 -- Optimizer/LR bracketing", "2026-06-20 &rarr; ~06-23",
     ["AdamW collapses at lr1e-4 (step 43,200, quality floor breached); the lr7.5e-5 "
      "arm stops mid-run with no recorded verdict (still an open gap). "
      "<b>FusionOpt wins by default</b> -- every serious checkpoint from here on is "
      "FusionOpt-trained, including the one behind the eventual ear-verdict."]),
    ("Phase 2 -- Baked into the low-VRAM inference path", "2026-06-27",
     ["The trained adapter folds into the ONNX DiT export as two extra inputs, "
      "validated bit-exact against torch. This CPU pipeline is what measured every "
      "correlation number in the rest of the story. <b>Same window:</b> LatCH "
      "sample-space guidance is swept across all 14 heads -- the onset/beat/downbeat "
      "activation family is dead at any weight. First sighting of a rule that holds "
      "for the rest of the campaign: <b>only the trained weight-space adapter "
      "steers onset density; gradient guidance never does.</b>"]),
    ("Phase 3 -- The Cautious-optimizer thread and a real divergence bug", "2026-06-30 &rarr; 07-02",
     ["A cautious-optimizer A/B turns up four negative-or-mixed results, plus the "
      "campaign's standing rule, minted here: <b>\"numbers are instruments, audition "
      "is the verdict\"</b> (a gameable-metric clip scored 12.9 onsets/s; Kim's ear "
      "caught the problem instantly, no metric did). Root-caused a real bug the same "
      "day: NS5's <code>1/keep_frac</code> rescale preserves mean magnitude but "
      "inflates update <i>norm</i> by <code>1/&radic;keep_frac</code> -- a hidden "
      "+37% effective LR at NS5's keep&asymp;0.53, harmless at AdamW's keep&asymp;0.9. "
      "This is what blew up a DoRA r128 cautious run's LoRA tensors to NaN between "
      "epoch 2 and 3."]),
    ("Phase 4 -- FusionCC: the campaign's first statistically significant win", "2026-07-02",
     ["Add a frozen, pretrained onset-density probe as a consistency loss on top of "
      "the diffusion objective (\"meter in the gradient\"). Result: corr at gain 2 "
      "goes .584&rarr;.880, a paired-bootstrap-significant win (P=.99) -- the "
      "campaign's only one. Mechanism: it fixes the SPARSE floor specifically "
      "(request-3 renders 5.7 onsets/s instead of every other head's ~6.0-6.9 "
      "floor); the upper ceiling doesn't move. <b>Open question, logged the same "
      "day: does CC actually play sparser, or does it just fool the onset "
      "detector? Kim's ears were always meant to decide this.</b>"]),
    ("Phase 5 -- Where meter-in-the-gradient breaks", "2026-07-03",
     ["The same recipe applied to a genre-consistency probe instead of onset "
      "density HURTS steering (Goa authority 0.92&rarr;0.65) -- the rule sharpens: "
      "meter-in-the-gradient only helps for properties the training loss is blind "
      "to (onset timing), not ones it already reconstructs (genre). Separately: "
      "the same frozen onset meter steers cleanly through WEIGHTS (this adapter) "
      "but not through SAMPLES (gradient guidance) -- contractive denoising erases "
      "the off-manifold perturbation guidance needs."]),
    ("Phase 6 -- The clipping bug, then the audition day", "2026-07-04 &rarr; 07-07",
     ["<b>07-04:</b> both CPU eval servers were hard-clipping audio since 06-27 -- "
      "every FusionCC audition before this date was on distorted output. Fixed; "
      "<code>E_fusion_v2</code>/<code>A_cc_v2</code> are the clean re-renders used "
      "everywhere on this page. <b>07-07, Kim's direct verdicts:</b> gain 6 \"never "
      "worked\" (pure overdrive, not a wiring bug) -- flat gain &asymp;1.75 becomes "
      "the new default. Then, going back to find the control clips he remembered "
      "as great, Kim landed on <code>E_fusion_v2</code> -- <b>plain Fusion FiLM, "
      "not the FusionCC checkpoint</b> -- titled in the journal as \"the ear-approved "
      "density control is PLAIN-Fusion FiLM, not FusionCC, not LatCH.\" This directly "
      "answers Phase 4's open question, on record, dated -- but nobody has ever "
      "gone back and actually re-run that audition against the clip-fixed FusionCC "
      "checkpoint. That's the gap this page's A/B section below is for."]),
]

GAPS = [
    ("open", "FusionCC vs. plain-Fusion, clean-audio, head-to-head",
     "Never actually done. The metric question is now closed (see below) but the "
     "audition question -- would Kim's ear still pick plain Fusion, knowing CC's "
     "edge is real and concentrated at the sparse floor? -- is not. Use the A/B "
     "grid on this page."),
    ("open", "onset_FUSION_lr2e5_40epoch's \"favourite, by ear\" claim",
     "A separate 40-epoch run has its own dated claim of being the favorite, never "
     "cross-examined against E_fusion_v2. The re-score put it at pooled corr 0.921 "
     "-- but on a wider density/gain grid, which mechanically inflates correlation, "
     "so it's not a fair comparison as-is."),
    ("closed", "Did the old, noisy onset detector (3x over-fire on drones) taint every number above?",
     "No -- WINTERMUTE's p95-gated re-score reproduced the FusionCC-over-plain-Fusion "
     "ranking on the honest meter (0.77 vs 0.717). The metric win is real, not a "
     "detector artifact."),
    ("closed", "Does the adapter's cross-attention injection make sense given onset density localizes to late self-attn/ff in the base model?",
     "Yes -- CONTINUITY's per-layer ablation shows late taps (blocks 16-23) carry "
     "essentially all the real authority (corr +0.45 alone vs. all-taps +0.91); "
     "early/mid taps aren't redundant, they keep the adapter's writes in-distribution "
     "(removing them is actively anti-correlated, -0.80). Write-site (cross-attn) "
     "and compute-site (late self-attn/ff) are different questions about a shared bus."),
]


def build_ab_grid():
    """One <select> pair (prompt, seed) driving a density x gain grid, each cell a
    [E][CC] pair pointing at the SAME coordinates in both checkpoints' clip sets --
    the actual head-to-head audition Gap #1 asks for, built as a listening tool."""
    n_have = sum(1 for p in range(3) for s in SEEDS for g in GAINS for d in DENSITIES
                for k in ("E", "CC") if clip_exists(clip_rel(k, p, s, g, d)))
    n_total = 3 * len(SEEDS) * len(GAINS) * len(DENSITIES) * 2
    html = []
    html.append(f'<div class="legend">'
                f'<span><span class="sw" style="background:{CHECKPOINTS["E"]["color"]}"></span>'
                f'E = plain Fusion (Kim\'s 07-07 pick)</span>'
                f'<span><span class="sw" style="background:{CHECKPOINTS["CC"]["color"]}"></span>'
                f'CC = FusionCC (the metric winner)</span>'
                f'<span class="muted">{n_have}/{n_total} clips staged</span></div>')
    html.append('<div>prompt <select id="abP" onchange="renderAB()">' +
               "".join(f'<option value="{i}">{p}</option>' for i, p in enumerate(PROMPTS)) +
               '</select> seed <select id="abS" onchange="renderAB()">' +
               "".join(f'<option value="{s}">{s}</option>' for s in SEEDS) +
               '</select></div>')
    html.append('<div id="abOut"></div>')
    return "\n".join(html)


def main():
    CONTROL_RUNS.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(parents=True, exist_ok=True)

    doc = [f"<!doctype html><html><head><meta charset=utf-8>"
          f"<title>The onset-density control-adapter story</title><style>{CSS}</style></head><body>"]
    doc.append('<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span>'
              ' <span id=ld class=muted style="color:#fa5"></span>'
              ' &nbsp;&middot;&nbsp; <span class=muted>same playhead across every cell &middot; '
              'loops until stopped &middot; amber outline = loading</span></div>')
    doc.append('<div id=wrap>')
    doc.append('<h1>The onset-density control-adapter story</h1>'
              '<a href=index.html>&larr; evals</a> &middot; <a href=onset_eval.html>onset_eval.html (the raw grid)</a>')

    doc.append('<div id=explain><b>What this tests:</b> whether a trained adapter can make SA3 render '
              'sparser or denser rhythm on request -- "give me a busier beat" actually working. '
              '<b>Why it matters:</b> this became the longest-running control-adapter investigation in '
              'the project, with real training bugs, a statistically significant metric win, and a '
              'documented case where the metric and Kim\'s own ear pointed different directions. '
              '<b>How to read this page:</b> the verdict box tells you where things stand right now; '
              'the A/B grid below it lets you actually run the one comparison that would settle it; '
              'the timeline underneath is the full story, in order, including the dead ends.</div>')

    doc.append('<div class="verdict"><h2>&#9733; Where things stand</h2>'
              '<p><b>By the correlation metric</b> (now independently confirmed on the corrected, '
              'p95-gated onset meter -- not a detector artifact): '
              '<span class="metric">FusionCC wins</span>, pooled corr 0.77 vs. plain Fusion\'s 0.717, '
              'concentrated at the sparse end of the range.</p>'
              '<p><b>By Kim\'s ear, on record and dated 2026-07-07</b> '
              '(<i>"the ear-approved density control is PLAIN-Fusion FiLM, not FusionCC, not LatCH"</i>): '
              '<span class="ear">plain Fusion is the working recipe</span> -- checkpoint '
              '<code>onset_Fusion_lr1e-4_randomcrop</code>, FiLM gain &asymp;1.75, recalibrate per '
              'checkpoint, stay within the trained range (roughly requests 4-10 onsets/sec).</p>'
              '<div class="contested">These two verdicts disagree and nobody has run the actual '
              'clean-audio head-to-head to settle it -- the 07-07 audition happened before FusionCC\'s '
              'clip-fixed re-render existed, and the metric re-score happened without a follow-up '
              'listen. <b>The A/B grid right below this box is exactly that missing comparison</b>, '
              'built from both checkpoints\' full density &times; gain sweep on the same prompts/seeds.</div>'
              '<p><b>Not contested:</b> LatCH sample-space guidance for onset density does not work, '
              'confirmed dead by mechanism and by ear, twice. Whichever adapter checkpoint you pick, '
              'guidance is not the alternative.</p></div>')

    doc.append('<h2>Listen for yourself -- the head-to-head nobody\'s run yet</h2>')
    doc.append(build_ab_grid())

    doc.append('<h2>The story, in order</h2><div class="timeline">')
    for title, when, paras in PHASES:
        doc.append(f'<div class="phase"><h3>{title}</h3><div class="when">{when}</div>'
                  f'<ul>' + "".join(f"<li>{p}</li>" for p in paras) + '</ul></div>')
    doc.append('</div>')

    doc.append('<h2>Open questions (honest, not glossed over)</h2><ul class="gaps">')
    for status, title, body in GAPS:
        mark = '<span class="open">&#9679; OPEN</span>' if status == "open" else '<span style="color:#5d9">&#9679; CLOSED</span>'
        doc.append(f'<li>{mark} <b>{title}</b><br>{body}</li>')
    doc.append('</ul>')

    doc.append(f'<p class="muted">Full reconstruction, per-run annotations, and every fleet '
              f'contributor\'s notes: <code>docs/onset-density-control-narrative.md</code> '
              f'(not republished here in full -- this page is the reader-facing distillation).</p>')
    doc.append('</div>')  # wrap

    doc.append(notes_block("onset_narrative",
                          levels=[("clip", "this clip"), ("model", "E vs CC overall"), ("page", "whole page")],
                          hint="click a clip in the A/B grid, or just leave a page-level note"))

    # shared single-<audio> player: click-only (no autoplay-on-hover per Kim's
    # 2026-07-20 correction), loops, amber .loading outline on the played cell.
    doc.append("""<audio id="pl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('pl');
a.loop=true;
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('play');cur=null}ph=0});
a.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';if(cur)cur.classList.add('loading')});
a.addEventListener('playing',()=>{document.getElementById('ld').textContent='';if(cur)cur.classList.remove('loading')});
function seekAndPlay(pos){
 const go=()=>{try{const d=a.duration||1e9;a.currentTime=(pos>d-1)?0:Math.min(pos,d-0.05)}catch(e){}a.play()};
 if(a.readyState>=3){go();return}
 let done=false;const fire=()=>{if(done)return;done=true;go()};
 a.addEventListener('canplay',fire,{once:true});setTimeout(fire,1200)}
function play(el){const f=el.dataset.src;if(!f)return;
 if(window.noteSet)noteSet({model:el.dataset.model||'',ckpt:'',clip:f.split('/').pop()});
 if(cur===el){a.pause();el.classList.remove('play','loading');cur=null;document.getElementById('ld').textContent='';return}
 if(cur)cur.classList.remove('play','loading');
 document.getElementById('ld').textContent='loading…';
 a.pause();a.src=f;seekAndPlay(ph);cur=el;el.classList.add('play')}

const CK=""" + json.dumps({k: v["dir"] for k, v in CHECKPOINTS.items()}) + """;
const DENSITIES=""" + json.dumps(DENSITIES) + """;
const GAINS=""" + json.dumps(GAINS) + """;
function clipRel(k,p,s,g,d){
 const dn=(d===Math.trunc(d))?String(Math.trunc(d)):String(d);
 return `control_runs/${CK[k]}/${CK[k]}_p${p}_s${s}_g${Math.trunc(g)}_d${dn}.m4a`}
function renderAB(){
 const p=document.getElementById('abP').value, s=document.getElementById('abS').value;
 let h='<table class="grid"><tr><th>density</th>' + GAINS.map(g=>`<th colspan=2>gain ${g}</th>`).join('') + '</tr>';
 for(const d of DENSITIES){
  const sparse = (d===3);
  h += `<tr><td class="dens${sparse?' sparse':''}">${d}${sparse?' ★ sparse floor':''}</td>`;
  for(const g of GAINS){
   h += '<td><div class="playpair">';
   for(const k of ['E','CC']){
    const rel=clipRel(k,p,s,g,d);
    h += `<span class="c ${k}" data-src="${rel}" data-model="${CK[k]}" onclick="play(this)">${k}</span>`;}
   h += '</div></td>';}
  h += '</tr>';}
 h += '</table>';
 document.getElementById('abOut').innerHTML=h}
renderAB();
</script>""")

    doc.append('<footer class="src">aavepyora.online &middot; evals &middot; onset-density control-adapter story &middot; '
              'sources: WORKLOG.md, profiles/*.journal.md, docs/onset-density-control-narrative.md, '
              'eval/onset_rescore_p95.json &middot; clips: sa3_control_runs/composed_sweep (internal)</footer>')
    doc.append('</body></html>')

    OUT.write_text("\n".join(doc))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
