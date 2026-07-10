#!/usr/bin/env python3
"""
build_model_index.py -- THE MODELS INDEX (Kim 2026-07-10: "a list of every model
we've trained, and links after each to any tests that used them... I suspect we
might even have some we have barely tested... from the landing page an index that
helps me stay aware of the models we already have at hand").

Inventory sources (mechanical):
  * Mantu/sa3_lora_runs/<run>/   -- DoRA/LoRA adapter runs (dirs holding .pt/.ckpt/.safetensors)
  * Mantu/sa3_control_runs/<run>/ -- control-adapter / FusionCC / attribute runs
  * stable-audio-3/latch_weights_sa3_medium/*_best.pt -- LatCH guidance heads
Cross-reference (the "which tests used it" join):
  * every eval page dir under ~/.cache/evals_aac/{renders,riffer,control_runs}:
    token overlap between the model's run label and the eval dir name, its clip
    filenames, or its index.html text. Name-matching is imperfect -> the page says
    so, and MODEL_NOTES / models_index_overrides.json lets anyone correct entries.
Recipes: eval/mp_checkpoint_recipes.json where labels match; HoF badges from
docs/checkpoint-hall-of-fame.md (## headings mentioning a run label).

Redaction: model entries show the RUN LABEL (shareable science per MASTER §4),
never file paths. Barely-tested flag: 0-1 linked eval pages.

Run: python3 Misc/build_model_index.py  (writes ~/.cache/evals_aac/models.html;
ship with the usual rsync; landing links it via build_evals' curated list).
"""
import html
import json
import os
import re
from pathlib import Path

HOME = Path.home()
STAGING = HOME / ".cache/evals_aac"
LORA = Path("/run/media/kim/Mantu/sa3_lora_runs")
CTRL = Path("/run/media/kim/Mantu/sa3_control_runs")
LATCH = Path("/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium")
HOF = Path("/home/kim/Projects/SAO/docs/checkpoint-hall-of-fame.md")
RECIPES = Path("/home/kim/Projects/SAO/eval/mp_checkpoint_recipes.json")
OVERRIDES = Path("/home/kim/Projects/SAO/Misc/models_index_overrides.json")
OUT = STAGING / "models.html"

CKPT_EXT = (".pt", ".ckpt", ".safetensors")
STOP = {"sa3", "lora", "dora", "runs", "run", "the", "and", "test", "eval", "board",
        "8ep", "5ep", "clips", "index", "html"}


def tokens(name):
    return {t for t in re.split(r"[_\-.]+", name.lower()) if len(t) > 2 and t not in STOP}


def collect_models():
    models = []
    for base, family in ((LORA, "DoRA/LoRA adapter"), (CTRL, "control adapter / head run")):
        if not base.exists():
            continue
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            ckpts = [f for f in os.listdir(d) if f.endswith(CKPT_EXT)]
            if not ckpts:
                continue
            models.append({"label": d.name, "family": family, "n_ckpts": len(ckpts),
                           "mtime": d.stat().st_mtime})
    if LATCH.exists():
        for f in sorted(LATCH.glob("*_best.pt")):
            label = f.stem.replace("_best", "")
            models.append({"label": label, "family": "LatCH guidance head",
                           "n_ckpts": 1, "mtime": f.stat().st_mtime})
    return models


def collect_eval_pages():
    """(rel_href, display, searchable-text) for every eval page in staging."""
    pages = []
    for sub in ("renders", "riffer", "control_runs"):
        root = STAGING / sub
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and (d / "index.html").exists():
                text = d.name + " " + " ".join(os.listdir(d))[:20000]
                try:
                    text += (d / "index.html").read_text(errors="ignore")[:60000]
                except Exception:
                    pass
                pages.append((f"{sub}/{d.name}/index.html", d.name, text.lower()))
            elif d.suffix == ".html" and d.name != "index.html":
                try:
                    text = d.name + (d.read_text(errors="ignore"))[:60000]
                except Exception:
                    text = d.name
                pages.append((f"{sub}/{d.name}", d.stem, text.lower()))
    return pages


def main():
    models = collect_models()
    pages = collect_eval_pages()
    hof_text = HOF.read_text().lower() if HOF.exists() else ""
    recipes = {}
    if RECIPES.exists():
        try:
            raw = json.load(open(RECIPES))
            for k, v in (raw.items() if isinstance(raw, dict) else []):
                if isinstance(v, dict):
                    recipes[k.lower()] = v
        except Exception:
            pass
    overrides = {}
    if OVERRIDES.exists():
        try:
            overrides = json.load(open(OVERRIDES))
        except Exception:
            pass

    for m in models:
        toks = tokens(m["label"])
        links = []
        for href, disp, text in pages:
            # match: the full label as substring, or >=2 distinctive token hits
            hits = sum(1 for t in toks if t in text)
            if m["label"].lower() in text or hits >= max(2, min(3, len(toks) - 1)):
                links.append((href, disp))
        ov = overrides.get(m["label"], {})
        for href in ov.get("add_links", []):
            if href not in [h for h, _ in links]:
                links.append((href, href.split("/")[-2] if "/" in href else href))
        for href in ov.get("remove_links", []):
            links = [(h, d) for h, d in links if h != href]
        m["links"] = links
        m["hof"] = m["label"].lower() in hof_text
        rk = next((k for k in recipes if k in m["label"].lower() or m["label"].lower() in k), None)
        m["recipe"] = ov.get("recipe") or (recipes[rk].get("recipe") or recipes[rk].get("params", "")
                                           if rk else "")
        m["note"] = ov.get("note", "")

    models.sort(key=lambda m: (-m["mtime"]))
    n_barely = sum(1 for m in models if len(m["links"]) <= 1)

    css = """
body{font:13px system-ui;margin:14px;background:#101012;color:#e0e0e0;max-width:1100px}
h1{font-size:17px;margin:0 0 4px}h2{font-size:14px;color:#9cf;margin:18px 0 6px}
a{color:#7cf}.tip{color:#8a8;font-size:12px;margin:4px 0 12px;line-height:1.5}
.how{color:#cba;font-size:12px;line-height:1.5;margin:6px 0;max-width:980px}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th{color:#9cf;text-align:left;padding:5px 8px;border-bottom:1px solid #2a2a30;position:sticky;top:0;background:#101012}
td{padding:5px 8px;border-bottom:1px solid #1c1c20;vertical-align:top}
tr:hover td{background:#16161a}
.fam{color:#889;font-size:11px}.n{color:#777;font-size:11px}
.hof{background:#3a2;color:#dfd;border-radius:4px;padding:1px 6px;font-size:10px;margin-left:6px}
.bare{background:#a33;color:#fdd;border-radius:4px;padding:1px 6px;font-size:10px;margin-left:6px}
.links a{margin-right:10px;white-space:nowrap}
.recipe{color:#9ab;font-size:11px}
"""
    doc = [f"<!doctype html><html><head><meta charset=utf-8><title>Models index</title>"
           f"<style>{css}</style></head><body>"]
    doc.append('<h1>Models index — every trained artifact, and what has tested it</h1>'
               '<a href=index.html>← evals</a>')
    doc.append(f'<div class=how><b>What this is:</b> the awareness page — all '
               f'{len(models)} trained models (adapter runs, control runs, LatCH heads) '
               f'newest first, each linking to the eval pages that exercised it. '
               f'<b style="color:#f99">{n_barely} are barely tested</b> (≤1 linked eval). '
               f'Links come from name-matching between run labels and eval pages, so they '
               f'can miss or over-match — corrections go in '
               f'<code>Misc/models_index_overrides.json</code> (add_links / remove_links / '
               f'recipe / note per label) and rebuild. HoF = in the checkpoint '
               f'hall-of-fame.</div>')
    doc.append('<table><tr><th>model (run label)</th><th>family</th><th>tested by</th></tr>')
    for m in models:
        badges = ('<span class=hof>HoF</span>' if m["hof"] else '') + \
                 ('<span class=bare>barely tested</span>' if len(m["links"]) <= 1 else '')
        links = " ".join(f'<a href="{html.escape(h)}">{html.escape(d)}</a>'
                         for h, d in m["links"]) or '<span style="color:#a55">none found</span>'
        recipe = f'<div class=recipe>{html.escape(str(m["recipe"])[:160])}</div>' if m["recipe"] else ''
        note = f'<div class=recipe>{html.escape(m["note"][:200])}</div>' if m["note"] else ''
        doc.append(f'<tr><td><b>{html.escape(m["label"])}</b>{badges}{recipe}{note}</td>'
                   f'<td class=fam>{html.escape(m["family"])}<div class=n>{m["n_ckpts"]} ckpt(s)</div></td>'
                   f'<td class=links>{links}</td></tr>')
    doc.append('</table>')
    doc.append("<footer style='margin-top:18px;color:#666;font-size:11px'>aavepyora.online · evals · models index</footer></body></html>")
    OUT.write_text("".join(doc))
    print(f"wrote {OUT}: {len(models)} models, {n_barely} barely tested, {len(pages)} eval pages scanned")


if __name__ == "__main__":
    main()
