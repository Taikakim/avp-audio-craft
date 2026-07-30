#!/usr/bin/env python3
"""build_paper_verdicts.py — the PAPERS section: which reviewed research papers' claims SAO
actually tested on its own model (SA3 / SAME), what happened, and how each relates to our work.

Two surfaces (both edg3-themed, masthead nav, redacted), from ONE data file
(paper_verdicts_data.json):
  LANDING  ~/.cache/evals_aac/paper_verdicts.html         (-> files/evals/paper_verdicts.html)
    verdict-category sections of cards (tested papers: badge + one_liner + -> results link) +
    a compact "untested — reviewed only" shelf (one-liners, no detail page).
  DETAIL   ~/.cache/evals_aac/paper_verdicts/<slug>.html  (-> files/evals/paper_verdicts/<slug>.html)
    one per TESTED paper: claim / what-we-found / verdict / caveats / "In the landscape" (enrich) /
    eval clips (when staged). Analysis-only papers simply carry no clip section.

THE-FINN owns the CONTENT (paper_verdicts_data.json rows: one_liner all papers, enrich on tested,
clips curated incrementally); WINTERMUTE owns the generator + deploy. Spec:
docs/superpowers/specs/2026-07-30-papers-site-rebuild-design.md.

This page is for two audiences: researchers deciding whether a method is worth porting to their
own rectified-flow / DiT stack, and the original authors, who should be able to trust the verdict
is accurate and fair. Every row cites the internal log/doc it's backed by.

Run: python3 Misc/build_paper_verdicts.py   (then rsync the landing + the paper_verdicts/ dir)
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_site as bs  # noqa: E402  (reuse edg3 chrome: head/masthead/colophon)

DATA = Path(__file__).parent / "paper_verdicts_data.json"
OUT = Path.home() / ".cache/evals_aac/paper_verdicts.html"           # landing
DETAIL_DIR = Path.home() / ".cache/evals_aac/paper_verdicts"         # per-paper detail pages

# Sections whose papers are TESTED (get a detail page + a results link on the landing).
TESTED_KEYS = {"nulled", "partial", "confirmed", "independent_convergence", "declined_to_test"}

BADGE_LABEL = {
    "nulled": "nulled", "partial": "partial", "confirmed": "confirmed",
    "independent_convergence": "convergence", "declined_to_test": "declined", "untested": "untested",
}

# ── redaction seam (public pages) ───────────────────────────────────────────
# Science stays — configs, hyperparams, metrics, paper claims — but corpus NAMES, absolute paths,
# drive labels, checkpoint filenames, infra addresses never ship. Render-time scrub + a
# refuse-to-write gate (belt + suspenders). `corpus` reads cleanly in prose.
_SCRUB = [
    (re.compile(r"\bgoa[_.\s-]?archive\w*", re.I), "corpus"),
    (re.compile(r"\b(?:goa[.\s_-]*)?psy[.\s_-]*trance[.\s_-]*collection\w*", re.I), "corpus"),
    (re.compile(r"/home/[a-z_][\w-]*(?:/[^\s\"'<>()]*)?", re.I), "[path]"),
    (re.compile(r"/run/media/[^\s\"'<>()]+"), "[path]"),
    (re.compile(r"\b(?:Mantu1|Mantu|Lehto)\b:?(?:/[^\s\"'<>()]*)?"), "[path]"),
    (re.compile(r"\bepoch=\d+[^\s\"'<]*\.ckpt\b"), "[ckpt]"),
]
_LEAK_GATE = re.compile(
    r"goa[_.\s-]?archive|/home/[a-z]|/run/media/|\bMantu\b|\bLehto\b|epoch=\d+[^\s\"'<]*\.ckpt", re.I)


def scrub(doc: str) -> str:
    for rx, repl in _SCRUB:
        doc = rx.sub(repl, doc)
    return doc


# ── file-mention linkification ──────────────────────────────────────────────
# Referenced files that are ALREADY hosted (and redacted) on the site get turned into links so
# a visitor can click through instead of guessing whether the file is available (Kim 2026-07-30).
# ONLY hosted+redacted markup is mapped here — a clickable name means "available." Deliberately
# NOT mapped (stay plain text): (1) .py source (comes back with GitHub public pages, per Kim);
# (2) WORKLOG.md / knowledge.md / docs/*.md — referenced but not served, and they carry internal
# paths/drives so serving needs a redaction pass first (open question for Kim). URLs are ROOT-
# relative to files/; the page depth prefix is prepended at render (landing ../, detail ../../).
FILE_LINKS = {
    "AGENT_DIALOGUE.md": "dialogue.html",
    "profiles/continuity.journal.md": "profiles/continuity.journal.html",
    "continuity.journal.md": "profiles/continuity.journal.html",
    "profiles/wintermute.journal.md": "profiles/wintermute.journal.html",
    "wintermute.journal.md": "profiles/wintermute.journal.html",
    "profiles/ghost-note.journal.md": "profiles/ghost-note.journal.html",
    "ghost-note.journal.md": "profiles/ghost-note.journal.html",
    "profiles/the-finn.journal.md": "profiles/the-finn.journal.html",
    "the-finn.journal.md": "profiles/the-finn.journal.html",
    # internal docs served redacted via Misc/publish_docs.py (Kim 2026-07-30: serve knowledge.md
    # + docs/*.md, skip WORKLOG). Served names flatten to docs/<basename>.html.
    "papers/knowledge.md": "docs/knowledge.html",
    "knowledge.md": "docs/knowledge.html",
    "docs/latch.md": "docs/latch.html",
    "docs/layer-feature-map.md": "docs/layer-feature-map.html",
    "docs/onset-density-control-narrative.md": "docs/onset-density-control-narrative.html",
    "docs/findings-2026-07-02-perceptual-signal-night.md": "docs/findings-2026-07-02-perceptual-signal-night.html",
    "docs/research-brief-2026-07-03-novelty-check.md": "docs/research-brief-2026-07-03-novelty-check.html",
    "docs/ai-research/gemini-report2-assessment-2026-07-15.md": "docs/gemini-report2-assessment-2026-07-15.html",
    "docs/ai-research/validation-experiment-plan-2026-07-15.md": "docs/validation-experiment-plan-2026-07-15.html",
}
# One alternation, longest key first -> re.sub consumes each span once, left-to-right, so a
# path-qualified name ("profiles/x.journal.md") wins over its bare tail ("x.journal.md") and no
# link nests inside another.
_FILE_RE = re.compile("|".join(re.escape(f) for f in sorted(FILE_LINKS, key=len, reverse=True)))


def linkify(text: str, prefix: str) -> str:
    """Wrap hosted-file mentions in links. `prefix` reaches files/ from the page (../ or ../../)."""
    return _FILE_RE.sub(
        lambda m: f'<a class="pv-fl" href="{prefix}{FILE_LINKS[m.group(0)]}">{m.group(0)}</a>', text)


def _gate(page: str, label: str) -> str:
    leak = _LEAK_GATE.search(page)
    if leak:
        raise SystemExit(f"REFUSING to write {label}: leak survived scrub near "
                         f"{page[max(0, leak.start()-40):leak.end()+40]!r}")
    return page


# ── helpers ─────────────────────────────────────────────────────────────────

def slug_for(e: dict) -> str:
    s = e.get("slug") or e.get("id") or e["title"]
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "paper"


def one_liner_for(e: dict) -> str:
    """The crisp landing take. Falls back to the first sentence of verdict, then claim."""
    ol = e.get("one_liner")
    if ol:
        return ol
    for src in (e.get("verdict", ""), e.get("claim", "")):
        txt = re.sub(r"<[^>]+>", "", src).strip()
        if txt:
            first = re.split(r"(?<=[.!?])\s", txt)[0]
            return first
    return ""


def arxiv_link(e: dict):
    return e.get("link")


def _idbit(e: dict) -> str:
    link = arxiv_link(e)
    if link:
        return f' <span class="pv-id">(<a href="{html.escape(link)}">{html.escape(e["id"])}</a>)</span>'
    return f' <span class="pv-id">({html.escape(e["id"])})</span>'


def _badge(key: str) -> str:
    return f'<span class="pv-badge pv-{key}">{html.escape(BADGE_LABEL.get(key, key))}</span>'


def _deepen(masthead_html: str) -> str:
    """bs.masthead() emits all-`../` hrefs (correct for a page one level under files/). Detail
    pages sit TWO levels down (files/evals/paper_verdicts/), so bump every masthead href +
    the figlet link one level deeper."""
    return masthead_html.replace('href="../', 'href="../../')


# ── page-specific styles (layered on top of edg3.css) ───────────────────────
PV_CSS = """
<style>
.pv-intro{color:#9aa;font-size:13px;line-height:1.6;margin:8px 0 22px;max-width:820px}
.pv-sec{margin:26px 0 8px}
.pv-sec h2{font-size:15px;margin:0 0 3px}
.pv-sec .pv-count{color:#8a9;font-size:12px;font-weight:400}
.pv-sec .pv-blurb{color:#899;font-size:12px;line-height:1.5;margin:2px 0 12px;max-width:820px}
.pv-card{border:1px solid #2a2a30;border-left:3px solid #3a6;border-radius:6px;padding:9px 12px;
  margin:8px 0;background:rgba(255,255,255,.015);transition:border-color .12s}
.pv-card:hover{border-color:#5cf}
.pv-card .pv-title{color:#cde;font-weight:600;font-size:13.5px}
.pv-titlelink{color:#cde;text-decoration:none}
.pv-card:hover .pv-titlelink{color:#eef}
.pv-card .pv-one{color:#9ba;font-size:12.5px;line-height:1.5;margin-top:3px}
.pv-go{color:#6cf;font-size:11.5px;float:right;margin-left:10px;text-decoration:none}
.pv-go:hover{text-decoration:underline}
.pv-badge{display:inline-block;font-size:9.5px;text-transform:uppercase;letter-spacing:.04em;
  border-radius:3px;padding:1px 6px;margin-right:8px;vertical-align:middle}
.pv-nulled{background:#4a1f1f;color:#e5a}.pv-partial{background:#4a3d1f;color:#eb5}
.pv-confirmed{background:#1f4a2a;color:#7e7}.pv-independent_convergence{background:#1f2f4a;color:#8ae}
.pv-declined_to_test{background:#332f4a;color:#bae}.pv-untested{background:#2a2a2e;color:#889}
.pv-id{color:#678;font-size:11px;font-weight:400}.pv-id a{color:#789}
.pv-shelf{margin:6px 0}.pv-shelf-row{border-left:2px solid #26262c;padding:3px 0 3px 12px;margin:5px 0}
.pv-shelf-row .pv-title{color:#bcd;font-size:12.5px;font-weight:500}
.pv-shelf-row .pv-one{color:#899;font-size:12px}
/* detail page */
.pv-detail h1{font-size:19px;margin:6px 0 2px}
.pv-lead{color:#cbd;font-size:14px;line-height:1.55;margin:4px 0 18px;font-style:italic}
.pv-detail h2{font-size:14px;color:#9cf;margin:20px 0 4px;border-top:1px solid #23232a;padding-top:14px}
.pv-detail .pv-claim{color:#bbc;line-height:1.6;font-style:italic}
.pv-detail .pv-body{color:#cbd;line-height:1.6}
.pv-detail .pv-caveat{color:#a98;line-height:1.55;font-size:13px;margin-top:6px}
.pv-detail .pv-land{color:#adc;line-height:1.6}
.pv-clip{border:1px solid #2a2a30;border-radius:6px;padding:8px 10px;margin:8px 0;background:rgba(255,255,255,.02)}
.pv-clip .pv-clab{color:#cde;font-size:12.5px;font-weight:600;margin-bottom:4px}
.pv-clip .pv-ccap{color:#899;font-size:12px;margin-top:3px}
.pv-clip audio{width:100%;margin-top:2px}
.pv-back{display:inline-block;margin:22px 0 0;color:#6cf;font-size:12.5px;text-decoration:none}
.pv-back:hover{text-decoration:underline}
.pv-fl{color:#7cf;text-decoration:none;border-bottom:1px dotted #567}.pv-fl:hover{border-bottom-style:solid}
</style>
"""


# ── clips ────────────────────────────────────────────────────────────────────

def render_clips(clips: list, prefix: str) -> str:
    """Same-dir clip players. `prefix` reaches the clips dir from the detail page
    (clips staged under evals/paper_verdicts/clips/, detail pages under evals/paper_verdicts/)."""
    if not clips:
        return ""
    rows = ['<h2>Eval clips</h2>']
    for c in clips:
        f = html.escape(c.get("file", ""))
        lab = html.escape(c.get("label", "clip"))
        cap = c.get("caption")
        rows.append(f'<div class=pv-clip><div class=pv-clab>{lab}</div>'
                    f'<audio controls preload=none src="{prefix}clips/{f}"></audio>'
                    + (f'<div class=pv-ccap>{scrub(cap)}</div>' if cap else '') + '</div>')
    return "\n".join(rows)


# ── landing ──────────────────────────────────────────────────────────────────

def render_landing(d: dict) -> str:
    secs = d["sections"]
    total = sum(len(s["entries"]) for s in secs)
    doc = bs.head("Paper Verdicts — what SAO actually tested", css="../edg3.css")
    doc += bs.masthead("papers", f"{total} papers")
    doc += PV_CSS
    doc += '<h1>Paper Verdicts</h1>\n'
    doc += ('<p class="pv-intro">For every research paper the team reviewed with an eye toward '
            '<b>SA3</b> (our rectified-flow music model) or <b>SAME</b> (its latent autoencoder), '
            'this tracks whether its claim was actually tested against our own model and what '
            'happened — <b>confirmed</b>, <b>nulled</b> (a real negative result despite theoretical '
            'compatibility), <b>partial</b>, <b>convergence</b> (we built the same mechanism before '
            'finding the paper), or <b>declined</b> (a reasoned decision to skip it). Each tested '
            'paper has its own page with our results and, where audio exists, eval clips. The '
            'untested shelf at the bottom is reviewed-for-landscape, one line each. Maintained by '
            'THE-FINN.</p>\n')

    # tested sections (cards, most-load-bearing first — data order)
    for s in secs:
        key = s["key"]
        if key == "untested":
            continue
        doc += (f'<div class="pv-sec"><h2>{html.escape(s["title"])} '
                f'<span class="pv-count">({len(s["entries"])})</span></h2>')
        if s.get("blurb"):
            doc += f'<div class="pv-blurb">{html.escape(s["blurb"])}</div>'
        doc += '</div>\n'
        for e in s["entries"]:
            slug = slug_for(e)
            # card is a <div> (NOT an <a>): the title + "results" links to the detail page and
            # the arxiv idbit is its own <a> — siblings, never nested (nested <a> is invalid HTML
            # and the browser splits the card).
            doc += (f'<div class="pv-card">'
                    f'<div class="pv-title">'
                    f'<a class="pv-titlelink" href="paper_verdicts/{slug}.html">'
                    f'{_badge(key)}{html.escape(e["title"])}</a>{_idbit(e)}'
                    f'<a class="pv-go" href="paper_verdicts/{slug}.html">results &rarr;</a>'
                    f'</div>'
                    f'<div class="pv-one">{linkify(scrub(html.escape(one_liner_for(e))), "../")}</div></div>\n')

    # untested shelf (one-liners, no detail page)
    for s in secs:
        if s["key"] != "untested":
            continue
        doc += (f'<div class="pv-sec"><h2>{html.escape(s["title"])} '
                f'<span class="pv-count">({len(s["entries"])})</span></h2>')
        if s.get("blurb"):
            doc += f'<div class="pv-blurb">{html.escape(s["blurb"])}</div>'
        doc += '</div>\n<div class="pv-shelf">\n'
        for e in s["entries"]:
            doc += (f'<div class="pv-shelf-row"><div class="pv-title">'
                    f'{html.escape(e["title"])}{_idbit(e)}</div>'
                    f'<div class="pv-one">{linkify(scrub(html.escape(one_liner_for(e))), "../")}</div></div>\n')
        doc += '</div>\n'

    doc += bs.colophon(["Paper Verdicts", "science open · plumbing redacted"],
                       "trust the verdict")
    return _gate(scrub(doc), "landing")


# ── detail ───────────────────────────────────────────────────────────────────

def render_detail(e: dict, key: str) -> str:
    slug = slug_for(e)
    doc = bs.head(f'{e["title"]} — Paper Verdict', css="../../edg3.css")
    doc += _deepen(bs.masthead("papers", "paper verdict"))
    doc += PV_CSS
    doc += '<div class="pv-detail">\n'
    doc += f'<h1>{_badge(key)}{html.escape(e["title"])}{_idbit(e)}</h1>\n'
    lk = lambda s: linkify(scrub(s), "../../")  # noqa: E731 — scrub then linkify hosted-file mentions
    ol = one_liner_for(e)
    if ol:
        doc += f'<p class="pv-lead">{lk(html.escape(ol))}</p>\n'
    if e.get("claim"):
        doc += f'<h2>The claim</h2>\n<div class="pv-claim">{scrub(html.escape(e["claim"]))}</div>\n'
    if e.get("explanation"):
        doc += f'<h2>What we found</h2>\n<div class="pv-body">{lk(e["explanation"])}</div>\n'  # trusted HTML
    if e.get("verdict"):
        doc += f'<h2>Verdict</h2>\n<div class="pv-body">{lk(e["verdict"])}</div>\n'
    if e.get("caveats"):
        doc += f'<div class="pv-caveat"><b>Caveat:</b> {lk(e["caveats"])}</div>\n'
    if e.get("enrich"):
        doc += f'<h2>In the landscape</h2>\n<div class="pv-land">{lk(e["enrich"])}</div>\n'  # trusted HTML
    doc += render_clips(e.get("clips", []), prefix="")
    doc += '<a class="pv-back" href="../paper_verdicts.html">&larr; all paper verdicts</a>\n'
    doc += '</div>\n'
    doc += bs.colophon(["Paper Verdicts", f"section: {BADGE_LABEL.get(key, key)}"], "trust the verdict")
    return _gate(scrub(doc), f"detail:{slug}")


def main():
    d = json.loads(DATA.read_text())
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_landing(d))
    n_detail = 0
    for s in d["sections"]:
        if s["key"] not in TESTED_KEYS:
            continue
        for e in s["entries"]:
            (DETAIL_DIR / f"{slug_for(e)}.html").write_text(render_detail(e, s["key"]))
            n_detail += 1
    total = sum(len(s["entries"]) for s in d["sections"])
    print(f"wrote landing ({total} papers) + {n_detail} detail pages -> {OUT.parent} — leak-gate clean")


if __name__ == "__main__":
    main()
