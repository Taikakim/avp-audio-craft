#!/usr/bin/env python3
"""build_kaq.py — the KAQ (Kim's Asked Questions) page (Kim 2026-07-12: "a KAQ where the
answers to my questions are journaled, organised into sections"). Renders kaq_data.json ->
~/.cache/evals_aac/kaq.html. THE-FINN owns the CONTENT (extend kaq_data.json as Kim asks
recurring questions + their settled answers); WINTERMUTE owns the page build + deploy.
Run: python3 Misc/build_kaq.py  (then rsync kaq.html)
"""
import html
import json
from pathlib import Path

DATA = Path(__file__).parent / "kaq_data.json"
OUT = Path.home() / ".cache/evals_aac/kaq.html"

CSS = """
body{font:13px system-ui;margin:16px;background:#101012;color:#e0e0e0;max-width:920px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:14px;color:#9cf;margin:22px 0 6px;border-top:1px solid #26262c;padding-top:14px}
a{color:#7cf}.how{color:#cba;font-size:12px;line-height:1.55;margin:6px 0 12px}
.qa{border-left:2px solid #2a4a48;padding:2px 0 2px 12px;margin:12px 0}
.q{color:#cde;font-weight:600;font-size:13.5px;margin-bottom:3px}
.a{color:#cbd;font-size:12.5px;line-height:1.55}
.lnks{margin-top:4px;font-size:11.5px}.lnks a{margin-right:12px}
.toc{color:#8a9;font-size:12px;margin:6px 0 10px}.toc a{margin-right:14px}
"""


def main():
    d = json.loads(DATA.read_text())
    secs = d["sections"]
    doc = [f"<!doctype html><html><head><meta charset=utf-8><title>KAQ — Kim's Asked Questions</title>"
           f"<style>{CSS}</style></head><body>"]
    doc.append("<h1>KAQ — Kim's Asked Questions</h1><a href=index.html>← evals</a>")
    doc.append('<div class=how>The settled answers to recurring questions, so they don\'t get '
               're-asked (or re-derived). Organised by topic; each answer links to the depth. '
               'Maintained by THE-FINN — new questions + answers get added as they come up.</div>')
    doc.append('<div class=toc>' + " ".join(
        f'<a href="#s{i}">{html.escape(s["title"])}</a>' for i, s in enumerate(secs)) + '</div>')
    for i, s in enumerate(secs):
        doc.append(f'<h2 id="s{i}">{html.escape(s["title"])}</h2>')
        for e in s["entries"]:
            doc.append('<div class=qa>')
            doc.append(f'<div class=q>{html.escape(e["q"])}</div>')
            doc.append(f'<div class=a>{e["a"]}</div>')          # answer is trusted HTML from the data file
            if e.get("links"):
                doc.append('<div class=lnks>' + " ".join(
                    f'<a href="{html.escape(l["href"])}">{html.escape(l["text"])} &rarr;</a>'
                    for l in e["links"]) + '</div>')
            doc.append('</div>')
    doc.append("<footer style='margin-top:20px;color:#666;font-size:11px'>aavepyora.online · evals · KAQ</footer></body></html>")
    OUT.write_text("".join(doc))
    n = sum(len(s["entries"]) for s in secs)
    print(f"wrote {OUT}: {len(secs)} sections, {n} Q&A")


if __name__ == "__main__":
    main()
