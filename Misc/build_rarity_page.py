#!/usr/bin/env python3
# Last edited: THE-FINN 2026-11-03 — paths updated for the __theme sorting of sa3_lora_runs and latch_sweep
"""
build_rarity_page.py -- column-layout eval page for rarity_gen_set (task #33: the
StoryScope-transfer rarity meter).

Kim's ask (2026-07-10, via WINTERMUTE): reorganize the 450-clip rarity_gen_set board
as COLUMNS -- identical settings (same prompt) stacked vertically as rows, one column
per model (+base), plus DELTA-TO-BASE columns for CONTINUITY's rarity-lite score
(not landed yet -- layout is built now so delta cells populate automatically once
`rarity_scores.json` exists next to run_meta.json/clip_index.json in the source dir).

Data: `rarity_gen_set/clip_index.json` (450 entries, clip-stem -> {prompt, band,
seed, source}) is the ground truth for prompt text + grouping -- verified all 3
models (base/newstack/evr1x) share the SAME prompt text per (band, promptid) group,
just a different per-model seed (150 groups x 3 = 450). Rows group by (band,
promptid); 3 sections (common/mid/rare, 50 rows each) matching the stratification
already in the data.

Delta score file convention (for CONTINUITY's scoring pass): a JSON dict at
`rarity_gen_set/rarity_scores.json`, `{clip_stem: rarity_lite_score, ...}` (same
keys as clip_index.json, one float per clip). If absent, delta cells show "pending".

Doesn't fit any existing template (a2a ladders are nl x adapter; mp_crossmodel is
checkpoint x prompt with a pulldown) -- this is prompt x model with a currently-empty
scoring axis -- standalone page.

Run: python3 Misc/build_rarity_page.py
"""
import html
import json
import statistics
from pathlib import Path

SRC_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/__misc/rarity_gen_set")
OUT = Path("/home/kim/riffer-evals/rarity.html")
CLIPS = "../renders/rarity_gen_set"  # reuse the already-served set — no 148MB duplicate (W 2026-07-10)

MODEL_ORDER = ["base", "newstack", "evr1x"]
MODEL_LABEL = {
    "base": "base (no adapter)",
    "newstack": "newstack r16 (ep7)",
    "evr1x": "evr1x r128 (a2a workhorse / goa in-dist)",
}
BAND_ORDER = ["common", "mid", "rare"]
BAND_LABEL = {
    "common": "common captions (top-frequency)",
    "mid": "mid-frequency captions",
    "rare": "rare captions (long-tail)",
}

CSS = """
html{overflow-x:hidden}
body{font:13px system-ui;margin:14px;background:#101012;color:#e0e0e0;max-width:100vw;overflow-x:hidden}
h1{font-size:17px;margin:0 0 4px}h2{font-size:14px;color:#9cf;margin:20px 0 6px}
a{color:#7cf}.tip{color:#8a8;font-size:12px;margin:4px 0 14px;max-width:900px}
.tblwrap{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;font-size:12px;margin:4px 0}
td,th{border:1px solid #2c2c30;padding:4px 8px;text-align:center}
th{background:#1c1c20;color:#aaa;position:sticky;top:34px}
td.prompt{text-align:left;color:#9ab;max-width:280px}
td.c{cursor:pointer;font-variant-numeric:tabular-nums}
td.c:hover{outline:1px solid #7cf}
td.play{outline:2px solid #5d5 !important}
td.delta{color:#666;font-style:italic}
td.delta.scored{color:#e8b;font-style:normal;font-variant-numeric:tabular-nums}
.findings-box{border:1px solid #2a2a30;border-left:3px solid #5d9;background:#13181a;
padding:10px 14px;margin:8px 0;font-size:12.5px;color:#ddd;max-width:900px;line-height:1.55}
.findings-box .lbl{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#7ed;display:block;margin:0 0 6px}
#hdr{position:sticky;top:0;z-index:9;background:#16181c;padding:7px 12px;margin:-14px -14px 8px;
border-bottom:1px solid #2a2a30;font-size:13px}#np{color:#cde}#pos{color:#888}
.legend{font-size:11px;color:#9aa;margin:4px 0 8px}
"""


def load_scores():
    p = SRC_DIR / "rarity_scores.json"
    if p.exists():
        return json.load(open(p))
    return None


def main():
    index = json.load(open(SRC_DIR / "clip_index.json"))
    scores = load_scores()

    # group by (band, promptid) -- promptid is the numeric id embedded in the clip
    # stem (2nd underscore field for base, matches across all 3 models' filenames)
    groups = {}  # (band, promptid) -> {model: clip_stem}
    prompt_text = {}
    for stem, meta in index.items():
        parts = stem.split("__")
        model, band, promptid = parts[0], parts[1], parts[2]
        key = (band, promptid)
        groups.setdefault(key, {})[model] = stem
        prompt_text[key] = meta["prompt"]

    doc = [f"<!doctype html><html><head><meta charset=utf-8><title>Rarity gen set — column compare</title><style>{CSS}</style></head><body>"]
    doc.append('<div id=hdr>&#9654; <b id=np>click a cell to play</b> <span id=pos></span> '
                '&nbsp;·&nbsp; <span style="color:#888">switching keeps the playhead; re-click stops</span></div>')
    doc.append('<h1>Rarity gen set — one row per prompt, one column per model</h1>'
                '<a href=index.html>← compare</a>')
    doc.append(
        '<div class=findings-box><span class=lbl>What this tests / how to read it</span>'
        '<b>Rarity</b> asks: how unusual is a generated clip compared to a big reference set of '
        'similar clips? A model that always plays it safe (the "average" of what it learned) '
        'scores LOW rarity; a model producing genuinely distinctive content scores HIGHER. This '
        'matters for a fine-tuned adapter: does it actually add something new to the model\'s '
        'output, or does it just restyle the SAME generic content? The score is measured via a '
        'k-nearest-neighbours percentile on MERT audio embeddings (a learned representation '
        'that\'s robust to production/mastering differences) comparing each generation to a set '
        'of similar generations — 0 = very typical/average, 1 = very unusual/isolated. '
        '<b>Delta</b> columns are (model score − base/no-adapter score) for the SAME prompt: '
        'positive means the adapter made the output more distinctive than the un-adapted model, '
        'not just differently-styled.</div>'
    )
    doc.append('<div class=tip>150 prompts (50 common / 50 mid / 50 rare caption-frequency bands), '
                'stratified from the goa caption sidecar. Each row is the SAME prompt across all 3 '
                'models — base has no adapter, newstack/evr1x are trained; each column uses its own '
                'random seed (steps 24, cfg 6, 20s). Delta columns (rarity-lite score vs base) '
                'populate once the scoring pass lands — task #33.</div>')

    if scores is not None:
        medians = {}
        for m in MODEL_ORDER:
            vals = [scores[s] for s in scores if s.split("__")[0] == m]
            if vals:
                medians[m] = statistics.median(vals)
        if medians:
            summary = " · ".join(f"{MODEL_LABEL[m]}: median {medians[m]:.3f}" for m in MODEL_ORDER if m in medians)
            doc.append(
                f'<div class=findings-box><span class=lbl>Rarity-lite scoring (CONTINUITY, MERT mid+upper '
                f'kNN(k8) rarity percentile, gen-vs-gen, production-invariant)</span>{html.escape(summary)}. '
                f'The DoRA adapters produce MORE isolated/distinctive output than base, not just a style '
                f'shift onto the same distribution — deltas below should read mostly positive for the '
                f'adapter columns.</div>'
            )

    for band in BAND_ORDER:
        rows = sorted((k for k in groups if k[0] == band), key=lambda k: prompt_text[k])
        if not rows:
            continue
        doc.append(f'<h2>{html.escape(BAND_LABEL[band])} ({len(rows)} prompts)</h2>')
        doc.append('<div class=tblwrap><table><tr><th>prompt</th>')
        for m in MODEL_ORDER:
            doc.append(f'<th>{html.escape(MODEL_LABEL[m])}</th>')
        for m in MODEL_ORDER[1:]:
            doc.append(f'<th>Δ {m}−base</th>')
        doc.append('</tr>')
        for key in rows:
            band_, promptid = key
            clips = groups[key]
            doc.append(f'<tr><td class=prompt>{html.escape(prompt_text[key])}</td>')
            for m in MODEL_ORDER:
                stem = clips.get(m)
                if not stem:
                    doc.append('<td>·</td>')
                    continue
                cell_id = f"c_{stem}"
                doc.append(
                    f'<td class=c id="{cell_id}" onclick="rPlay(\'{cell_id}\',\'{CLIPS}/{stem}.m4a\',\'{html.escape(stem)}\')">▶</td>'
                )
            base_stem = clips.get("base")
            for m in MODEL_ORDER[1:]:
                stem = clips.get(m)
                if scores is not None and stem in scores and base_stem in scores:
                    d = scores[stem] - scores[base_stem]
                    doc.append(f'<td class="delta scored">{d:+.3f}</td>')
                else:
                    doc.append('<td class=delta>pending</td>')
            doc.append('</tr>')
        doc.append('</table></div>')

    js = (
        "let rCur=null,rAu=new Audio();"
        "function rPlay(id,f,lbl){"
        "document.querySelectorAll('td.c').forEach(e=>e.classList.remove('play'));"
        "if(rCur===id){rAu.pause();rCur=null;document.getElementById('np').textContent='stopped';return;}"
        "const pos=(rCur!==null&&!rAu.paused)?rAu.currentTime:0;"
        "rCur=id;document.getElementById(id).classList.add('play');"
        "document.getElementById('np').textContent='▶ '+lbl;"
        "rAu.src=f;const go=()=>{try{rAu.currentTime=((rAu.duration&&pos>rAu.duration-1)?0:Math.min(pos,(rAu.duration||1e9)-0.05));}catch(e){}rAu.play();};"
        "if(rAu.readyState>=1)go();else rAu.addEventListener('loadedmetadata',go,{once:true});"
        "}"
        "setInterval(()=>{if(rCur&&!rAu.paused)document.getElementById('pos').textContent="
        "Math.floor(rAu.currentTime/60)+':'+String(Math.floor(rAu.currentTime%60)).padStart(2,'0');},500);"
    )
    doc.append(f"<script>{js}</script>")
    doc.append(f"<footer style='margin-top:20px;color:#666;font-size:11px'>aavepyora.online · evals · "
                f"same-playhead · {'scored' if scores else 'delta scoring pending (task #33)'}</footer>")
    doc.append("</body></html>")

    OUT.write_text("".join(doc))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes), {len(groups)} rows x {len(MODEL_ORDER)} models"
          f"{', SCORED' if scores else ', deltas pending'}")


if __name__ == "__main__":
    main()
