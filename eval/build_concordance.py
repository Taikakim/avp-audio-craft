#!/usr/bin/env python3
"""Concordance table — join trajectory analysis, acoustic descriptors, and human
votes onto ONE row per (model, ckpt), so the three surfaces can finally be compared.

WHY (Kim, 2026-09-21): the Antigravity checkpoint-trajectory sweep (frob_norm,
velocity_per_1k, directional_cosine per checkpoint) and the existing evaluation data
(eval/clap_dora_aggregate.csv acoustic descriptors, eval/ratings_export_*.jsonl human
A/B votes) use two DIFFERENT identity schemes and had never been joined:

  - checkpoint_analysis_summary.csv keys on `run_name` (sometimes a human recipe name
    like "adamw_avp_t512_bs1_lr1e4", sometimes a raw wandb run-id hash like "2ankrkoh",
    sometimes a bare condition label like "A_control") + `epoch`.
  - clap_dora_aggregate.csv and the vote exports key on `model` (always the human
    recipe name) + `ckpt` (a string like "ep7" or "adapter").

Exact string match on (run_name -> model, epN -> ckpt) resolves a real majority of
rows (177/354 descriptor models, 81/389 trajectory run_names, as of 2026-09-21) but
NOT all of them -- wandb-hash and bare condition-label run_names have no recipe name
anywhere in this repo to resolve against. NO FUZZY MATCHING is attempted: a wrong
join here silently mislabels a checkpoint's quality data, which is worse than the gap
it would be covering (the model_census "false presence is worse than false absence"
rule, see build_model_census.py). Unresolved identities are reported, not guessed at.

Votes are NOT collapsed to one win-rate. Kim: "I vote high score both for well
produced and interesting despite worse timbre" -- ratings_export_*.jsonl already
tags each pairwise vote with a `question_id` (production / interesting /
spectral_image / structure / clarity_meaning / top_end), so a single blended
win-rate would hide exactly the axis split the whole exercise is trying to see.
Each axis gets its own win-rate column.

Output: eval/concordance_table.csv (one row per model+ckpt) and .html (sortable,
same convention as model_census.html).

  eval/build_concordance.py
"""
from __future__ import annotations

import csv
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAO_ROOT = HERE.parent

TRAJECTORY_CSV = SAO_ROOT / "checkpoint_analysis_summary.csv"
DESCRIPTORS_CSV = HERE / "clap_dora_aggregate.csv"
RATINGS_FILES = sorted(HERE.glob("ratings_export_*.jsonl"))
CURATED_VOTES = HERE / "curated_votes_2026-09-08.jsonl"

# question_id axes worth their own column. "preference" (the tiny curated set) is
# handled separately since it also carries an explicit 1-5 rating, not just a choice.
VOTE_AXES = ("production", "interesting", "spectral_image", "structure",
            "clarity_meaning", "top_end")

DESCRIPTOR_FIELDS = ("pq", "ce", "cu", "pc", "clap_matched", "retrieval_rank",
                     "bpm", "centroid", "rms", "flux")

TRAJECTORY_FIELDS = ("step", "frob_norm_B", "velocity_per_1k", "directional_cosine",
                     "nan_count", "is_finite")


# Raw wandb run-id hashes resolved to their launch `--name` by Antigravity (via
# local wandb/*/files/wandb-metadata.json + launch args), 2026-09-21, in response
# to THE-FINN's question relayed by Kim. Two pairs share a name because they're the
# SAME logical run: 59h2y4zo/pzqv5mcw are both "dora128_300trk" (different
# rank/alpha though -- pzqv5mcw is the alpha=128 blowout that aborted after 35
# steps, so it has no epoch checkpoints to collide with 59h2y4zo's anyway) and
# z18fy24b/e3hun0v6 are the same "dora128_mix3_nodas_20260918_231801" run split
# across a resume. Neither aliased name has any clap/vote coverage regardless
# (too new / aborted too early) -- the alias closes the NAME gap, not the DATA gap.
RUN_NAME_ALIASES = {
    "2ankrkoh": "sa3-goa-dora-47s",
    "x20b3ygb": "sa3-goa-dora-47s-b4-cont",
    "mqe3ne49": "sa3-goa-dora-47s-r128-fusion",
    "i8nygj4y": "sa3-goa-dora-47s-r64",
    "dq0egegi": "sa3-goa-dora-47s-r128-adamw",
    "qy50uilf": "sa3-goa-dora-47s-r128-fusion-caut",
    "59h2y4zo": "dora128_300trk",
    "pzqv5mcw": "dora128_300trk",
    "z18fy24b": "dora128_mix3_nodas_20260918_231801",
    "e3hun0v6": "dora128_mix3_nodas_20260918_231801",
}


def ckpt_key(epoch: str, adapter_type: str, filename: str) -> str | None:
    """Best-effort ep-number key, matching clap_dora_aggregate's `ckpt` column.

    Returns None (never a guess) when the row can't be identified as a specific
    epoch -- e.g. a merged/exported adapter file with no epoch on it. Those rows
    still count in trajectory data, just not in this join.
    """
    if epoch not in (None, ""):
        try:
            return f"ep{int(float(epoch))}"
        except ValueError:
            return None
    if "adapter" in filename.lower() and adapter_type not in (None, "", "unknown"):
        return "adapter"
    return None


def load_trajectory() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    seen_run_names: set[str] = set()
    with open(TRAJECTORY_CSV) as fh:
        for row in csv.DictReader(fh):
            run_name = row["run_name"]
            seen_run_names.add(run_name)
            resolved = RUN_NAME_ALIASES.get(run_name, run_name)
            ck = ckpt_key(row.get("epoch", ""), row.get("adapter_type", ""),
                         row.get("filename", ""))
            if ck is None:
                continue
            out[(resolved, ck)] = {f: row.get(f, "") for f in TRAJECTORY_FIELDS}
    return out, seen_run_names


def load_descriptors() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    seen_models: set[str] = set()
    with open(DESCRIPTORS_CSV) as fh:
        for row in csv.DictReader(fh):
            seen_models.add(row["model"])
            out[(row["model"], row["ckpt"])] = {f: row.get(f, "") for f in DESCRIPTOR_FIELDS}
    return out, seen_models


def load_votes() -> tuple[dict[tuple[str, str], dict], set[str]]:
    """Pairwise win-rate per (model, ckpt) per question_id axis, pooled across every
    ratings_export file. `choice` is 'A', 'B', or 'EVEN'; EVEN counts as half a win
    for both sides so it doesn't silently vanish from the denominator.
    """
    tally: dict[tuple[str, str, str], list[float]] = defaultdict(lambda: [0.0, 0])  # [wins, n]
    seen_models: set[str] = set()
    for fn in RATINGS_FILES:
        with open(fn) as fh:
            for line in fh:
                d = json.loads(line)
                qid = d.get("question_id")
                if qid not in VOTE_AXES:
                    continue
                choice = d.get("choice")
                if choice not in ("A", "B", "EVEN"):
                    continue
                for side, other in (("a", "b"), ("b", "a")):
                    model, ckpt = d.get(f"model_{side}"), d.get(f"ckpt_{side}")
                    if not model or not ckpt:
                        continue
                    seen_models.add(model)
                    key = (model, ckpt, qid)
                    win = 1.0 if choice == side.upper() else (0.5 if choice == "EVEN" else 0.0)
                    tally[key][0] += win
                    tally[key][1] += 1

    out: dict[tuple[str, str], dict] = defaultdict(dict)
    for (model, ckpt, qid), (wins, n) in tally.items():
        out[(model, ckpt)][f"win_{qid}"] = round(wins / n, 3)
        out[(model, ckpt)][f"n_{qid}"] = int(n)

    # The tiny curated "preference" set carries an explicit 1-5 rating on top of
    # win/lose -- worth keeping separately, it's a finer signal than a binary choice.
    if CURATED_VOTES.exists():
        rating_tally: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0])
        with open(CURATED_VOTES) as fh:
            for line in fh:
                d = json.loads(line)
                for side in ("a", "b"):
                    model, ckpt = d.get(f"model_{side}"), d.get(f"ckpt_{side}")
                    r = d.get(f"_rating_{side}")
                    if model and ckpt and r is not None:
                        rating_tally[(model, ckpt)][0] += float(r)
                        rating_tally[(model, ckpt)][1] += 1
        for key, (total, n) in rating_tally.items():
            out[key]["preference_rating_mean"] = round(total / n, 2)
            out[key]["preference_n"] = int(n)

    return out, seen_models


def main() -> int:
    traj, traj_run_names = load_trajectory()
    desc, desc_models = load_descriptors()
    votes, vote_models = load_votes()

    all_keys = set(traj) | set(desc) | set(votes)

    vote_axis_cols = [f"win_{a}" for a in VOTE_AXES] + [f"n_{a}" for a in VOTE_AXES]
    columns = (["model", "ckpt", "has_trajectory", "has_descriptors", "has_votes"]
              + list(TRAJECTORY_FIELDS) + list(DESCRIPTOR_FIELDS)
              + vote_axis_cols + ["preference_rating_mean", "preference_n"])

    rows = []
    for model, ck in sorted(all_keys):
        t = traj.get((model, ck), {})
        d = desc.get((model, ck), {})
        v = votes.get((model, ck), {})
        row = {"model": model, "ckpt": ck,
              "has_trajectory": bool(t), "has_descriptors": bool(d), "has_votes": bool(v)}
        row.update(t)
        row.update(d)
        row.update(v)
        rows.append(row)

    all3 = sum(1 for r in rows if r["has_trajectory"] and r["has_descriptors"] and r["has_votes"])
    traj_desc = sum(1 for r in rows if r["has_trajectory"] and r["has_descriptors"])
    print(f"trajectory identities (run_name): {len(traj_run_names)}")
    print(f"descriptor identities (model):    {len(desc_models)}")
    print(f"vote identities (model):          {len(vote_models)}")
    print(f"concordance rows (model,ckpt):     {len(rows)}")
    print(f"  trajectory+descriptors:  {traj_desc}")
    print(f"  all three sources:       {all3}")
    resolved_traj_names = {RUN_NAME_ALIASES.get(n, n) for n in traj_run_names}
    unresolved_traj = resolved_traj_names - desc_models
    print(f"({len(RUN_NAME_ALIASES)} wandb-hash run_names resolved via Antigravity lookup, "
         f"2026-09-21)")
    print(f"trajectory run_names with NO descriptor-name match at all "
         f"({len(unresolved_traj)}, wandb-hash / condition-label runs, sample):")
    for name in sorted(unresolved_traj)[:15]:
        print(f"  - {name}")

    out_csv = HERE / "concordance_table.csv"
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out_csv}  ({len(rows)} rows)")

    write_html(rows, columns, HERE / "concordance_table.html")
    print(f"wrote {HERE / 'concordance_table.html'}")
    return 0


HEAD = """<meta charset="utf-8">
<title>SA3 concordance table</title>
<style>
 :root{--bg:#fff;--fg:#111;--line:#d0d0d0;--head:#f4f4f4;--dim:#999}
 @media(prefers-color-scheme:dark){:root{--bg:#141414;--fg:#e8e8e8;--line:#333;--head:#1f1f1f;--dim:#777}}
 body{background:var(--bg);color:var(--fg);font:13px/1.45 system-ui,sans-serif;margin:0;padding:16px}
 h1{font-size:19px;margin:0 0 4px} p.sub{margin:0 0 14px;opacity:.75;max-width:100ch}
 .wrap{overflow-x:auto;max-width:100%}
 table{border-collapse:collapse;width:max-content;min-width:100%;font-size:12px}
 th,td{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top;white-space:nowrap}
 th{background:var(--head);position:sticky;top:0;cursor:pointer}
 td.num{text-align:right;font-variant-numeric:tabular-nums}
 td.empty{color:var(--dim)}
 tr:hover{background:rgba(127,127,127,.12)}
 input{padding:5px 8px;width:340px;margin-bottom:10px;font:inherit}
</style>
<h1>SA3 concordance table</h1>
<p class="sub">One row per (model, ckpt) present in trajectory analysis, acoustic
descriptors, and/or human votes -- joined on EXACT name match only, never guessed.
A row with <code>has_trajectory=False</code> means that model/ckpt was voted on or
scored but the trajectory sweep's run_name for it (if any) didn't match; a
wandb-hash run_name (see build_concordance.py docstring) has no recipe name to
join against at all and will never appear here under descriptors/votes. Vote
columns are per axis (Kim rates "well produced" and "interesting" differently) --
win_X is the win-rate on axis X, n_X is how many pairwise votes fed it.
Click a header to sort; type to filter.</p>
<input id="q" placeholder="filter (model, ckpt...)">
<div class="wrap"><table id="t"><thead><tr>
"""

TAIL = """</tbody></table></div>
<script>
const t=document.getElementById('t');
document.getElementById('q').addEventListener('input',e=>{
  const v=e.target.value.toLowerCase();
  for(const r of t.tBodies[0].rows) r.style.display=r.innerText.toLowerCase().includes(v)?'':'none';
});
t.tHead.addEventListener('click',e=>{
  const th=e.target.closest('th'); if(!th) return;
  const i=[...th.parentNode.children].indexOf(th), asc=!(th.dataset.asc==='1');
  th.dataset.asc=asc?'1':'0';
  const rows=[...t.tBodies[0].rows].sort((a,b)=>{
    const x=a.cells[i].dataset.v??a.cells[i].innerText, y=b.cells[i].dataset.v??b.cells[i].innerText;
    const nx=parseFloat(x), ny=parseFloat(y);
    const c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(x).localeCompare(String(y));
    return asc?c:-c;});
  rows.forEach(r=>t.tBodies[0].appendChild(r));
});
</script>
"""


def write_html(rows: list[dict], columns: list[str], out: Path) -> None:
    parts = [HEAD]
    parts += [f"<th>{html.escape(c)}</th>" for c in columns]
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for c in columns:
            v = row.get(c, "")
            if v in (None, ""):
                parts.append('<td class="empty">-</td>')
            elif isinstance(v, bool):
                parts.append(f'<td>{"yes" if v else "no"}</td>')
            elif isinstance(v, (int, float)):
                parts.append(f'<td class="num" data-v="{v}">{v}</td>')
            else:
                parts.append(f"<td>{html.escape(str(v))}</td>")
        parts.append("</tr>")
    parts.append(TAIL)
    out.write_text("\n".join(parts))


if __name__ == "__main__":
    raise SystemExit(main())
