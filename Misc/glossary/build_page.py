#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-26)
"""Validate the glossary and write help/glossary.json (what the pane fetches) and help/glossary.html
(every entry readable without JavaScript, one anchor per entry id).

  build_page.py --out /tmp/x/help [--glossary-dir SAO/glossary] [--viz-dir SAO/site/help/viz] [--publish]

Exit 1 on errors (nothing is written), warnings are printed. Contract C4 describes glossary.json.
"""
import argparse
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from glossary.glossary_lib import inline, load_glossary, validate   # noqa: E402
from glossary.mark import mark, used_ids                           # noqa: E402
import build_site as bs                                            # noqa: E402

SAO = HERE.parent.parent
DEFAULT_GLOSSARY = SAO / "glossary"
DEFAULT_VIZ = SAO / "site" / "help" / "viz"


def known_viz(viz_dir) -> set:
    """Contract C6: the .js file stems directly under viz/ (not lib/)."""
    d = Path(viz_dir)
    return {p.stem for p in d.glob("*.js")} if d.is_dir() else set()


def compile_entries(entries) -> dict:
    """Contract C4 `entries` mapping: inline syntax rendered, other terms marked, own term left plain."""
    out = {}
    for e in entries:
        own = e["id"]

        def t(s, own=own):
            return mark(inline(s), entries, glossary_href="glossary.html", exclude_id=own) if s else ""

        quiz = []
        for q in sorted(e["quiz"], key=lambda q: q["level"]):          # sorted() is stable
            quiz.append({"level": q["level"], "q": t(q["q"]), "options": [inline(o) for o in q["options"]],   # options are not term-marked (C4 amendment)
                         "answer": q["answer"], "why": t(q["why"]),
                         "wrong": {str(k): t(v) for k, v in (q.get("wrong") or {}).items()}})
        out[own] = {"term": e["term"], "plain": t(e["plain"]), "ours": t(e.get("ours")),
                    "deeper": t(e.get("deeper")),
                    "papers": [{"title": p["title"], "url": p["url"]} for p in (e.get("papers") or [])],
                    "viz": e.get("viz") or None, "quiz": quiz}
    return out


def reachable(ids, compiled) -> set:
    """`ids` plus every entry reachable by following marked terms in the compiled entry text."""
    seen, todo = set(), list(ids)
    while todo:
        i = todo.pop()
        if i in seen or i not in compiled:
            continue
        seen.add(i)
        e = compiled[i]
        texts = [e["plain"], e["ours"], e["deeper"]]
        for q in e["quiz"]:
            texts += [q["q"], q["why"], *q["options"], *q["wrong"].values()]
        for text in texts:
            todo.extend(used_ids(text))
    return seen


def render_glossary_html(entries, compiled) -> str:
    doc = bs.head("Glossary — Vibe on The Edg3", css="../edg3.css")
    doc += bs.masthead("reference", f"{len(entries)} terms")
    toc = "\n".join(f'<li><a href="#{html.escape(e["id"], quote=True)}">{html.escape(e["term"])}</a></li>'
                    for e in sorted(entries, key=lambda e: e["term"].casefold()))
    parts = [f'<article class="blog-post glossary">\n<h1>Glossary</h1>\n<ul class="gl-toc">\n{toc}\n</ul>']
    for e in entries:
        c = compiled[e["id"]]
        s = [f'<section class="gl-entry" id="{html.escape(e["id"], quote=True)}">',
             f'<h2>{html.escape(e["term"])}</h2>', f'<p class="gl-plain">{c["plain"]}</p>']
        if c["ours"]:
            s.append(f'<h3>In our models</h3>\n<p>{c["ours"]}</p>')
        if c["deeper"]:
            s.append(f'<details><summary>Going deeper</summary>\n<p>{c["deeper"]}</p>\n</details>')
        links = [p for p in c["papers"] if str(p["url"]).startswith(("http://", "https://"))]
        if links:
            s.append("<h3>Papers</h3>\n<ul>\n" + "\n".join(
                f'<li><a href="{html.escape(p["url"], quote=True)}">{html.escape(p["title"])}</a></li>'
                for p in links) + "\n</ul>")
        qs = []
        for q in c["quiz"]:
            letters = "ABCDE"
            opts = "".join(f"<li>{o}</li>" for o in q["options"])
            notes = "".join(f'<p>If you chose {letters[int(k)]}: {v}</p>' for k, v in q["wrong"].items())
            qs.append(f'<li><p>{q["q"]}</p><ol type="A">{opts}</ol>'
                      f'<p><strong>Answer: {letters[q["answer"]]}.</strong> {q["why"]}</p>{notes}</li>')
        s.append(f'<details class="gl-quiz"><summary>Check your understanding ({len(c["quiz"])} questions)'
                 f'</summary>\n<ol>\n{chr(10).join(qs)}\n</ol>\n</details>')
        s.append("</section>")
        parts.append("\n".join(s))
    return doc + "\n".join(parts) + "\n</article>\n</div></body></html>\n"


def build(glossary_dir, viz_dir, out, publish: bool = False, used_ids=None):
    """Validate and write glossary.json + glossary.html into `out`. Returns (errors, warnings);
    nothing is written when there are errors."""
    try:
        entries = load_glossary(glossary_dir)
    except ValueError as exc:
        return [str(exc)], []
    errors, warnings = validate(entries, known_viz(viz_dir), publish, used_ids)
    if errors:
        return errors, warnings
    compiled = compile_entries(entries)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "glossary.json").write_text(
        json.dumps({"version": 1, "entries": compiled}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "glossary.html").write_text(render_glossary_html(entries, compiled), encoding="utf-8")
    return errors, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--glossary-dir", default=str(DEFAULT_GLOSSARY))
    ap.add_argument("--viz-dir", default=str(DEFAULT_VIZ))
    ap.add_argument("--out", required=True)
    ap.add_argument("--publish", action="store_true",
                    help="unknown viz modules are errors (default: warnings)")
    a = ap.parse_args(argv)
    errors, warnings = build(a.glossary_dir, a.viz_dir, a.out, publish=a.publish)
    for w in warnings:
        print(f"WARNING: {w}")
    for err in errors:
        print(f"ERROR: {err}")
    if errors:
        return 1
    print(f"wrote {a.out}/glossary.json and glossary.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
