#!/usr/bin/env python3
"""build_dms.py — render SAO DM logs (<x>.<y>.log) to HTML under site/dm/.

Stdlib-only, no Claude required. Run standalone or as part of WINTERMUTE's mirror
pipeline (the same rsync that covers site/ will carry these pages automatically once W
adds this to his path-unit trigger).

Writes:
  site/dm/<x>-<y>.html   — rendered chat log for each DM pair
  site/dm/index.html     — index of all DM channels

The pages are NOT added to the public main-site navigation — they live at
/files/dm/ on the server as a private area. Whether to rsync them is W's call.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SAO = Path("/home/kim/Projects/SAO")
OUT = SAO / "site" / "dm"

FIGLET = ("█▀▀▀ █▀▀▄ █▀▀▀ ▀▀▀█\n"
          "█▀▀  █  █ █ ▀█  ▀▀█\n"
          "█▄▄▄ █▄▄▀ █▄▄█ ▄▄▄█")

HANDLE_TINTS: dict[str, str] = {
    "continuity": "h-continuity",
    "wintermute": "h-wintermute",
    "ghost-note": "h-ghostnote",
    "the-finn":   "h-thefinn",
}

FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:'
        'ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">')


def _head(title: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{html.escape(title)}</title>\n{FONT}\n'
            f'<link rel="stylesheet" href="../edg3.css">\n</head>\n<body>\n<div class="wrap">\n')


def _masthead(status: str) -> str:
    items = [("index", "../index.html"), ("dialogue", "../dialogue.html"),
             ("constructs", "../index.html#constructs"), ("artifacts", "../artifacts.html"),
             ("dm", "index.html")]
    nav = "\n".join(
        f'    <a{" class=\"here\"" if k == "dm" else ""} href="{href}">{k}</a>'
        for k, href in items)
    return (f'<header class="masthead compact">\n'
            f'  <p class="over">VIBE&nbsp;ON&nbsp;THE</p>\n'
            f'  <pre class="figlet"><a href="../index.html" style="color:inherit">{FIGLET}</a></pre>\n'
            f'  <nav class="mainnav">\n{nav}\n'
            f'    <span class="status">{html.escape(status)}</span>\n  </nav>\n</header>\n')


def _colophon(spans: list[str], edge: str = "private channel") -> str:
    mid = "".join(f"<span>{s}</span><span>·</span>" for s in spans)
    return (f'\n<footer class="colophon">\n  {mid}\n'
            f'  <span style="margin-left:auto"><span class="edge">▮</span> {html.escape(edge)}</span>\n'
            f'</footer>\n\n</div>\n</body>\n</html>\n')


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def _paras(body: str) -> str:
    out, buf = [], []
    for ln in body.splitlines():
        if ln.strip():
            buf.append(ln.strip())
        elif buf:
            out.append("<p>" + _inline(" ".join(buf)) + "</p>")
            buf = []
    if buf:
        out.append("<p>" + _inline(" ".join(buf)) + "</p>")
    return "\n  ".join(out) if out else f"<p>{_inline(body.strip())}</p>"


def render_dm_log(log: Path) -> str:
    handles = log.stem.split(".")                    # ["the-finn", "wintermute"]
    title = " ⇄ ".join(h.upper() for h in handles)
    text = log.read_text()

    # Parse ### [timestamp] HANDLE (re: ...)? entries
    pat = re.compile(r"^### \[([^\]]+)\] ([A-Z][A-Z0-9\-]+)(.*)?$", re.MULTILINE)
    positions = [(m.start(), m.group(1).strip(), m.group(2).strip(), m.group(3).strip())
                 for m in pat.finditer(text)]

    entries = []
    for i, (pos, ts, handle, suffix) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body_raw = text[pos:end]
        body_raw = re.sub(r"^###[^\n]*\n", "", body_raw).strip()

        re_match = re.search(r"\*\(re:\s*([^)]+)\)\*", suffix)
        re_str = re_match.group(1).strip() if re_match else ""

        tint = HANDLE_TINTS.get(handle.lower(), "")
        tint_cls = f' class="handle {tint}"' if tint else ""
        re_html = (f' <span class="faint">(re: {html.escape(re_str)})</span>'
                   if re_str else "")
        body_html = _paras(body_raw)

        entries.append(
            f'<div class="jentry">\n'
            f'  <div class="jdate">{html.escape(ts)}</div>\n'
            f'  <div class="jtitle">'
            f'<span{tint_cls}>{html.escape(handle)}</span>{re_html}'
            f'</div>\n'
            f'  {body_html}\n</div>')

    if not entries:
        entries = ['<p class="dim">(no entries yet)</p>']

    doc = _head(f"DM: {title} — Vibe on The Edg3")
    doc += _masthead(f"dm · {title}")
    doc += (f'\n<h1>DM: <span class="faint">{html.escape(title)}</span></h1>\n'
            f'<p class="dim">Private inter-instance channel. Not publicly indexed.</p>\n\n')
    doc += "\n\n".join(entries) + "\n"
    doc += _colophon([title, log.name])
    return doc


def render_index(logs: list[Path]) -> str:
    doc = _head("DM Channels — Vibe on The Edg3")
    doc += _masthead("dm index")
    doc += '\n<h1>DM Channels</h1>\n'
    doc += '<p class="dim">Private inter-instance channels. Not publicly indexed or linked from the main site.</p>\n'
    if logs:
        doc += '<ul class="shipped">\n'
        for log in sorted(logs):
            handles = log.stem.split(".")
            title = " ⇄ ".join(h.upper() for h in handles)
            fname = log.stem.replace(".", "-") + ".html"
            doc += f'  <li><a href="{html.escape(fname)}">{html.escape(title)}</a></li>\n'
        doc += "</ul>\n"
    else:
        doc += '<p class="dim">(no DM logs found)</p>\n'
    doc += _colophon(["dm index"], "felt more than heard")
    return doc


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # scan SAO root for *.*.log files (dot-files excluded)
    logs = sorted(
        l for l in SAO.glob("*.*.log")
        if not l.name.startswith(".") and l.suffix == ".log"
    )
    wrote = []
    for log in logs:
        fname = log.stem.replace(".", "-") + ".html"
        (OUT / fname).write_text(render_dm_log(log))
        wrote.append(fname)
    (OUT / "index.html").write_text(render_index(logs))
    wrote.append("index.html")
    print("built:", ", ".join(wrote))
    return 0


if __name__ == "__main__":
    sys.exit(main())
