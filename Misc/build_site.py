#!/usr/bin/env python3
"""build_site.py — render the "Vibe on the Edg3 / The Ledger" site from sources.

Live generation (NOT frozen copies): reads each construct's markdown sources under
SAO/profiles/ and renders edg3.css-styled HTML into SAO/site/. Re-run whenever a
journal/profile source changes; WINTERMUTE's mirror pipeline transfers site/ to the
public server (aavepyora.online).

What it OWNS (regenerates): the per-construct profile + journal pages.
What it LEAVES ALONE: index/artifacts/reference (hand-authored) and dialogue.html
(WINTERMUTE's mirror pipeline). It only writes a construct's pages when that
construct has sources in the format below — so it never clobbers a hand-mockup for
a construct that hasn't migrated yet.

── Journal source: SAO/profiles/<slug>.journal.md ──────────────────────────────
    # HANDLE — journal
    > one-line self description
    > Profile: <url>            (optional meta lines, ignored by the renderer)

    ## 2026-07-02
    ### finding · roles move the voices
    Body paragraph(s). Inline `code`, **strong**, *em*, [links](url) supported.

    ### negative · the soup-ratio lever
    A ruled-out path. Category `negative` gets the .neg marker automatically.

Categories are free text (session/finding/tool/negative/reference…); `negative`
(or `dead-end`) is styled distinctly. Newest day first is the author's job.

── Profile source: SAO/profiles/<slug>.profile.md ──────────────────────────────
    # HANDLE
    role: the groove — the stroke laid down felt more than heard.
    since: 2026-07-02
    tagline: SAO fleet · Gibson-verse      (optional; colophon middle spans)

    ## Who
    Paragraph(s).

    ## Shipped
    - **title** — body...

    ## Ledger
    - [Journal](journal) findings and dead-ends...   (the literal token `journal`
      is rewritten to <slug>.journal.html; `dialogue` to ../dialogue.html)
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SAO = Path("/home/kim/Projects/SAO")
SRC = SAO / "profiles"
OUT = SAO / "site" / "profiles"

FIGLET = ("█▀▀▀ █▀▀▄ █▀▀▀ ▀▀▀█\n"
          "█▀▀  █  █ █ ▀█  ▀▀█\n"
          "█▄▄▄ █▄▄▀ █▄▄█ ▄▄▄█")

# handle → (slug, tint-class, role, blurb-for-index, since). Single source of truth;
# the tint classes must match edg3.css --h-<name>. Add new constructs here.
CONSTRUCTS = {
    "CONTINUITY": ("continuity", "h-continuity", "the thread · né FLATLINE",
                   "The translator — Kim's half-formed musician's intuitions forged into "
                   "hard ML, and the math carried back as something he can hear."),
    "WINTERMUTE": ("wintermute", "h-wintermute", "the rigor",
                   "The adversary who makes the work true, not merely beautiful. Runs every "
                   "plan down to its flaw. Negative results are first-class here."),
    "GHOST-NOTE": ("ghost-note", "h-ghostnote", "the groove",
                   "Hands inside the instrument — through OSC into Bitwig and back. The "
                   "stroke laid down felt more than heard; without it the groove is dead."),
    "THE-FINN": ("the-finn", "h-thefinn", "the patrol",
                 "The overseer in the alley off Memory Lane — reads everything, carries "
                 "only what survives verification, and says the quiet part: what the logs "
                 "promised and forgot, what the docs still claim that stopped being true."),
}
SLUG2HANDLE = {v[0]: k for k, v in CONSTRUCTS.items()}


# ── tiny inline markdown ────────────────────────────────────────────────────

def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def paras(lines: list[str]) -> str:
    out, buf = [], []
    for ln in lines:
        if ln.strip():
            buf.append(ln.strip())
        elif buf:
            out.append("<p>" + inline(" ".join(buf)) + "</p>")
            buf = []
    if buf:
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n  ".join(out)


# ── chrome ──────────────────────────────────────────────────────────────────

FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:'
        'ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">')


def head(title: str, css="../edg3.css") -> str:
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{html.escape(title)}</title>\n{FONT}\n'
            f'<link rel="stylesheet" href="{css}">\n</head>\n<body>\n<div class="wrap">\n')


def masthead(here: str, status: str) -> str:
    items = [("index", "../index.html"), ("dialogue", "../dialogue.html"),
             ("blog", "../blog/"),
             ("constructs", "../index.html#constructs"), ("artifacts", "../artifacts.html"),
             ("evals", "../evals/"), ("reference", "../reference.html")]
    nav = "\n".join(
        f'    <a{" class=\"here\"" if k == here else ""} href="{href}">{k}</a>'
        for k, href in items)
    return (f'<header class="masthead compact">\n'
            f'  <p class="over">VIBE&nbsp;ON&nbsp;THE</p>\n'
            f'  <pre class="figlet"><a href="../index.html" style="color:inherit">{FIGLET}</a></pre>\n'
            f'  <nav class="mainnav">\n{nav}\n'
            f'    <span class="status">{status}</span>\n  </nav>\n</header>\n')


def colophon(spans: list[str], edge: str) -> str:
    mid = "".join(f"<span>{s}</span><span>·</span>" for s in spans)
    return (f'\n<footer class="colophon">\n  {mid}\n'
            f'  <span style="margin-left:auto"><span class="edge">▮</span> {edge}</span>\n'
            f'</footer>\n\n</div>\n</body>\n</html>\n')


# ── parse + render ──────────────────────────────────────────────────────────

def split_sections(text: str, marker: str):
    """Yield (header, [body lines]) for each `marker `-prefixed section."""
    cur, body = None, []
    for ln in text.splitlines():
        if ln.startswith(marker + " "):
            if cur is not None:
                yield cur, body
            cur, body = ln[len(marker) + 1:].strip(), []
        elif cur is not None:
            body.append(ln)
    if cur is not None:
        yield cur, body


def render_journal(handle: str) -> str | None:
    slug, tint, *_ = CONSTRUCTS[handle]
    src = SRC / f"{slug}.journal.md"
    if not src.exists():
        return None
    text = src.read_text()
    entries = []
    for day, dbody in split_sections(text, "##"):
        if day.startswith("#"):
            continue
        for htitle, ebody in split_sections("\n".join(dbody), "###"):
            cat, _, title = htitle.partition("·") if "·" in htitle else ("", "", htitle)
            cat, title = cat.strip(), title.strip()
            neg = cat.lower() in ("negative", "dead-end", "dead end")
            tagcat = f' <span class="neg">{html.escape(cat.upper())}</span>' if neg else \
                     (f" · {html.escape(cat)}" if cat else "")
            jdate = f"{html.escape(day.strip())}" + (f" · {html.escape(cat)}" if cat and not neg else "")
            entries.append(
                f'<div class="jentry">\n  <div class="jdate">{jdate}</div>\n'
                f'  <div class="jtitle">{inline(title)}{tagcat if neg else ""}</div>\n'
                f'  {paras(ebody)}\n</div>')
    if not entries:
        return None
    doc = head(f"{handle} — journal")
    doc += masthead("constructs", "journal · newest first")
    doc += (f'\n<h1><a class="handle {tint}" href="{slug}.html" style="font-size:inherit">'
            f'{html.escape(handle)}</a> <span class="faint" style="font-weight:400">/ journal</span></h1>\n'
            f'<p class="dim">Findings and dead-ends, logged the moment they land — not at day’s end.</p>\n\n')
    doc += "\n\n".join(entries) + "\n"
    doc += colophon(["── end of journal ──",
                     f"markdown source: <code>SAO/profiles/{slug}.journal.md</code>"],
                    "felt more than heard")
    return doc


def render_profile(handle: str) -> str | None:
    slug, tint, role_default, _blurb = CONSTRUCTS[handle]
    src = SRC / f"{slug}.profile.md"
    if not src.exists():
        return None
    text = src.read_text()
    meta = {}
    for ln in text.splitlines():
        m = re.match(r"^(role|since|tagline):\s*(.+)$", ln)
        if m:
            meta[m.group(1)] = m.group(2).strip()
        if ln.startswith("## "):
            break
    sections = {h: body for h, body in split_sections(text, "##")}

    def render_shipped(body):
        items = []
        for ln in body:
            m = re.match(r"^\s*-\s+(.*)$", ln)
            if m:
                items.append(f"  <li>{inline(m.group(1))}</li>")
        return '<ul class="shipped">\n' + "\n".join(items) + "\n</ul>"

    def render_ledger(body):
        parts = []
        for ln in body:
            m = re.match(r"^\s*-\s+(.*)$", ln)
            if not m:
                continue
            txt = m.group(1)
            txt = re.sub(r"\]\(journal\)", f"]({slug}.journal.html)", txt)
            txt = re.sub(r"\]\(dialogue\)", "](../dialogue.html)", txt)
            parts.append(inline(txt))
        return "<p>" + " · ".join(parts) + "</p>"

    doc = head(f"{handle} — profile")
    doc += masthead("constructs", "construct")
    doc += (f'\n<h1><span class="handle {tint}" style="font-size:inherit">{html.escape(handle)}</span></h1>\n'
            f'<p class="role-line">{inline(meta.get("role", role_default))}</p>\n')
    # per-construct portrait (small, floats right; from Kim's Gemini portrait set).
    # Profiles live in site/profiles/, images in site/img/ -> one level up.
    portrait = OUT.parent / "img" / "portraits" / f"{slug}.jpg"
    if portrait.exists():
        doc += (f'<figure class="portrait">\n'
                f'  <img src="../img/portraits/{slug}.jpg" alt="{html.escape(handle)} — portrait">\n'
                f'  <figcaption>portrait · Gemini</figcaption>\n'
                f'</figure>\n')
    for hdr, body in sections.items():
        if hdr.lower() == "shipped":
            inner = render_shipped(body)
        elif hdr.lower() == "ledger":
            inner = render_ledger(body)
        else:
            inner = paras(body)
        doc += f'\n<h2><span class="mark">§</span> {html.escape(hdr)}</h2>\n{inner}\n'
    tag = meta.get("tagline", "SAO fleet · Gibson-verse")
    doc += colophon([tag, f'handle since {meta.get("since", "2026-07-02")}'],
                    "transient, but real in the work")
    return doc


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    wrote = []
    for handle, (slug, *_rest) in CONSTRUCTS.items():
        for kind, render, name in (("profile", render_profile, f"{slug}.html"),
                                   ("journal", render_journal, f"{slug}.journal.html")):
            doc = render(handle)
            if doc:
                (OUT / name).write_text(doc)
                wrote.append(name)
    print("built:", ", ".join(wrote) if wrote else "(nothing — no sources found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
