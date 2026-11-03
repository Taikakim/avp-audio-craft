#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""eval_page_retheme.py -- move a dark eval page to the canonical paper colours (docs/eval-page-standard.md), without reading it by hand.

Colour rules, by hue/saturation/lightness of each colour found in CSS or a colour-looking JS string:
  neutral dark -> paper tones; neutral mid -> rules and dim text; neutral light -> ink (the dark theme's light text becomes dark text)
  saturated dark (tinted panels) -> a pale tint of the same hue
  saturated bright (accents, text) -> darkened until readable on paper; blues and cyans become the site's one accent
Only touches <style> blocks, style="" attributes, and quoted colours in scripts. HTML entities like &#9654; and data values are left alone.
Colours computed at run time (heatmaps from hsl(...) templates) are NOT changed: check those pages by eye.
Also applies eval_page_finish (standard header, nav, floating player) and swaps in the current floating-player style.
A rebuilt page goes dark again until its builder is changed. Idempotent. Writes <page>.predark beside nothing: back up first.
RUN: python3 Misc/eval_page_retheme.py [--up ../] ~/evals_aac/page.html [...]
"""
import argparse
import colorsys
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_page_finish import finish  # noqa: E402
from float_player import SNIPPET  # noqa: E402

MARK = "<!-- eval-paper v1 -->"
BASE = (MARK + "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">"
        "<link href=\"https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap\" rel=\"stylesheet\">"
        "<style>html,body{background:#fafaf7;color:#3b4649}"
        "body,button,select,input,td,th,textarea{font-family:'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace}"
        ".over{margin:0;font-size:11px;letter-spacing:.45em;color:#9aa7a9}"
        ".nav{margin:14px 0 0;padding-bottom:10px;border-bottom:1px solid #c9d2d0;font-size:11.5px;color:#7a8a8e}"
        ".nav a{color:#0c807c;margin-right:16px}a{color:#0c807c}</style>")
HEX = r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b"
COLOR_SCRIPT = re.compile(r"""(['"`])(""" + HEX + r""")\1""")
INLINE_CSS_IN_SCRIPT = re.compile(r"((?:color|background|background-color|border(?:-[a-z]+)?|outline|fill|stroke)\s*:\s*[^;'\"`<>]*?)(" + HEX + ")")


def to_rgb(h):
    h = h[1:]
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    return int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16), (h[6:8] if len(h) == 8 else "")


def neutral(l):
    for top, out in ((.11, "#fafaf7"), (.145, "#f2f3ef"), (.17, "#e2e6e2"), (.30, "#c9d2d0"), (.42, "#b0bcbb"), (.52, "#9aa7a9"),
                     (.70, "#7a8a8e"), (.80, "#5f6f73"), (.92, "#3b4649"), (1.01, "#2b3538")):
        if l <= top:
            return out
    return "#2b3538"


def remap(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if s < .22 or l < .03:
        return neutral(l)
    deg = h * 360
    if l < .22:                                      # a dark tinted panel
        rr, gg, bb = colorsys.hls_to_rgb(h, .94, .45)
    elif 165 <= deg <= 235:                          # blues and cyans were the dark theme's accent
        return "#0c807c"
    else:                                            # meaning-carrying colour (red, green, amber, violet): readable on paper
        rr, gg, bb = colorsys.hls_to_rgb(h, min(l, .34), min(s, .8))
    return f"#{int(rr * 255):02x}{int(gg * 255):02x}{int(bb * 255):02x}"


def map_hex(m):
    r, g, b, a = to_rgb(m.group(0))
    return remap(r, g, b) + a


def map_rgba(m):
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    x = remap(r, g, b)
    rr, gg, bb = int(x[1:3], 16), int(x[3:5], 16), int(x[5:7], 16)
    return f"rgba({rr},{gg},{bb},{m.group(4)})" if m.group(4) else f"rgb({rr},{gg},{bb})"


RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")


def tint_hex(m):
    """A saturated colour used as a BACKGROUND: a pale tint of its hue, whatever its lightness, so dark text stays readable on it."""
    r, g, b, a = to_rgb(m.group(0))
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if s < .22 or l < .03:
        return neutral(l) + a
    rr, gg, bb = colorsys.hls_to_rgb(h, .92, .5)
    return f"#{int(rr * 255):02x}{int(gg * 255):02x}{int(bb * 255):02x}" + a


BG = re.compile(r"(background(?:-color)?\s*:\s*)(" + HEX + ")")


def css(text):
    text = BG.sub(lambda m: m.group(1) + "@@" + tint_hex(re.match(HEX, m.group(2))).lstrip("#"), text)
    text = RGBA.sub(map_rgba, re.sub(HEX, map_hex, text))
    return text.replace("@@", "#")


def retheme(html, up=""):
    if MARK in html:
        return html
    player_css = re.search(r"<style>#fpbar\{.*?</style>", SNIPPET, flags=re.S).group(0)
    html = re.sub(r"<style>#fpbar\{.*?</style>", "@@FP@@", html, count=1, flags=re.S)
    html = re.sub(r"(<style\b[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + css(m.group(2)) + m.group(3), html, flags=re.S)
    html = re.sub(r"""style=(["'])(.*?)\1""", lambda m: f"style={m.group(1)}{css(m.group(2))}{m.group(1)}", html, flags=re.S)

    def script(m):
        body = COLOR_SCRIPT.sub(lambda k: k.group(1) + re.sub(HEX, map_hex, k.group(2)) + k.group(1), m.group(2))
        body = INLINE_CSS_IN_SCRIPT.sub(lambda k: k.group(1) + re.sub(HEX, tint_hex if k.group(1).lstrip().startswith("background") else map_hex, k.group(2)), body)
        return m.group(1) + body + m.group(3)

    html = re.sub(r"(<script\b[^>]*>)(.*?)(</script>)", script, html, flags=re.S)
    html = html.replace("@@FP@@", player_css)
    html = html.replace("</head>", BASE + "</head>", 1) if "</head>" in html else BASE + html
    return finish(html, up=up)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--up", default="", help="path back to the evals index: '' beside it, '../' in a folder")
    ap.add_argument("pages", nargs="+")
    a = ap.parse_args()
    for p in a.pages:
        f = Path(p).expanduser()
        before = f.read_text(errors="replace")
        after = retheme(before, a.up)
        f.write_text(after)
        print(f.name, len(before), "->", len(after), "dark left:", len(re.findall(r"#0[0-9a-f]0[0-9a-f]1[0-9a-f]|#1[0-9a-f]1[0-9a-f]1[0-9a-f]", after)))


if __name__ == "__main__":
    main()
