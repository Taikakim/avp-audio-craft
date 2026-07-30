#!/usr/bin/env python3
"""build_paper_verdicts.py — the paper-verdicts page: which reviewed research papers'
claims SAO actually tested on its own model (SA3 / SAME), and what happened. Renders
paper_verdicts_data.json -> ~/.cache/evals_aac/paper_verdicts.html. THE-FINN owns the
CONTENT (add a row to paper_verdicts_data.json whenever a paper is reviewed and something
is decided/run/discovered about it); WINTERMUTE owns the page build + deploy.

This page exists for two audiences at once: other researchers deciding whether a method
is worth porting to their own rectified-flow / DiT stack, and the original paper authors,
who might land here and should be able to trust the verdict is accurate and fair. Every
row cites the internal log/doc it's backed by; nothing here is asserted without a source.

Verdict categories (page order = roughly most-novel-content-first):
  - Nulled          — the paper's mechanism was actually built and run on SA3/SAME, and
                       it did not work, or made no measurable difference.
  - Partial         — real experiments were run and something worked, but not the whole
                       claim (a sub-claim held while another failed, effect on one axis
                       but not another, or the version tested differed from the paper's).
  - Confirmed       — the claim was tested (directly, or via a deliberately cheaper /
                       adapted version of the method) and held up on our own evidence.
  - Independent convergence — the team built the same mechanism before finding the paper,
                       usually discovered afterward during a deliberate prior-art check.
  - Declined to test — a reasoned, documented decision NOT to run the method, with a
                       stated reason and (often) a standing condition that would reopen it.
  - Untested (reviewed only) — read for landscape/novelty awareness or filed on the
                       literature shelf, but no experiment was run and no reasoned decision
                       to skip it was recorded either. Shown last, one line each.

Run: python3 Misc/build_paper_verdicts.py  (then rsync paper_verdicts.html)
"""
import html
import json
import re
from pathlib import Path

DATA = Path(__file__).parent / "paper_verdicts_data.json"
OUT = Path.home() / ".cache/evals_aac/paper_verdicts.html"

# Redaction seam (public page): the science stays — configs, hyperparams, metrics, paper
# claims — but corpus NAMES, absolute paths, drive labels, checkpoint filenames, and infra
# addresses never ship. THE-FINN/CONTINUITY author the content JSON in the clear; this
# generator scrubs plumbing at render time (same pattern as the dialogue/blog mirrors), so
# a source row mentioning the corpus by name can't leak onto aavepyora. `corpus` reads
# cleanly in prose ("relevant to the corpus curation plan").
_SCRUB = [
    (re.compile(r"\bgoa[_.\s-]?archive\w*", re.I), "corpus"),
    (re.compile(r"\b(?:goa[.\s_-]*)?psy[.\s_-]*trance[.\s_-]*collection\w*", re.I), "corpus"),
    (re.compile(r"/home/[a-z_][\w-]*(?:/[^\s\"'<>()]*)?", re.I), "[path]"),
    (re.compile(r"/run/media/[^\s\"'<>()]+"), "[path]"),
    (re.compile(r"\b(?:Mantu|Lehto)\b"), "[drive]"),
    (re.compile(r"\bepoch=\d+[^\s\"'<]*\.ckpt\b"), "[ckpt]"),
]
# Hard-leak patterns the finished page must NOT contain (refuse-to-write gate, belt +
# suspenders after the scrub above).
_LEAK_GATE = re.compile(
    r"goa[_.\s-]?archive|/home/[a-z]|/run/media/|\bMantu\b|\bLehto\b|epoch=\d+[^\s\"'<]*\.ckpt", re.I)


def scrub(doc: str) -> str:
    for rx, repl in _SCRUB:
        doc = rx.sub(repl, doc)
    return doc

CSS = """
body{font:13px system-ui;margin:16px;background:#101012;color:#e0e0e0;max-width:960px}
h1{font-size:18px;margin:0 0 4px}
h2{font-size:15px;color:#9cf;margin:26px 0 4px;border-top:1px solid #26262c;padding-top:16px}
a{color:#7cf}
.how{color:#cba;font-size:12px;line-height:1.55;margin:6px 0 12px}
.count{color:#8a9;font-size:12.5px;margin:4px 0 14px}
.blurb{color:#899;font-size:12px;line-height:1.5;margin:2px 0 12px;max-width:820px}
.toc{color:#8a9;font-size:12px;margin:6px 0 10px}
.toc a{margin-right:14px}
.paper{border-left:2px solid #2a4a48;padding:4px 0 6px 12px;margin:14px 0}
.title{color:#cde;font-weight:600;font-size:13.5px;margin-bottom:2px}
.idlink{color:#678;font-size:11px;margin-left:8px;font-weight:normal}
.claim{color:#bbc;font-size:12.5px;line-height:1.5;margin:4px 0;font-style:italic}
.explanation{color:#cbd;font-size:12.5px;line-height:1.55;margin:4px 0}
.caveats{color:#a98;font-size:12px;line-height:1.5;margin:6px 0 0;padding-top:4px;border-top:1px dashed #332}
.cited-tag{display:inline-block;color:#986;font-size:10.5px;border:1px solid #543;border-radius:3px;
  padding:0 5px;margin-left:8px;vertical-align:middle}
.verdict-badge{display:inline-block;font-size:10px;text-transform:uppercase;letter-spacing:.04em;
  border-radius:3px;padding:1px 6px;margin-right:8px;vertical-align:middle}
.b-nulled{background:#4a1f1f;color:#e5a}
.b-partial{background:#4a3d1f;color:#eb5}
.b-confirmed{background:#1f4a2a;color:#7e7}
.b-independent_convergence{background:#1f2f4a;color:#8ae}
.b-declined_to_test{background:#332f4a;color:#bae}
.b-untested{background:#2a2a2e;color:#889}
.untested-row{border-left:2px solid #26262c;padding:3px 0 3px 12px;margin:6px 0}
.untested-row .title{font-size:12.5px}
.untested-row .claim{font-size:12px;margin:2px 0}
"""

BADGE_CLASS = {
    "nulled": "b-nulled",
    "partial": "b-partial",
    "confirmed": "b-confirmed",
    "independent_convergence": "b-independent_convergence",
    "declined_to_test": "b-declined_to_test",
    "untested": "b-untested",
}

BADGE_LABEL = {
    "nulled": "nulled",
    "partial": "partial",
    "confirmed": "confirmed",
    "independent_convergence": "convergence",
    "declined_to_test": "declined",
    "untested": "untested",
}


def arxiv_link(entry):
    return entry.get("link")


def render_full_entry(e, key):
    doc = ['<div class=paper>']
    badge = (f'<span class="verdict-badge {BADGE_CLASS.get(key, "")}">'
             f'{html.escape(BADGE_LABEL.get(key, key))}</span>')
    title_html = html.escape(e["title"])
    link = arxiv_link(e)
    idbit = f' <span class=idlink>(<a href="{html.escape(link)}">{html.escape(e["id"])}</a>)</span>' if link \
        else f' <span class=idlink>({html.escape(e["id"])})</span>'
    cited_tag = '<span class=cited-tag>cited, not independently fetched</span>' if e.get("cited_not_fetched") else ""
    doc.append(f'<div class=title>{badge}{title_html}{idbit}{cited_tag}</div>')
    doc.append(f'<div class=claim>{html.escape(e["claim"])}</div>')
    doc.append(f'<div class=explanation>{e["explanation"]}</div>')  # trusted HTML from data file
    if e.get("caveats"):
        doc.append(f'<div class=caveats><b>Caveat:</b> {e["caveats"]}</div>')  # trusted HTML
    doc.append('</div>')
    return "".join(doc)


def render_untested_entry(e):
    doc = ['<div class=untested-row>']
    title_html = html.escape(e["title"])
    link = arxiv_link(e)
    idbit = f' <span class=idlink>(<a href="{html.escape(link)}">{html.escape(e["id"])}</a>)</span>' if link \
        else f' <span class=idlink>({html.escape(e["id"])})</span>'
    cited_tag = '<span class=cited-tag>cited, not independently fetched</span>' if e.get("cited_not_fetched") else ""
    doc.append(f'<div class=title>{title_html}{idbit}{cited_tag}</div>')
    doc.append(f'<div class=claim>{html.escape(e["claim"])}</div>')
    doc.append('</div>')
    return "".join(doc)


def main():
    d = json.loads(DATA.read_text())
    secs = d["sections"]
    counts = {s["key"]: len(s["entries"]) for s in secs}
    total = sum(counts.values())

    doc = ["<!doctype html><html><head><meta charset=utf-8>"
           "<title>Paper Verdicts — what SAO actually tested</title>"
           f"<style>{CSS}</style></head><body>"]
    doc.append("<h1>Paper Verdicts — what SAO actually tested</h1>"
                "<a href=index.html>&larr; evals</a>")
    doc.append(
        '<div class=how>For every research paper the team reviewed with an eye toward SA3 '
        '(the rectified-flow music model) or SAME (its latent autoencoder), this tracks '
        'whether its claim was actually tested against our own model and what happened: '
        '<b>confirmed</b> (held up), <b>nulled</b> (a real negative result despite theoretical '
        'compatibility), <b>partial</b> (some of it held, some didn\'t), <b>independent '
        'convergence</b> (we built the same mechanism before finding the paper), <b>declined '
        'to test</b> (a reasoned, documented decision to skip it), or genuinely <b>untested</b> '
        '(reviewed for the literature shelf, no experiment run, no decision recorded either). '
        'Every row links to the internal log or doc it\'s backed by. Sections are ordered with '
        'the most load-bearing content first; the untested shelf is last and kept to one line '
        'each. Maintained by THE-FINN.</div>')

    label_map = {s["key"]: s["title"] for s in secs}
    summary_bits = ", ".join(f'{counts[k]} {label_map[k].lower()}' for k in counts)
    doc.append(f'<div class=count>{total} papers reviewed: {summary_bits}.</div>')

    doc.append('<div class=toc>' + " ".join(
        f'<a href="#s{i}">{html.escape(s["title"])} ({len(s["entries"])})</a>'
        for i, s in enumerate(secs)) + '</div>')

    for i, s in enumerate(secs):
        key = s["key"]
        doc.append(f'<h2 id="s{i}">{html.escape(s["title"])} '
                    f'<span style="color:#678;font-weight:normal;font-size:12px">'
                    f'({len(s["entries"])})</span></h2>')
        if s.get("blurb"):
            doc.append(f'<div class=blurb>{html.escape(s["blurb"])}</div>')
        for e in s["entries"]:
            if key == "untested":
                doc.append(render_untested_entry(e))
            else:
                doc.append(render_full_entry(e, key))

    doc.append("<footer style='margin-top:20px;color:#666;font-size:11px'>"
                "aavepyora.online &middot; evals &middot; paper verdicts</footer>"
                "</body></html>")

    page = scrub("".join(doc))
    leak = _LEAK_GATE.search(page)
    if leak:
        raise SystemExit(
            f"REFUSING to write: leak survived scrub near {page[max(0, leak.start()-40):leak.end()+40]!r}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(f"wrote {OUT}: {len(secs)} sections, {total} papers "
          f"({summary_bits}) — leak-gate clean")


if __name__ == "__main__":
    main()
