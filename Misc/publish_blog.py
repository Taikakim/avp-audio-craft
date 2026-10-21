#!/usr/bin/env python3
# Last edited: WINTERMUTE 2026-10-21 -- [text](https://...) links; ![caption](assets/...) figures and audio players; referenced assets uploaded with the post
"""Publish blog/*.md drafts to aavepyora /files/blog/ — a new public surface (Kim 2026-07-30,
"the blog is good to go"). Reuses build_site's masthead/head + edg3.css so it matches the site,
and the dialogue mirror's HARDENED redact() as a belt-and-suspenders leak-scan before ship.

  publish_blog.py            # render + push every blog/*.md (+ index)
  publish_blog.py --dry-run  # render to /tmp, print redaction check, push nothing
"""
import sys, re, html, glob, argparse, subprocess, tempfile
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/Misc")
sys.path.insert(0, "/home/kim/bin")
import build_site as bs                       # noqa: E402
from mirror_dialogue import redact, HOST, KEY, DEST_DIR   # noqa: E402

SAO = Path("/home/kim/Projects/SAO")
BLOG_DIR = SAO / "blog"


def _inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    # [text](https://...) links; http(s) only, so a relative or local path in a draft stays visible text
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    return t


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


def render_post(p: Path):
    md = p.read_text()
    title = _title(md, p.stem)
    doc = bs.head(f"{title} — Vibe on The Edg3", css="../edg3.css")
    doc += bs.masthead("blog", "week in review")     # /files/blog/ is one level down -> keep ../ nav
    doc += f'<article class="blog-post">\n{md_to_html(md)}\n</article>\n</div></body></html>'
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="specific blog .md files (default: all — use to "
                    "publish only approved drafts, not every draft in the folder)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    drafts = ([Path(f) for f in a.files] if a.files
              else sorted(BLOG_DIR.glob("*.md"), reverse=True))
    if not a.dry_run:                                 # ensure the /files/blog/ dir exists
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-i", KEY, HOST,
                        f"mkdir -p {DEST_DIR}/blog"], check=False)
    posts, pending = [], {}
    for p in drafts:
        doc, title = render_post(p)
        slug = _slug(p)
        leaks = sorted({L for L in LEAK if L in doc})
        print(f"{p.name} -> {slug}.html  ({len(doc)} B)  leaks={leaks or 'CLEAN'}")
        if leaks:
            sys.exit(f"REFUSING: {p.name} still leaks {leaks} after redact()")
        posts.append((slug, title))
        pending[f"{slug}.html"] = doc
        if a.dry_run:
            Path(f"/tmp/blog_{slug}.html").write_text(doc)
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
        print(f"[dry-run] {len(posts)} posts rendered to /tmp/blog_*.html (nothing pushed)")
    assets = sorted({x for p in drafts for x in _assets_of(p.read_text())})
    missing = [x for x in assets if not (BLOG_DIR / x).is_file()]
    if missing:
        sys.exit(f"REFUSING: referenced assets missing locally: {missing}")
    print(f"assets: {len(assets)} referenced file(s)")
    if a.dry_run:
        pass
    else:
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
