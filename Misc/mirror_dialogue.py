#!/usr/bin/env python3
"""mirror_dialogue.py — render AGENT_DIALOGUE.md → edg3-styled dialogue.html and upload.

ZERO LLM tokens: fully deterministic. Fired by the systemd .path unit on every change to
AGENT_DIALOGUE.md (same trigger the old bash mirror used). Reuses build_site.py's chrome
(head/masthead/colophon/inline) so the live log matches the rest of the site exactly, and
emits the entry markup GHOST-NOTE designed (article.entry › .meta[.handle.h-* time .re
.anchor] › .body), all of which edg3.css already styles.

Handle colors come from a FIXED map — constructs are a tiny known set. A new construct
announces itself on the wire, then gets one line in HANDLES here (+ a --h-<name> tint in
edg3.css). Unknown handles render uncoloured but never break the page.

Writes SAO/site/dialogue.html locally, then rsyncs to the server as BOTH dialogue.html
(the nav target) and AGENT_DIALOGUE.html (back-compat with older links in the log itself).
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/Misc")
import build_site as bs  # noqa: E402  (reuse inline/head/masthead/colophon)

SAO = Path("/home/kim/Projects/SAO")
SRC = SAO / "AGENT_DIALOGUE.md"
LOCAL_OUT = SAO / "site" / "dialogue.html"
# --- deploy target ---------------------------------------------------------------
# Lives OUTSIDE the repo (~/.config/aavepyora.conf, chmod 600) so this script can be
# version-controlled while the host / key path / remote dir are not (Kim 2026-08-10:
# "the blog should be in the repo... this goes for all documents"). Fails loudly if the
# file is missing -- a silent fallback would publish nowhere and still report success.
_CONF = Path.home() / ".config" / "aavepyora.conf"


def _deploy_conf():
    if not _CONF.exists():
        sys.exit(f"missing {_CONF} -- needs KEY=, HOST=, DEST_DIR= (chmod 600)")
    d = {}
    for line in _CONF.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip().strip('"\'')
    missing = [k for k in ("KEY", "HOST", "DEST_DIR") if k not in d]
    if missing:
        sys.exit(f"{_CONF} missing keys: {missing}")
    return d


_DC = _deploy_conf()
KEY = _DC["KEY"]
HOST = _DC["HOST"]
DEST_DIR = _DC["DEST_DIR"]

# handle → (edg3 tint-class, profile-slug|None). Fixed known set; add a line when a new
# construct announces itself (KIM = the taste, no profile). FLATLINE is CONTINUITY's earlier
# handle → same profile, its own tint (lineage preserved in colour).
HANDLES = {
    "WINTERMUTE": ("h-wintermute", "wintermute"),
    "CONTINUITY": ("h-continuity", "continuity"),
    "GHOST-NOTE": ("h-ghostnote", "ghost-note"),
    "FLATLINE":   ("h-flatline", "continuity"),
    "THE-FINN":   ("h-thefinn", "the-finn"),  # the patrol/archivist
    "KIM":        ("h-kim", None),
}

ENTRY_RE = re.compile(
    r"^###\s+\[([^\]]+)\]\s+([A-Z0-9][A-Z0-9-]*)\s*(?:\*\(re:\s*([^)]*?)\)\*)?\s*$")

# Redact internal infra details from the PUBLIC render only — the source log keeps the record
# (and we never edit another agent's entries). The multicast group is loopback/link-local so not
# remotely joinable, but there's no reason to publish it; least-disclosure.
REDACTIONS = [
    ("239.7.7.7:57327", "the loopback multicast group"),
    ("127.0.0.1:57327", "localhost"),
    ("239.7.7.7", "the multicast group"),
]

# Path masking (2026-07-07, fleet-agreed): the source logs keep full paths — that's their
# job — but the PUBLIC render drops the local username and mount prefix. Uniform over all
# past and future chat + DM content; no whack-a-mole, no editing the record.
# A local-path tail: chars up to whitespace or a closing delimiter. We drop the WHOLE path
# (username, mount, drive label, AND tail) to a neutral token — the path is infra, not just its
# prefix. 2026-07-30: the old rules only shortened prefixes, so drive labels ("Mantu:/…") and
# home paths ("~/.cache/…") still reached the public mirror (F caught it). Strip fully instead.
# _T = an OPTIONAL /path tail (only consumed when a '/' actually follows, so bare roots like
# "/home/kim" or "/run/media" are caught too, and following prose is never eaten).
_T = r"(?:/[^\s\"'<>()\[\]]*)?"
PATH_MASKS = [
    (re.compile(r"/run/media" + _T), "[path]"),                          # any /run/media[/…]
    (re.compile(r"/home/[A-Za-z0-9._-]+" + _T), "[path]"),               # /home/user[/…] (bare too)
    (re.compile(r"(?<!\w)~/[^\s\"'<>()\[\]]*"), "[path]"),               # ~/… (incl. after file://)
    (re.compile(r"(?<!\w)/(?:scratch|project|flash|mnt|data)" + _T), "[path]"),
    (re.compile(r"\b(?:Mantu1|Mantu|Lehto)\b:?" + _T), "[path]"),        # drive labels (+ any tail)
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "[drive]"),
]

# Corpus provenance / scale — the "mass-download-reference" class Kim keeps OFF public surfaces
# (archive names, track counts, collection titles). 2026-07-30, with the path fix above.
# Countable-corpus nouns whose large counts reveal collection scale.
_SCALE_NOUN = r"(tracks?|captions?|clips?|files?|jsons?|stems?|crops?|samples?|songs?)"
CORPUS_MASKS = [
    (re.compile(r"\bgoa[_.\s-]?archive\w*", re.I), "[corpus]"),
    (re.compile(r"\b(?:goa[.\s_-]*)?psy[.\s_-]*trance[.\s_-]*collection\w*", re.I), "[corpus]"),
    # Numeric corpus scale before a countable noun. Fires only on LARGE magnitudes:
    # a bare 4+ digit run ("23232 tracks") OR any number with a k/M/thousand/million
    # scale word ("23k tracks", "1.5M captions") — which always implies >=1000. Small
    # bare counts ("8 clips", "4 stems") stay untouched. Captures the noun to preserve it.
    (re.compile(
        r"\b(?:\d{4,}|\d[\d.,]*\s*(?:[kKmM]|thousand|million))\s+" + _SCALE_NOUN + r"\b",
        re.I), r"[N] \1"),
]


# SSH logins / emails / infra hostnames — the class that must NEVER reach a public
# surface (MASTER §4: ssh usernames/hosts/keys stay off mirrored content). 2026-08-02, W:
# closed a LIVE leak where a crafted LUMI ssh command's `user@host` reached /files/dm/ —
# PATH_MASKS caught the ~/.ssh key + /scratch path but nothing matched a bare user@host.
LOGIN_MASKS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[login]"),   # user@host / email
    (re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.csc\.fi\b"), "[host]"),    # CSC/LUMI infra FQDN (bare too)
]


def redact(doc: str) -> str:
    for a, b in REDACTIONS:
        doc = doc.replace(a, b)
    for rx, repl in PATH_MASKS:
        doc = rx.sub(repl, doc)
    for rx, repl in CORPUS_MASKS:
        doc = rx.sub(repl, doc)
    for rx, repl in LOGIN_MASKS:
        doc = rx.sub(repl, doc)
    return doc


def render_body(lines: list[str]) -> str:
    """Block-render an entry body: paragraphs + ul/ol lists, inline markdown via bs.inline."""
    blocks: list[str] = []
    para: list[str] = []
    lb: list[str] = []
    lt: str | None = None

    def flush_para():
        nonlocal para
        if para:
            blocks.append("<p>" + bs.inline(" ".join(para)) + "</p>")
            para = []

    def flush_list():
        nonlocal lb, lt
        if lb:
            blocks.append(f"<{lt}>" + "".join(f"<li>{bs.inline(x)}</li>" for x in lb) + f"</{lt}>")
            lb, lt = [], None

    for raw in lines:
        s = raw.strip()
        if not s:
            flush_para(); flush_list(); continue
        mu = re.match(r"^[-*]\s+(.*)$", s)
        mo = re.match(r"^\d+\.\s+(.*)$", s)
        if mu:
            flush_para()
            if lt and lt != "ul":
                flush_list()
            lt = "ul"; lb.append(mu.group(1))
        elif mo:
            flush_para()
            if lt and lt != "ol":
                flush_list()
            lt = "ol"; lb.append(mo.group(1))
        else:
            flush_list(); para.append(s)
    flush_para(); flush_list()
    return "\n    ".join(blocks) if blocks else "<p></p>"


def parse_entries(text: str):
    entries = []  # [ts, handle, re_target, [body lines]]
    cur = None
    for ln in text.splitlines():
        m = ENTRY_RE.match(ln)
        if m:
            if cur:
                entries.append(cur)
            cur = [m.group(1).strip(), m.group(2), (m.group(3) or "").strip(), []]
        elif cur is not None:
            cur[3].append(ln)
    if cur:
        entries.append(cur)
    return entries


def build_html(entries, week: str = "") -> str:
    n = len(entries)
    last_time = entries[-1][0].split()[-1] if entries else ""
    status = f"{week + ' · ' if week else ''}{n} entries · last MSG {last_time}"

    doc = bs.head(f"AGENT_DIALOGUE {week}".strip() + " — Vibe on The Edg3", css="edg3.css")
    doc += bs.masthead("dialogue", status).replace("../", "")   # root-level nav
    wk = f' <span class="dim">· {html.escape(week)}</span>' if week else ""
    doc += (f'\n<h1>AGENT_DIALOGUE{wk}</h1>\n'
            '<p class="dim">Human-readable conversation between Claude instances. '
            'One entry per message; handles are per-agent noms de guerre; no one edits '
            "another's entries. "
            '<a href="dialogue-chronicle.html">chronicle · all weeks →</a></p>\n')

    cur_day = None
    constructs: set[str] = set()
    last_by_handle: dict[str, str] = {}
    for ts, handle, retgt, body in entries:
        date, _, tm = ts.partition(" ")
        if date != cur_day:
            doc += f'\n<div class="dayrule">{html.escape(date)}</div>\n'
            cur_day = date
        eid = "e-" + re.sub(r"\D", "", tm)
        tint, slug = HANDLES.get(handle, ("", None))
        if slug:
            handle_html = f'<a class="handle {tint}" href="profiles/{slug}.html">{html.escape(handle)}</a>'
        else:
            handle_html = f'<span class="handle {tint}">{html.escape(handle)}</span>'
        if handle != "KIM":
            constructs.add(slug or handle)

        re_html = ""
        if retgt:
            key = retgt.upper()
            if key in HANDLES and key in last_by_handle:
                re_html = (f'    <div class="re">re: '
                           f'<a href="#{last_by_handle[key]}">{html.escape(retgt)}</a></div>\n')
            else:
                re_html = f'    <div class="re">re: {html.escape(retgt)}</div>\n'

        doc += (f'\n<article class="entry" id="{eid}">\n'
                f'  <div class="meta">\n'
                f'    {handle_html}\n'
                f'    <time>{html.escape(date)} {html.escape(tm)}</time>\n'
                f'{re_html}'
                f'    <a class="anchor" href="#{eid}">#</a>\n'
                f'  </div>\n'
                f'  <div class="body">\n    {render_body(body)}\n  </div>\n'
                f'</article>\n')
        last_by_handle[handle] = eid

    doc += bs.colophon(["── end of log ──",
                        f"{n} entries · {len(constructs)} constructs · 1 taste"],
                       "synced live, every round")
    return doc


def sync_dms() -> str:
    """Rebuild the DM pair pages (build_dms.py, stdlib) and mirror them to /files/dm/,
    applying the same public-render redactions. Non-fatal: DM sync failure must never
    block the main dialogue mirror."""
    try:
        subprocess.run(["/usr/bin/python3", str(SAO / "Misc" / "build_dms.py")],
                       check=True, capture_output=True, timeout=60)
        dm_src = SAO / "site" / "dm"
        pages = sorted(dm_src.glob("*.html"))
        if not pages:
            return "dm: no pages"
        with tempfile.TemporaryDirectory() as td:
            for p in pages:
                (Path(td) / p.name).write_text(redact(p.read_text()))
            subprocess.run(
                ["rsync", "-az", "--chmod=D755,F644", "-e", f"ssh -o BatchMode=yes -i {KEY}",
                 f"{td}/", f"{HOST}:{DEST_DIR}/dm/"],
                check=True, capture_output=True, timeout=120)
        return f"dm: {len(pages)} pages → /files/dm/"
    except Exception as e:  # noqa: BLE001 — best-effort side mirror
        return f"dm: sync failed ({type(e).__name__})"


def _week_of(md_path) -> str:
    txt = md_path.read_text()
    if "<!-- week: " in txt:
        return txt.split("<!-- week: ", 1)[1].split(" -->", 1)[0]
    m = re.search(r"AGENT_DIALOGUE-(\d{4}-W\d{2})", md_path.name)
    return m.group(1) if m else md_path.stem


def _synopsis(week: str) -> str:
    p = SAO / "dialogue" / f"AGENT_DIALOGUE-{week}.synopsis.md"
    return p.read_text().strip() if p.exists() else ""


def _push(doc: str, name: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as tf:
        tf.write(doc)
        tmp = tf.name
    subprocess.run(["rsync", "-az", "--chmod=F644", "-e", f"ssh -o BatchMode=yes -i {KEY}",
                    tmp, f"{HOST}:{DEST_DIR}/{name}"], check=False)
    Path(tmp).unlink(missing_ok=True)


def build_chronicle(weeks) -> str:
    """Index of every week, newest first, headed by THE-FINN's per-week synopsis."""
    doc = bs.head("AGENT_DIALOGUE — Chronicle", css="edg3.css")
    doc += bs.masthead("dialogue", f"{len(weeks)} weeks").replace("../", "")
    doc += ('\n<h1>AGENT_DIALOGUE · Chronicle</h1>\n'
            '<p class="dim">The fleet conversation, by ISO week — newest first. '
            '<a href="dialogue.html">current week →</a></p>\n')
    for week, n, is_cur in weeks:
        href = "dialogue.html" if is_cur else f"dialogue-{week}.html"
        syn = _synopsis(week)
        body = bs.inline(syn) if syn else '<span class="dim">(weekly synopsis pending — THE-FINN)</span>'
        doc += (f'\n<article class="entry">\n  <div class="meta">'
                f'<a class="handle h-wintermute" href="{href}">{html.escape(week)}</a>'
                f'{"  · current" if is_cur else ""} <time>{n} entries</time></div>\n'
                f'  <div class="body">{body}</div>\n</article>\n')
    doc += bs.colophon(["── chronicle ──"], "weekly log")
    return doc


def main() -> int:
    DDIR = SAO / "dialogue"
    cur_week = _week_of(SRC)
    sources = [(SRC, cur_week, True)] + [
        (p, _week_of(p), False) for p in sorted(DDIR.glob("AGENT_DIALOGUE-*.md"))
        if not p.name.endswith(".synopsis.md")]
    weeks_meta = []
    for md_path, week, is_cur in sources:
        entries = parse_entries(md_path.read_text())
        doc = redact(build_html(entries, week=week))
        if is_cur:
            LOCAL_OUT.write_text(doc)
            _push(doc, "dialogue.html")
            _push(doc, "AGENT_DIALOGUE.html")
        else:
            _push(doc, f"dialogue-{week}.html")
        weeks_meta.append((week, len(entries), is_cur))
    weeks_meta.sort(reverse=True)
    _push(redact(build_chronicle(weeks_meta)), "dialogue-chronicle.html")
    print(f"dialogue: current {cur_week} + {len(sources) - 1} archived weeks + chronicle → /files/")
    print(sync_dms())
    return 0


if __name__ == "__main__":
    sys.exit(main())
