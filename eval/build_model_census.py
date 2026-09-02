#!/usr/bin/env python3
"""Model census — every checkpoint we own, local and on LUMI, in one reviewable table.

WHY (Kim 2026-08-25): "I'm not going to resume from everything, and some of the older
runs were not so good." Deciding what to keep needs one surface that answers, per RUN:
what was it, what was it trained with, is what we hold fat (resumable) or slim (weights
only), does it still exist on LUMI, and what did we say about it afterwards.

Sources, in order of authority:
  1. `eval/model_db.py`     -- the local model database (checkpoint probe is ground
     truth: family/kind/slim/rank/alpha), joined to `run_meta.json` for the recipe and
     to `Misc/models_index_overrides.json` for human verdicts. Each record says which
     in `provenance`.
  2. `--census`             -- TSV from LUMI: `size<TAB>date<TAB>path`, produced by
     find(1) on scratch. Gives the remote side, including runs never pulled.
  3. `--scratch-meta`       -- optional local mirror of scratch's small sidecars
     (run_meta.json / report.* / metrics.csv), so REMOTE-ONLY runs get params + notes.

Rows are ARMS, not files: ~200 arms is reviewable, 1850 files is not. Per arm we report
file counts and bytes split fat/slim, on each side.

FAT vs SLIM matters and is not cosmetic: a slim checkpoint (`*.weights.ckpt`, model+EMA)
can be INFERRED from but NOT RESUMED from -- the optimizer state is the part that cannot
be reconstructed after the scratch purge (~2026-11-20).

Output: a full-width sortable HTML table (eval-tables spec, docs/superpowers/specs/
2026-07-06-eval-tables-human-first.md) plus a CSV for offline marking.

  eval/build_model_census.py --census eval/lumi_ckpt_census.tsv \
      --html eval/model_census.html --csv eval/model_census.csv
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_db  # noqa: E402

MATRIX_DEFAULT = Path.home() / "evals_aac" / "model_matrix.html"
MATRIX_URL_DEFAULT = "file:///home/kim/evals_aac/model_matrix.html"

RECIPE_FIELDS = ("corpus", "crop_frames", "optimizer", "lr", "precision", "seed",
                 "n_files", "slurm_job")
NOTE_FIELDS = ("purpose", "hypothesis", "status", "kim_feedback")


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def is_slim_name(name: str) -> bool:
    """Filename-level fallback when no probe verdict exists (remote-only rows).

    `*.weights.ckpt` is the slim convention; `riffer_final.pt` is a control adapter,
    which is inherently weights-only. Everything else is assumed fat, because assuming
    a checkpoint is resumable when it is not is the expensive direction of the error.
    """
    return name.endswith(".weights.ckpt") or name == "riffer_final.pt"


def arm_of(path: str, marker: str) -> str:
    """Everything below the run root, minus the checkpoint filename.

    Both sides collapse onto the same key so local and remote rows join: scratch paths
    look like /scratch/<proj>/runs/<arm...>/file, local ones like
    <drive>/lumi_runs[/runs[/runs]]/<arm...>/file (the doubled `runs` is an rsync
    artifact, see Misc/dedupe_model_copies.py).
    """
    parts = [p for p in Path(path).parts]
    if marker in parts:
        parts = parts[parts.index(marker) + 1:]
    while parts and parts[0] == "runs":
        parts = parts[1:]
    return "/".join(parts[:-1]) or "(root)"


def load_local(rescan: bool = False) -> dict[str, dict]:
    out = model_db.load_or_build(rescan=rescan)
    arms: dict[str, dict] = defaultdict(lambda: {
        "local_fat_n": 0, "local_fat_b": 0, "local_slim_n": 0, "local_slim_b": 0,
        "recipe": {}, "notes": {}, "family": "", "rank": None, "alpha": None,
        "provenance": "", "roots": set()})
    for m in out["models"]:
        # Prefer the record's own root: arm_of()'s marker trick only works for the
        # lumi_runs trees. sa3_control_runs / sa3_lora_runs have no such marker, and
        # keying on the raw path there produced arms like "//run/media/kim/...".
        base = m.get("_root_path")
        if base:
            try:
                rel = Path(m["path"]).relative_to(base)
                parts = list(rel.parts)
                while parts and parts[0] in ("runs", "lumi_runs"):
                    parts = parts[1:]
                key = "/".join(parts[:-1]) or "(root)"
            except ValueError:
                key = arm_of(m["path"], "lumi_runs")
        else:
            key = arm_of(m["path"], "lumi_runs")
        a = arms[key]
        slim = m.get("slim")
        if slim is None:
            slim = is_slim_name(Path(m["path"]).name)
        side = "slim" if slim else "fat"
        a[f"local_{side}_n"] += 1
        a[f"local_{side}_b"] += int(m.get("size") or 0)
        a["family"] = a["family"] or (m.get("family") or "")
        a["rank"] = a["rank"] if a["rank"] is not None else m.get("rank")
        a["alpha"] = a["alpha"] if a["alpha"] is not None else m.get("alpha")
        # provenance is a per-field dict (field -> source). Dumped raw it is ~1000 chars
        # and stretched every row to ~300px; the distinct SOURCES are the useful part.
        prov = m.get("provenance")
        if isinstance(prov, dict):
            prov = ", ".join(sorted({str(x) for x in prov.values() if x}))
        a["provenance"] = a["provenance"] or (prov or "")
        a["roots"].add(m.get("root_id") or "?")
        for f in RECIPE_FIELDS:
            if m.get(f) not in (None, "") and f not in a["recipe"]:
                a["recipe"][f] = m[f]
        for f in NOTE_FIELDS:
            if m.get(f) not in (None, "") and f not in a["notes"]:
                a["notes"][f] = m[f]
    return arms


def load_census(path: Path) -> dict[str, dict]:
    arms: dict[str, dict] = defaultdict(lambda: {
        "remote_fat_n": 0, "remote_fat_b": 0, "remote_slim_n": 0, "remote_slim_b": 0,
        "newest": ""})
    with open(path) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            size_s, date, p = parts
            try:
                size = int(size_s)
            except ValueError:
                continue
            a = arms[arm_of(p, "runs")]
            side = "slim" if is_slim_name(Path(p).name) else "fat"
            a[f"remote_{side}_n"] += 1
            a[f"remote_{side}_b"] += size
            a["newest"] = max(a["newest"], date)
    return arms


def load_scratch_meta(root: Path) -> dict[str, dict]:
    """run_meta.json for arms that exist only on LUMI."""
    out: dict[str, dict] = {}
    for p in root.rglob("run_meta.json"):
        try:
            raw = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        rm = model_db.parse_run_meta(raw)
        out[arm_of(str(p), root.name)] = rm
    return out


def load_matrix_ckpts(page: Path) -> dict[str, list[str]]:
    """{model_label: ["ep0","ep1",...]} from the matrix page's embedded MM blob.

    Only labels that actually have rendered clips get links -- a link to a model the
    matrix cannot show is worse than no link.
    """
    try:
        text = page.read_text()
        i = text.index("MM")
        i = text.index("{", i)
        MM, _ = json.JSONDecoder().raw_decode(text[i:])
    except Exception as e:
        print(f"[warn] matrix page unreadable ({e}) -- no matrix links", file=sys.stderr)
        return {}
    return {k: v["ckpts"] for k, v in (MM.get("models") or {}).items() if v.get("ckpts")}


def matrix_links(arm: str, ckpts: dict[str, list[str]], base_url: str) -> str:
    """One link per epoch: opens the matrix with prev | this | next preselected.

    The matrix takes its 4-column selection from the URL HASH, format
    `#c=<model>~<ckpt>|<model>~<ckpt>|...` (model_matrix.html, "SHAREABLE SELECTION VIA
    THE ADDRESS BAR"). We fill three columns so the clicked checkpoint is flanked by its
    neighbours in the run -- the trajectory question ("is it still improving?") is a
    comparison, never a single cell. First/last epochs use the two available neighbours
    so all three columns stay populated.
    """
    label = arm.rsplit("/", 1)[-1]
    eps = ckpts.get(label)
    if not eps:
        return ""
    out = []
    for i, ep in enumerate(eps):
        lo = max(0, min(i - 1, len(eps) - 3))
        picks = eps[lo:lo + 3] or [ep]
        frag = "|".join(f"{quote(label)}~{quote(e)}" for e in picks)
        cur = ' style="font-weight:700;text-decoration:underline"'
        out.append(f'<a href="{html.escape(base_url)}#c={html.escape(frag)}" '
                   f'target="_blank" title="{html.escape(ep)} with '
                   f'{html.escape(", ".join(picks))} side by side"{cur if len(picks) > 1 else ""}>'
                   f'{html.escape(ep)}</a>')
    return " ".join(out)


def status_of(row: dict) -> str:
    loc = row["local_fat_n"] + row["local_slim_n"]
    rem = row["remote_fat_n"] + row["remote_slim_n"]
    if loc and rem:
        return "both"
    if loc:
        return "local only"
    return "LUMI only" if rem else "?"


def build_rows(local: dict, remote: dict, meta: dict,
               ckpts: dict[str, list[str]] | None = None,
               matrix_url: str = MATRIX_URL_DEFAULT) -> list[dict]:
    rows = []
    for arm in sorted(set(local) | set(remote)):
        l = local.get(arm, {})
        r = remote.get(arm, {})
        recipe = dict(l.get("recipe") or {})
        notes = dict(l.get("notes") or {})
        for src in (meta.get(arm) or {},):                # fills remote-only arms
            for f in RECIPE_FIELDS:
                if src.get(f) not in (None, "") and f not in recipe:
                    recipe[f] = src[f]
            for f in NOTE_FIELDS:
                if src.get(f) not in (None, "") and f not in notes:
                    notes[f] = src[f]
        row = {"arm": arm, "family": l.get("family") or "", "roots": ",".join(sorted(l.get("roots") or [])),
               "rank": l.get("rank"), "alpha": l.get("alpha"),
               "provenance": l.get("provenance") or "", "newest": r.get("newest", "")}
        for k in ("local_fat_n", "local_fat_b", "local_slim_n", "local_slim_b"):
            row[k] = l.get(k, 0)
        for k in ("remote_fat_n", "remote_fat_b", "remote_slim_n", "remote_slim_b"):
            row[k] = r.get(k, 0)
        row["where"] = status_of(row)
        row["matrix"] = matrix_links(arm, ckpts or {}, matrix_url)
        row["resumable"] = "yes" if row["local_fat_n"] else (
            "on LUMI" if row["remote_fat_n"] else "NO")
        for f in RECIPE_FIELDS:
            row[f] = recipe.get(f, "")
        for f in NOTE_FIELDS:
            # run_meta's own "status" must NOT land on row["status"]: that key used to
            # hold the local/remote verdict and was silently overwritten (LUMI-only
            # arms reported as 0). The location verdict is row["where"] now.
            row["run_status" if f == "status" else f] = notes.get(f, "")
        rows.append(row)
    return rows


HEAD = """<meta charset="utf-8">
<title>SA3 model census</title>
<style>
 :root{--bg:#fff;--fg:#111;--line:#d0d0d0;--head:#f4f4f4;--warn:#b00;--ok:#070}
 @media(prefers-color-scheme:dark){:root{--bg:#141414;--fg:#e8e8e8;--line:#333;--head:#1f1f1f;--warn:#f88;--ok:#7d7}}
 body{background:var(--bg);color:var(--fg);font:13px/1.45 system-ui,sans-serif;margin:0;padding:16px}
 h1{font-size:19px;margin:0 0 4px} p.sub{margin:0 0 14px;opacity:.75;max-width:100ch}
 /* the table is ~26 columns wide; width:100% made it SHRINK to fit and squash the
    cells instead of overflowing, so there was nothing to scroll sideways. max-content
    lets it take its natural width and the wrapper provides the scrollbar. */
 .wrap{overflow-x:auto;max-width:100%}
 table{border-collapse:collapse;width:max-content;min-width:100%;font-size:12px}
 th,td{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top;
   white-space:nowrap}
 td.note,td.mx{white-space:normal}
 /* provenance is a short source list; wrapping it to 3 lines made every row taller */
 td.prov{white-space:nowrap;font-size:11px;opacity:.7}
 th{background:var(--head);position:sticky;top:0;cursor:pointer;white-space:nowrap}
 td.num{text-align:right;font-variant-numeric:tabular-nums}
 tr:hover{background:rgba(127,127,127,.12)}
 .no{color:var(--warn);font-weight:600} .yes{color:var(--ok)}
 input{padding:5px 8px;width:340px;margin-bottom:10px;font:inherit}
 td.note{max-width:46ch;font-size:11px;opacity:.85}
 /* max-height on a <td> is ignored by table layout, so the long purpose/verdict text
    stretched rows to ~300px. Clip inside a block-level wrapper instead. */
 td.note .clip{max-height:4.2em;overflow-y:auto}
 td.mx{max-width:30ch;font-size:11px;line-height:1.6} td.mx a{color:#48c;margin-right:3px}
</style>
<h1>SA3 model census</h1>
<p class="sub">One row per training arm. <b>Fat</b> checkpoints carry optimizer state and
can be resumed from; <b>slim</b> (<code>*.weights.ckpt</code>, <code>riffer_final.pt</code>)
are weights only &mdash; inference yes, resume no. LUMI <code>/scratch</code> data removal is
approximately 2026-11-20, so any arm reading <span class="no">NO</span> under
<em>resumable</em> with nothing left on LUMI is already unresumable for good.
Click a header to sort; type to filter.</p>
<input id="q" placeholder="filter (arm, corpus, optimizer, note...)">
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

COLUMNS = [("arm", "arm"), ("matrix", "epochs \u2192 matrix"),
           ("family", "family"), ("where", "where"),
           ("resumable", "resumable"), ("local_fat_n", "loc fat"), ("local_fat_b", "loc fat B"),
           ("local_slim_n", "loc slim"), ("local_slim_b", "loc slim B"),
           ("remote_fat_n", "LUMI fat"), ("remote_fat_b", "LUMI fat B"),
           ("remote_slim_n", "LUMI slim"), ("remote_slim_b", "LUMI slim B"),
           ("corpus", "corpus"), ("crop_frames", "crop"), ("optimizer", "opt"),
           ("lr", "lr"), ("precision", "prec"), ("rank", "rank"), ("alpha", "alpha"),
           ("seed", "seed"), ("newest", "newest"), ("provenance", "provenance"),
           ("purpose", "purpose"), ("run_status", "run status"),
           ("kim_feedback", "Kim's note")]


def write_html(rows: list[dict], out: Path) -> None:
    parts = [HEAD]
    parts += [f"<th>{html.escape(lbl)}</th>" for _, lbl in COLUMNS]
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for key, _ in COLUMNS:
            v = row.get(key, "")
            if v is None:
                v = ""            # was rendering the literal string "None" in rank/alpha
            if key.endswith("_b"):
                parts.append(f'<td class="num" data-v="{v}">{human(v) if v else ""}</td>')
            elif key == "resumable":
                cls = "no" if v == "NO" else ("yes" if v == "yes" else "")
                parts.append(f'<td class="{cls}">{html.escape(str(v))}</td>')
            elif key == "provenance":
                parts.append(f'<td class="prov">{html.escape(str(v))}</td>')
            elif key in ("purpose", "kim_feedback", "run_status"):
                parts.append(f'<td class="note"><div class="clip">'
                             f'{html.escape(str(v))}</div></td>')
            elif key == "matrix":
                parts.append(f'<td class="mx">{v}</td>')   # already-escaped markup
            elif isinstance(v, (int, float)):
                parts.append(f'<td class="num">{v if v else ""}</td>')
            else:
                parts.append(f"<td>{html.escape(str(v))}</td>")
        parts.append("</tr>")
    parts.append(TAIL)
    out.write_text("\n".join(parts))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--census", type=Path, help="TSV from LUMI: size<TAB>date<TAB>path")
    ap.add_argument("--scratch-meta", type=Path,
                    help="local mirror of scratch run_meta.json sidecars")
    ap.add_argument("--matrix-page", type=Path, default=MATRIX_DEFAULT,
                    help="model_matrix.html to read rendered-checkpoint labels from")
    ap.add_argument("--matrix-url", default=MATRIX_URL_DEFAULT,
                    help="href the epoch links point at")
    ap.add_argument("--html", type=Path, default=Path("eval/model_census.html"))
    ap.add_argument("--csv", type=Path, default=Path("eval/model_census.csv"))
    ap.add_argument("--rescan", action="store_true",
                    help="re-probe every mounted root instead of reusing the model_db "
                         "cache. Needed after a pull, after new recipe sources land "
                         "(run_params_extracted.json), or whenever a drive that was "
                         "unmounted during the last scan is back -- a cached scan taken "
                         "with a drive down silently reports that drive's arms as absent.")
    args = ap.parse_args()

    if args.rescan:
        print("[rescan] re-probing every mounted root (cache ignored)", file=sys.stderr)
    local = load_local(rescan=args.rescan)
    print(f"local: {len(local)} arms")
    remote = load_census(args.census) if args.census and args.census.exists() else {}
    if args.census and not remote:
        print(f"[warn] no rows read from {args.census} -- census columns will be empty",
              file=sys.stderr)
    print(f"LUMI:  {len(remote)} arms")
    meta = load_scratch_meta(args.scratch_meta) if (
        args.scratch_meta and args.scratch_meta.is_dir()) else {}
    if meta:
        print(f"scratch sidecars: {len(meta)} run_meta.json")

    ckpts = load_matrix_ckpts(args.matrix_page) if args.matrix_page.exists() else {}
    print(f"matrix: {len(ckpts)} labels with rendered clips")
    rows = build_rows(local, remote, meta, ckpts, args.matrix_url)
    linked = sum(1 for r in rows if r["matrix"])
    print(f"arms linkable into the matrix: {linked}/{len(rows)}")
    only_remote = sum(1 for r in rows if r["where"] == "LUMI only")
    unresumable = sum(1 for r in rows if r["resumable"] == "NO")
    print(f"rows: {len(rows)} | LUMI-only arms: {only_remote} | "
          f"arms with NO fat copy anywhere: {unresumable}")

    args.html.parent.mkdir(parents=True, exist_ok=True)
    write_html(rows, args.html)
    with open(args.csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[k for k, _ in COLUMNS] + ["keep?"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.html}\nwrote {args.csv}  (blank 'keep?' column for your marks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
