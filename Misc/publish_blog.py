#!/usr/bin/env python3
# Last edited: WINTERMUTE 2026-10-21 -- [text](https://...) links; ![caption](assets/...) figures and audio players; referenced assets uploaded with the post
# Last edited: WINTERMUTE 2026-10-26 -- _inline moved to glossary_lib (shared with the glossary entries), behaviour unchanged
# Last edited: WINTERMUTE 2026-10-26 -- help pane: `help-pane: on` opt-in, glossary term marking, help/ bundle (dry-run root /tmp/blog_dryrun)
# Last edited: WINTERMUTE 2026-10-26 -- SAO root derived from file location (worktree-safe)
# Last edited: WINTERMUTE 2026-10-26 -- final review: own dir first on sys.path; leak-scan every shipped help/ text file; --publish compiles only reachable entries; redact refusal names the snippet
"""Publish blog/*.md drafts to aavepyora /files/blog/ — a new public surface (Kim 2026-07-30,
"the blog is good to go"). Reuses build_site's masthead/head + edg3.css so it matches the site,
and the dialogue mirror's HARDENED redact() as a belt-and-suspenders leak-scan before ship.

  publish_blog.py            # render + push every blog/*.md (+ index)
  publish_blog.py --dry-run  # render to /tmp, print redaction check, push nothing
"""
import sys, re, html, json, glob, argparse, subprocess, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # own Misc/ first (worktree-safe), never the main checkout's
sys.path.insert(0, "/home/kim/bin")
import build_site as bs                       # noqa: E402
from mirror_dialogue import redact, HOST, KEY, DEST_DIR   # noqa: E402

from glossary import mark as gmark                        # noqa: E402
from glossary import build_page as gbuild                 # noqa: E402

SAO = Path(__file__).resolve().parent.parent   # repo root from own location (worktree-safe)
BLOG_DIR = SAO / "blog"
SITE_HELP = SAO / "site" / "help"                  # help-pane.js/.css, viz/ (tracks 2 and 3)
DRYRUN_ROOT = Path("/tmp/blog_dryrun")             # contract C1 layout for local browser checks
_HELP_IGNORE = ("tests", "test", "__pycache__", "node_modules", "*.test.js", "*.test.mjs", "package*.json", "dev.html")

# contract C3: what a page with the help pane carries before </body>
PANE_TAGS = ('<link rel="stylesheet" href="../help/help-pane.css">\n'
             '<script type="module" src="../help/help-pane.js" data-glossary="../help/glossary.json" '
             'data-viz-base="../help/viz/"></script>\n')


def help_pane_on(md: str) -> bool:
    """True when the draft's leading <!-- ... --> header comment has a line `help-pane: on`."""
    m = re.match(r"\s*<!--(.*?)-->", md, flags=re.S)
    return bool(m and re.search(r"^\s*help-pane:\s*on\s*$", m.group(1), flags=re.M | re.I))


from glossary import glossary_lib as gl                   # noqa: E402  (Misc/ is on sys.path above)

_inline = gl.inline        # one inline renderer for posts and glossary entries (moved to glossary_lib 2026-10-26)


# media must live under blog/assets/ (relative, no "..") so a post can only reference files the publisher uploads
_MEDIA = re.compile(r"^!\[([^\]]*)\]\((assets/[A-Za-z0-9_./-]+)\)$")
_AUDIO_EXT = (".m4a", ".mp3", ".wav", ".ogg")


def _assets_of(md: str):
    """Relative asset paths a post references (only these are uploaded with it)."""
    return sorted({m.group(2) for m in (_MEDIA.match(l.strip()) for l in md.splitlines())
                   if m and ".." not in m.group(2)})


_UL = re.compile(r"^[-*]\s+(.*)$")
_OL = re.compile(r"^\d+\.\s+(.*)$")


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def md_to_html(md: str) -> str:
    """Headings, paragraphs, bullet/numbered lists (indented lines continue the item) and pipe
    tables. Added 2026-10-20 (THE-FINN, Kim's go) so posts can carry result tables."""
    md = re.sub(r"^\s*<!--.*?-->\s*", "", md, flags=re.S)   # drop the draft-header comment
    out, para = [], []
    lines = md.splitlines()

    def flush():
        if para:
            out.append("<p>" + " ".join(para).strip() + "</p>")
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            flush(); i += 1; continue
        h = re.match(r"^(#{1,4})\s+(.*)$", s)
        if h:
            flush()
            lvl = len(h.group(1))
            out.append(f"<h{lvl}>{_inline(h.group(2))}</h{lvl}>")
            i += 1; continue
        # a line of its own ![caption](assets/...) = figure; .m4a/.mp3/.wav = an audio player with a caption
        fm = _MEDIA.match(s)
        if fm:
            flush()
            cap, src = _inline(fm.group(1)), html.escape(fm.group(2), quote=True)
            if src.lower().endswith(_AUDIO_EXT):
                out.append(f'<figure class="audio"><audio controls preload="none" src="{src}"></audio>'
                           f"<figcaption>{cap}</figcaption></figure>")
            else:
                out.append(f'<figure><img src="{src}" alt="{html.escape(fm.group(1), quote=True)}" '
                           f'style="max-width:100%;height:auto" loading="lazy"><figcaption>{cap}</figcaption></figure>')
            i += 1; continue
        # pipe table: header row, then a |---|---| separator row
        if (s.startswith("|") and i + 1 < len(lines)
                and re.match(r"^\|?\s*:?-{3,}", lines[i + 1].strip())):
            flush()
            head = _cells(s)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i])); i += 1
            t = "<table class=\"listing\">\n<thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead>\n<tbody>\n"
            for r in rows:
                t += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>\n"
            out.append(t + "</tbody>\n</table>")
            continue
        m = _UL.match(s) or _OL.match(s)
        if m:
            flush()
            tag = "ul" if _UL.match(s) else "ol"
            rx = _UL if tag == "ul" else _OL
            items = []
            while i < len(lines):
                ls = lines[i].strip()
                mm = rx.match(ls) if not lines[i][:1].isspace() else None
                if mm:
                    items.append([mm.group(1)])
                elif ls and lines[i][:1].isspace() and items:
                    items[-1].append(ls)          # indented continuation of the item
                else:
                    break
                i += 1
            out.append(f"<{tag}>\n" + "\n".join(
                "<li>" + _inline(" ".join(it)) + "</li>" for it in items) + f"\n</{tag}>")
            continue
        para.append(_inline(s))
        i += 1
    flush()
    return "\n".join(out)


def _title(md: str, stem: str) -> str:
    m = re.search(r"^#\s+(.*)$", re.sub(r"^\s*<!--.*?-->\s*", "", md, flags=re.S), flags=re.M)
    return m.group(1) if m else stem


def _slug(p: Path) -> str:
    return re.sub(r"-DRAFT$", "", p.stem)


def render_post(p: Path, glossary=None):
    """Render one draft. A draft with `help-pane: on` needs `glossary` (the loaded entries): its article
    HTML gets every glossary term marked and the page carries the pane's CSS/JS tags (contracts C2, C3)."""
    md = p.read_text()
    title = _title(md, p.stem)
    body = md_to_html(md)
    pane = help_pane_on(md)
    if pane:
        if glossary is None:
            raise ValueError(f"{p.name}: help-pane is on but no glossary was loaded")
        body = gmark.mark(body, glossary)
    doc = bs.head(f"{title} — Vibe on The Edg3", css="../edg3.css")
    doc += bs.masthead("blog", "week in review")     # /files/blog/ is one level down -> keep ../ nav
    doc += f'<article class="blog-post">\n{body}\n</article>\n</div>' + ("\n" + PANE_TAGS if pane else "") + '</body></html>'
    return redact(doc), title


def render_index(posts):
    doc = bs.head("Blog — Vibe on The Edg3", css="../edg3.css")
    doc += bs.masthead("blog", f"{len(posts)} posts")
    # Always list chronologically (oldest -> newest) by the YYYY-MM-DD date prefix, regardless of
    # the order files were passed on the CLI — so genesis (2026-05-31) leads and each week follows
    # in time order. (Kim 2026-08-02: index had drifted out of date order.)
    items = "\n".join(
        f'<li><a href="{slug}.html">{html.escape(title)}</a> '
        f'<span class="cfg">{slug[:10]}</span></li>'
        for slug, title in sorted(posts, key=lambda p: p[0][:10]))
    doc += f'<h1>Blog</h1>\n<ul class="blog-index">\n{items}\n</ul>\n</div></body></html>'
    return redact(doc)


def _live_slugs():
    """Slugs already published on the server.

    The index is a DIRECTORY LISTING, not a changelog of this run. Building it from `posts`
    alone means publishing ONE approved draft silently rewrites the index to that one link --
    which is exactly what happened on 2026-08-09: the four earlier posts stayed on the server,
    reachable by URL, but vanished from the index and so from every reader (Kim, 2026-08-10:
    "what happened to the blog? i see only one entry"). The CLI file-filter is there so
    unapproved drafts are not published; it must not also decide what the index remembers.

    Returns None when the listing FAILED, so the caller refuses instead of shipping a
    truncated index -- an unreadable remote must not look like an empty one.
    """
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-i", KEY, HOST,
                        f"ls {DEST_DIR}/blog/"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return {Path(x).stem for x in r.stdout.split()
            if x.endswith(".html") and x != "index.html"}


def _title_for(slug: str) -> str:
    """Title of an already-published post, read back from its local source."""
    for cand in (BLOG_DIR / f"{slug}.md", BLOG_DIR / f"{slug}-DRAFT.md"):
        if cand.exists():
            return _title(cand.read_text(), slug)
    return slug


def _push_all(docs: dict):
    """Ship every rendered page in ONE rsync -- one SSH connection, not one per file.

    Two bugs met here on 2026-08-10. The push used check=False and discarded rsync's exit code,
    so a failure printed the same "published N posts" as a success. And pushing 6 files meant 6
    rapid SSH connections, which the host resets partway through -- reliably killing the LAST
    one, which is always index.html. Net effect: the posts landed, the index silently did not,
    and the blog appeared to lose four entries. One connection removes the reset; the rc check
    means that if it ever fails again it says so instead of claiming success.
    """
    with tempfile.TemporaryDirectory() as d:
        for name, doc in docs.items():
            (Path(d) / name).write_text(doc)
        # --chmod=D755 is NOT optional: -a preserves perms, and tempfile.TemporaryDirectory()
        # is 0700, so a bare -a stamps 0700 onto the remote blog/ dir and the webserver 404s
        # every post (done exactly that, 2026-08-10). F644 alone only covers the files.
        r = subprocess.run(["rsync", "-az", "--chmod=D755,F644",
                            "-e", f"ssh -o BatchMode=yes -i {KEY}",
                            f"{d}/", f"{HOST}:{DEST_DIR}/blog/"],
                           capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"PUSH FAILED ({len(docs)} files): rsync rc={r.returncode} "
                 f"{r.stderr.strip()[-300:]}")


LEAK = ["goa_archive", "Goa.PsyTrance", "Mantu", "Lehto", "/run/media", "/home/kim",
        "~/.cache", "~/evals_aac", "/scratch/project"]


def _reset_dryrun(root: Path = None) -> None:
    """Fresh dry-run root: blog/ plus edg3.css (contract C1). Only ever deletes a dir named blog_dryrun."""
    root = root or DRYRUN_ROOT
    if root.name != "blog_dryrun":
        raise ValueError(f"refusing to reset {root}: not a blog_dryrun directory")
    if root.exists():
        shutil.rmtree(root)
    (root / "blog").mkdir(parents=True)
    shutil.copy(SAO / "site" / "edg3.css", root / "edg3.css")


def build_help_dir(out: Path, glossary_dir, publish: bool, page_used_ids) -> None:
    """Assemble the help/ directory: site/help/* files, then glossary.json + glossary.html.

    page_used_ids: the entry ids the pane pages link. The quiz_reviewed rule applies to those and to
    every entry reachable from them through the pane's own links. Exits (REFUSING) on any glossary
    error and when glossary.html/json would leak a path or be altered by redact().
    """
    out = Path(out)
    if SITE_HELP.is_dir():
        shutil.copytree(SITE_HELP, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*_HELP_IGNORE))
    viz_dir = SITE_HELP / "viz"
    try:
        entries = gl.load_glossary(glossary_dir)
    except ValueError as exc:
        sys.exit(f"REFUSING: glossary unreadable: {exc}")
    errors, _ = gl.validate(entries, gbuild.known_viz(viz_dir), False)     # structure of every entry
    if errors:
        sys.exit("REFUSING: glossary errors:\n  " + "\n  ".join(errors))
    compiled = gbuild.compile_entries(entries)
    used = gbuild.reachable(page_used_ids, compiled)
    # on --publish only the entries the pages can reach are validated and written, so an unreviewed
    # quiz or an unbuilt animation elsewhere in the glossary never reaches the public files
    errors, warnings = gbuild.build(glossary_dir, viz_dir, out, publish=publish, used_ids=used,
                                    only_ids=used if publish else None)
    for w in warnings:
        print(f"WARNING (glossary): {w}")
    if errors:
        sys.exit("REFUSING: glossary errors:\n  " + "\n  ".join(errors))
    _scan_help_files(out, compiled, used)
    print(f"help/: {len(used)} glossary entries used by the pane pages, help files CLEAN")


_HELP_TEXT_EXT = {".js", ".mjs", ".css", ".html", ".json", ".md", ".txt"}


def _first_diff(a: str, b: str) -> str:
    i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return f"...{a[max(0, i - 30):i + 40]!r} -> {b[max(0, i - 30):i + 40]!r}"


def _scan_help_files(help_dir: Path, compiled=None, used=()) -> None:
    """Leak-scan EVERY text file that would ship in help/ (js, css, html, json, md, txt), not just the
    glossary: modules carry run provenance in comments. Refuses naming the file (and, for glossary.json
    / glossary.html, the entry id and first differing snippet)."""
    for f in sorted(Path(help_dir).rglob("*")):
        if not f.is_file() or f.suffix.lower() not in _HELP_TEXT_EXT:
            continue
        rel = f.relative_to(help_dir)
        text = f.read_text(encoding="utf-8", errors="replace")
        leaks = sorted({L for L in LEAK if L in text})
        if leaks:
            sys.exit(f"REFUSING: help/{rel} leaks {leaks}")
        red = redact(text)
        if red != text:
            where = ""
            if compiled:
                for eid in sorted(used):
                    blob = json.dumps(compiled[eid], ensure_ascii=False)
                    if redact(blob) != blob:
                        where = f" (entry '{eid}')"
                        break
            sys.exit(f"REFUSING: help/{rel} has text that redact() would change{where}: {_first_diff(text, red)}")


def _push_help(help_dir: Path) -> None:
    """Ship help/ (pane files, viz modules, glossary) in one rsync, before any page that links it."""
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-i", KEY, HOST, f"mkdir -p {DEST_DIR}/help"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"HELP PUSH FAILED (mkdir): rc={r.returncode} {r.stderr.strip()[-300:]}")
    r = subprocess.run(["rsync", "-az", "--chmod=D755,F644", "-e", f"ssh -o BatchMode=yes -i {KEY}",
                        f"{help_dir}/", f"{HOST}:{DEST_DIR}/help/"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"HELP PUSH FAILED: rsync rc={r.returncode} {r.stderr.strip()[-300:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="specific blog .md files (default: all — use to "
                    "publish only approved drafts, not every draft in the folder)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--glossary-dir", default=str(SAO / "glossary"))
    a = ap.parse_args()
    drafts = ([Path(f) for f in a.files] if a.files
              else sorted(BLOG_DIR.glob("*.md"), reverse=True))
    pane_drafts = [p for p in drafts if help_pane_on(p.read_text())]
    glossary = None
    if pane_drafts:
        try:
            glossary = gl.load_glossary(a.glossary_dir)
        except ValueError as exc:
            sys.exit(f"REFUSING: glossary unreadable: {exc}")
    if a.dry_run:
        _reset_dryrun()
    if not a.dry_run:                                 # ensure the /files/blog/ dir exists
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-i", KEY, HOST,
                        f"mkdir -p {DEST_DIR}/blog"], check=False)
    posts, pending, page_used = [], {}, set()
    for p in drafts:
        doc, title = render_post(p, glossary)
        slug = _slug(p)
        if p in pane_drafts:
            page_used |= gmark.used_ids(doc)
        leaks = sorted({L for L in LEAK if L in doc})
        print(f"{p.name} -> {slug}.html  ({len(doc)} B)  leaks={leaks or 'CLEAN'}")
        if leaks:
            sys.exit(f"REFUSING: {p.name} still leaks {leaks} after redact()")
        posts.append((slug, title))
        pending[f"{slug}.html"] = doc
        if a.dry_run:
            Path(f"/tmp/blog_{slug}.html").write_text(doc)
            (DRYRUN_ROOT / "blog" / f"{slug}.html").write_text(doc)
    help_dir = None
    if pane_drafts:                                   # validate + assemble help/ BEFORE anything is pushed
        help_dir = (DRYRUN_ROOT / "help") if a.dry_run else Path(tempfile.mkdtemp(prefix="blog_help_"))
        build_help_dir(help_dir, a.glossary_dir, publish=not a.dry_run, page_used_ids=page_used)
    # index = everything readable on the server, not just what this run rendered (see _live_slugs)
    live = _live_slugs()
    if live is None:
        if not a.dry_run:
            sys.exit("REFUSING: could not list published posts -- writing the index now would "
                     "drop every link this run did not rebuild")
        print("[dry-run] remote listing unavailable -- index below covers THIS RUN ONLY")
        live = set()
    known = dict(posts)
    for slug in live - known.keys():
        known[slug] = _title_for(slug)
    dropped = known.keys() - live - {s for s, _ in posts}
    print(f"index: {len(known)} posts ({len(posts)} rebuilt now, "
          f"{len(known) - len(posts)} already live){' DROPPED:' + str(sorted(dropped)) if dropped else ''}")
    idx = render_index(sorted(known.items()))
    if a.dry_run:
        Path("/tmp/blog_index.html").write_text(idx)
        (DRYRUN_ROOT / "blog" / "index.html").write_text(idx)
        print(f"[dry-run] {len(posts)} posts rendered to /tmp/blog_*.html (nothing pushed)")
    assets = sorted({x for p in drafts for x in _assets_of(p.read_text())})
    missing = [x for x in assets if not (BLOG_DIR / x).is_file()]
    if missing:
        sys.exit(f"REFUSING: referenced assets missing locally: {missing}")
    print(f"assets: {len(assets)} referenced file(s)")
    if a.dry_run:
        for x in assets:                         # so audio/figures work in the local browser check
            dest = DRYRUN_ROOT / "blog" / x
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(BLOG_DIR / x, dest)
        print(f"[dry-run] browser root: {DRYRUN_ROOT}  (serve it; pages under blog/, help/ beside it)")
    else:
        if help_dir is not None:
            _push_help(help_dir)
        if assets:                               # only the files the published posts reference, one connection
            with tempfile.NamedTemporaryFile("w", suffix=".lst") as fl:
                fl.write("\n".join(assets) + "\n"); fl.flush()
                r = subprocess.run(["rsync", "-az", "--chmod=D755,F644", f"--files-from={fl.name}",
                                    "-e", f"ssh -o BatchMode=yes -i {KEY}",
                                    f"{BLOG_DIR}/", f"{HOST}:{DEST_DIR}/blog/"], capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit(f"ASSET PUSH FAILED: rsync rc={r.returncode} {r.stderr.strip()[-300:]}")
        pending["index.html"] = idx
        _push_all(pending)                       # one connection for posts + index
        print(f"published {len(posts)} posts + index ({len(known)} links) -> {DEST_DIR}/blog/")


if __name__ == "__main__":
    main()
