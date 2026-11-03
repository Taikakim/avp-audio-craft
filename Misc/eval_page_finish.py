#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""eval_page_finish.py -- bring a staged eval page to the normal eval-page chrome (docs/eval-page-standard.md).

Removes an invented masthead (a re-drawn logo and a per-page nav), puts in the standard header line and the one nav
("VIBE ON THE EDG3 · EVALS" + "← all evals"), hides the page's own audio bar and adds the shared floating player
(Misc/float_player.py). The page's playback logic is untouched: its <audio> element keeps playing, the floating bar follows it.
Idempotent, and meant to be re-run after a builder rewrites a page.

RUN: python3 Misc/eval_page_finish.py ~/evals_aac/choice_clips_chroma.html [...]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from float_player import inject  # noqa: E402

MARK = "<!-- eval-chrome v1 -->"
# Each page's own audio bar. Hidden, not deleted: its script still reads and writes these elements.
OWN_PLAYERS = (".transport-bar", "#player-bar", ".player-fixed", ".player-bar", "#bar")
HIDE = "<style>" + ",".join(OWN_PLAYERS) + "{display:none !important}</style>"
CHROME = ('<div class="page-chrome" style="padding-top:18px">'
          '<p class="over">VIBE ON THE EDG3 · EVALS</p>'
          '<p class="nav"><a href="{up}index.html">← all evals</a></p></div>')


def finish(html: str, up: str = "") -> str:
    """up = path back to the evals index ("" for a page beside it, "../" for one in a folder)."""
    if MARK in html:
        return html
    html = re.sub(r"<header\b[^>]*>.*?</header>\s*", "", html, count=1, flags=re.S) if "██" in html or "masthead" in html else html
    html = re.sub(r'<nav class="mainnav">.*?</nav>\s*', "", html, count=1, flags=re.S)
    chrome = MARK + CHROME.format(up=up)
    if "<h1" in html:                      # inside the page's own column, so it lines up with the title
        html = html.replace("<h1", chrome + "<h1", 1)
    else:
        html = re.sub(r"(<body\b[^>]*>)", lambda m: m.group(1) + chrome, html, count=1)
    html = html.replace("</head>", HIDE + "</head>", 1)
    return inject(html)


def main(paths):
    for p in paths:
        f = Path(p).expanduser()
        before = f.read_text(errors="replace")
        after = finish(before)
        f.write_text(after)
        left = {"logo": "██" in after, "mainnav": 'class="mainnav"' in after, "chrome": MARK in after, "float": "float-player" in after}
        print(f.name, len(before), "->", len(after), left)


if __name__ == "__main__":
    main(sys.argv[1:])
