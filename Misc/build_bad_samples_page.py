#!/usr/bin/env python
"""build_bad_samples_page.py — GHOST-NOTE 2026-09-24, Kim's ask: "we could have a site... which
references bad sample statistics and offers auditioning." Stdlib-only generator (no Claude
tokens to rebuild): joins clip_metrics.db's n_bad_jumps (audio_corruption_scan.py's amplitude-
jump count, see its docstring) against manifest_live.jsonl for prompt/model/ckpt context, and
renders the worst clips as playable same-playhead audio cells -- the standing eval-page
convention (MASTER.md: "every eval page... clickable same-playhead audio cells").

CALIBRATION CAVEAT, read before trusting a row here (Kim direct, 2026-09-24): the jump count is
a SCREEN, not a verdict -- a handful of jumps often blend into the mix inaudibly, only a LOT
sounds audibly bad. This page exists to let Kim's ear settle where that line actually falls,
not to assert it. The one count that IS unconditional is the 999999 sentinel (non-finite latent
-> literal silence/DC, see MASTER.md sec5) -- shown in its own section, not mixed into the
ranked list, since it isn't "a lot of jumps", it's a different failure entirely.

Run: Misc/build_bad_samples_page.py [--top N]  (default N=300 per section)
Writes eval/bad_samples.html + a staged copy at ~/evals_aac/bad_samples.html (same convention
as build_dora_table_page.py) so it can use the same relative model_matrix/ audio paths.
"""
import argparse
import json
import sqlite3
from pathlib import Path

DB = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")
MANIFEST = Path.home() / ".cache/evals_aac/model_matrix/manifest_live.jsonl"
OUT = Path("/home/kim/Projects/SAO/eval/bad_samples.html")
STAGED = Path.home() / "evals_aac/bad_samples.html"


def load_manifest():
    by_file = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text().splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            by_file[e["file"]] = e
    return by_file


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=300)
    a = ap.parse_args()

    by_file = load_manifest()
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cur.execute("SELECT path, n_bad_jumps FROM metrics WHERE n_bad_jumps IS NOT NULL AND path LIKE '%.m4a'")
    rows = cur.fetchall()
    con.close()

    corrupted, nonfinite = [], []
    n_unstaged = 0
    for path, n in rows:
        fname = Path(path).name
        e = by_file.get(fname)
        if e is None:
            n_unstaged += 1
            continue
        rec = {**e, "n_bad": n}
        (nonfinite if n >= 999999 else corrupted).append(rec)
    corrupted.sort(key=lambda r: -r["n_bad"])
    nonfinite.sort(key=lambda r: r["model"])

    n_corrupted_total, n_nonfinite_total = len(corrupted), len(nonfinite)
    corrupted = [r for r in corrupted if r["n_bad"] > 0][: a.top]
    nonfinite = nonfinite[: a.top]

    def cell(r):
        label = f"{r['model']} {r['ckpt']} · cfg{r['cfg']:g} w{r['strength']:g} · {r['prompt_id']}"
        return (
            f'<tr class=row data-file="{r["file"]}" data-label="{label}">'
            f'<td class=n>{r["n_bad"]}</td><td class=play>▶</td>'
            f'<td class=lbl title="{r["prompt_text"]}">{label}</td></tr>'
        )

    html = f"""<!doctype html><html><head><meta charset=utf-8>
<title>Bad-sample audit</title>
<style>
body{{font:14px/1.4 system-ui,sans-serif;background:#0b0d10;color:#ccd;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{color:#889;max-width:70ch;margin:0 0 20px}}
.sub b{{color:#dde}}
table{{border-collapse:collapse;width:100%;max-width:900px;margin-bottom:32px}}
td{{padding:4px 10px;border-bottom:1px solid #223}}
.n{{text-align:right;font-variant-numeric:tabular-nums;color:#f76;width:5em}}
.play{{cursor:pointer;width:2em;text-align:center;color:#7ed}}
.row.playing td{{background:#152018}}
.row.playing .play{{color:#fff}}
.lbl{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:60ch}}
.count{{color:#667;font-size:12px}}
#plabel{{position:sticky;top:0;background:#0b0d10;padding:8px 0;color:#7ed;z-index:1}}
</style></head><body>
<h1>Bad-sample audit</h1>
<p class=sub>Ranked by <b>audio_corruption_scan.py</b>'s per-clip amplitude-jump count
(<code>n_bad_jumps</code> in <code>clip_metrics.db</code>). <b>This count is a screen, not a
verdict</b> (Kim direct 2026-09-24) — a handful of jumps often blends into the mix inaudibly;
only a large count reliably sounds bad. Click a row to listen and judge for yourself. Showing
top {len(corrupted)} of {n_corrupted_total} corrupted clips currently staged
({n_unstaged} more scored but not currently on the served board).</p>
<div id=plabel>click a row to play</div>
<table><tbody>
{''.join(cell(r) for r in corrupted)}
</tbody></table>
<h1>Non-finite latents (DC-constant, not "a lot of jumps")</h1>
<p class=sub>A fully non-finite latent decodes to a full-scale DC constant, not noise — the
amplitude-jump screen above is blind to it by construction (MASTER.md §5). Different failure
class: evidence about the checkpoint, not a loud version of the same problem.
Showing {len(nonfinite)} of {n_nonfinite_total}.</p>
<table><tbody>
{''.join(cell(r) for r in nonfinite)}
</tbody></table>
<audio id=pl></audio>
<script>
const pl=document.getElementById('pl'),plabel=document.getElementById('plabel');
let ph=0,playingRow=null;
function seekAndPlay(){{
 const go=()=>{{try{{const d=pl.duration||1e9;pl.currentTime=(ph>d-0.5)?0:Math.min(ph,d-0.05);}}catch(e){{}}pl.play();}};
 if(pl.readyState>=2){{go();return;}}
 let done=false;const fire=()=>{{if(done)return;done=true;go();}};
 pl.addEventListener('loadedmetadata',fire,{{once:true}});setTimeout(fire,1500);}}
document.querySelectorAll('tr.row').forEach(tr=>{{
 tr.addEventListener('click',()=>{{
  if(playingRow===tr){{pl.pause();playingRow.classList.remove('playing');playingRow=null;
   plabel.textContent='click a row to play';return;}}
  if(playingRow)playingRow.classList.remove('playing');
  playingRow=tr;tr.classList.add('playing');
  plabel.textContent='▶ '+tr.dataset.label;
  pl.pause();pl.src='model_matrix/'+tr.dataset.file;seekAndPlay();}});}});
pl.addEventListener('timeupdate',()=>{{ph=pl.currentTime;}});
</script>
</body></html>"""
    OUT.write_text(html)
    STAGED.parent.mkdir(parents=True, exist_ok=True)
    STAGED.write_text(html)
    print(f"[bad-samples-page] {len(corrupted)} corrupted + {len(nonfinite)} non-finite rows "
          f"-> {OUT} (+ staged copy)")


if __name__ == "__main__":
    main()
