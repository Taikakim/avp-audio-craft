#!/usr/bin/env python3
"""publish_docs.py — render selected internal .md docs to REDACTED, edg3-themed HTML so the
paper-verdicts pages (and others) can LINK to them instead of citing an unavailable filename
(Kim 2026-07-30: "files we host or could host should be links"; he chose to serve knowledge.md +
the referenced docs/*.md, and to SKIP WORKLOG.md).

These are INTERNAL docs → the redaction bar is high and FAIL-CLOSED: every rendered page runs a
comprehensive scrub (paths, drive labels, UUID drives, corpus names + scale, LUMI/CSC + hosting
infra, IPs, credential/key filenames, checkpoint filenames) and then a refuse-to-write gate that
raises if ANY hard-leak pattern survives. Science (methods, hyperparams, metrics) stays; plumbing
and secrets do not. THE-FINN re-verifies live after deploy.

Output: ~/.cache/evals_aac/docs/<name>.html  ->  files/docs/<name>.html  (one level under files/).
Run: python3 Misc/publish_docs.py            (renders + hard-scans; deploy handled by the caller/
                                               rsync, or pass --deploy to push).
"""
import argparse
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_site as bs  # noqa: E402

SAO = Path(__file__).resolve().parent.parent
OUT_DIR = Path.home() / ".cache/evals_aac/docs"

# Deploy target (same DreamHost files/ root as the other mirrors).
KEY = "/home/kim/.ssh/id_ed25519"
HOST = "dh_4txyt6@iad1-shared-b8-25.dreamhost.com"
DEST = "/home/dh_4txyt6/aavepyora.online/files"

# md source (repo-relative) -> served html name under files/docs/. Keep names stable: the
# paper-verdicts FILE_LINKS map points at these.
DOCS = {
    "papers/knowledge.md": "knowledge.html",
    "docs/latch.md": "latch.html",
    "docs/layer-feature-map.md": "layer-feature-map.html",
    "docs/onset-density-control-narrative.md": "onset-density-control-narrative.html",
    "docs/findings-2026-07-02-perceptual-signal-night.md": "findings-2026-07-02-perceptual-signal-night.html",
    "docs/research-brief-2026-07-03-novelty-check.md": "research-brief-2026-07-03-novelty-check.html",
    "docs/ai-research/gemini-report2-assessment-2026-07-15.md": "gemini-report2-assessment-2026-07-15.html",
    "docs/ai-research/validation-experiment-plan-2026-07-15.md": "validation-experiment-plan-2026-07-15.html",
}

# ── comprehensive redaction (extends build_site.redact for whole-doc exposure) ──────────────
_T = r"(?:/[^\s\"'<>()\[\]]*)?"
_DOC_EXTRA = [
    # hosting + cluster infra
    (re.compile(r"\b[\w.-]*\.lumi\.csc\.fi\b", re.I), "[host]"),
    (re.compile(r"\b[\w.-]*\.csc\.fi\b", re.I), "[host]"),
    (re.compile(r"\bakekim\b", re.I), "[user]"),
    (re.compile(r"\bdh_4txyt6\b", re.I), "[user]"),
    (re.compile(r"\b[\w.-]*\.dreamhost\.com\b", re.I), "[host]"),
    (re.compile(r"\biad1-shared[\w.-]*\b", re.I), "[host]"),
    (re.compile(r"\bauth\.lumidata\.eu\b", re.I), "[host]"),
    (re.compile(r"\blumi-?o\b", re.I), "[store]"),
    (re.compile(r"\ballas\b", re.I), "[store]"),
    # credentials / keys
    (re.compile(r"\bid_ed25519\b"), "[key]"),
    (re.compile(r"\.netrc\b"), "[cred]"),
    (re.compile(r"\b(?:hf|sk|ghp|xox[bap])[-_][A-Za-z0-9]{8,}\b"), "[token]"),
    # bare IPv4 (skip pure version-ish? require 4 octets)
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"), "[addr]"),
    # checkpoint filenames (broader than the epoch=..ckpt in build_site)
    (re.compile(r"\b[\w=.-]*\.ckpt\b"), "[ckpt]"),
    (re.compile(r"\b[\w=.-]*\.safetensors\b"), "[weights]"),
    # extra corpus/collection scale nouns beyond build_site's set
    (re.compile(r"\b(?:\d{4,}|\d[\d.,]*\s*(?:[kKmM]|thousand|million))\s+"
                r"(crops?|latents?|npz|renders?|checkpoints?|ckpts?|adapters?)\b", re.I), r"[N] \1"),
]
# Fail-closed gate: if ANY of these survive the scrub, refuse to write the page.
_LEAK_GATE = re.compile(
    r"/home/[a-z]|/run/media|/scratch/|/project/|\bMantu\b|\bLehto\b|goa[_.\s-]?archive|"
    r"\.lumi\.csc\.fi|\.csc\.fi|akekim|dreamhost\.com|iad1-shared|id_ed25519|\.netrc|"
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|[\w=-]+\.ckpt\b|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}",
    re.I)


def redact(text: str) -> str:
    text = bs.redact(text)                 # paths / drives / corpus / multicast (shared)
    for rx, repl in _DOC_EXTRA:
        text = rx.sub(repl, text)
    return text


# ── markdown -> html (headers, paras, ul/ol, code fences, blockquote, inline) ────────────────

def _inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def md_to_html(md: str) -> str:
    out, para, list_stack, in_code = [], [], [], False

    def flush_para():
        if para:
            out.append("<p>" + " ".join(para).strip() + "</p>")
            para.clear()

    def close_lists(to=0):
        while len(list_stack) > to:
            out.append(f"</{list_stack.pop()}>")

    for line in md.splitlines():
        if line.strip().startswith("```"):
            flush_para(); close_lists()
            if in_code:
                out.append("</code></pre>"); in_code = False
            else:
                out.append("<pre class=doc-code><code>"); in_code = True
            continue
        if in_code:
            out.append(html.escape(line)); continue
        s = line.strip()
        if not s:
            flush_para(); close_lists(); continue
        h = re.match(r"^(#{1,6})\s+(.*)$", s)
        if h:
            flush_para(); close_lists()
            lvl = len(h.group(1))
            out.append(f"<h{min(lvl,6)}>{_inline(h.group(2))}</h{min(lvl,6)}>")
            continue
        li = re.match(r"^([-*+]|\d+\.)\s+(.*)$", s)
        if li:
            flush_para()
            tag = "ol" if li.group(1)[0].isdigit() else "ul"
            if not list_stack or list_stack[-1] != tag:
                close_lists(); out.append(f"<{tag}>"); list_stack.append(tag)
            out.append(f"<li>{_inline(li.group(2))}</li>")
            continue
        if s.startswith(">"):
            flush_para(); close_lists()
            out.append(f"<blockquote>{_inline(s.lstrip('> '))}</blockquote>")
            continue
        para.append(_inline(s))
    flush_para(); close_lists()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


DOC_CSS = """
<style>
.doc{max-width:820px}
.doc h1{font-size:20px;margin:6px 0 10px}.doc h2{font-size:16px;color:#9cf;margin:20px 0 4px;
  border-top:1px solid #23232a;padding-top:12px}.doc h3{font-size:14px;color:#adc;margin:14px 0 3px}
.doc p,.doc li{color:#cbd;line-height:1.6;font-size:13.5px}.doc ul,.doc ol{margin:4px 0 4px 4px}
.doc code{background:#1a1a20;padding:0 4px;border-radius:3px;color:#adc;font-size:12.5px}
.doc pre.doc-code{background:#141418;border:1px solid #262630;border-radius:6px;padding:9px 11px;
  overflow-x:auto}.doc pre.doc-code code{background:none;padding:0;color:#bcd;line-height:1.45}
.doc blockquote{border-left:2px solid #446;margin:6px 0;padding:2px 0 2px 12px;color:#9ab}
.doc .doc-note{color:#8a9;font-size:12px;margin:2px 0 14px}
.pv-back{display:inline-block;margin:22px 0 0;color:#6cf;font-size:12.5px;text-decoration:none}
.pv-back:hover{text-decoration:underline}
</style>
"""


def render_doc(md_path: Path, title: str) -> str:
    md = md_path.read_text()
    m = re.search(r"^#\s+(.*)$", md, flags=re.M)
    heading = m.group(1) if m else title
    doc = bs.head(f"{heading} — Vibe on The Edg3", css="../edg3.css")
    doc += bs.masthead("papers", "internal doc · redacted")
    doc += DOC_CSS
    doc += '<div class="doc">\n'
    doc += ('<p class="doc-note">An internal working doc, published redacted (paths, drives, infra, '
            'and checkpoint names stripped; the science stays). Linked from the paper verdicts.</p>\n')
    doc += md_to_html(md)
    doc += '\n<a class="pv-back" href="../evals/paper_verdicts.html">&larr; paper verdicts</a>\n'
    doc += '</div>\n'
    doc += bs.colophon(["internal doc", "redacted for the public mirror"], "science open")
    page = redact(doc)
    leak = _LEAK_GATE.search(page)
    if leak:
        raise SystemExit(f"REFUSING {md_path.name}: leak survived scrub near "
                         f"{page[max(0, leak.start()-50):leak.end()+50]!r}")
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for rel, name in DOCS.items():
        src = SAO / rel
        if not src.exists():
            print(f"  SKIP (missing): {rel}"); continue
        (OUT_DIR / name).write_text(render_doc(src, name[:-5]))
        written.append(name)
        print(f"  ok  {rel} -> docs/{name}  (leak-gate clean)")
    if a.deploy and written:
        rsh = f"ssh -o BatchMode=yes -i {KEY}"
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-i", KEY, HOST, f"mkdir -p {DEST}/docs"], check=False)
        subprocess.run(["rsync", "-az", "--chmod=D755,F644", "-e", rsh,
                        f"{OUT_DIR}/", f"{HOST}:{DEST}/docs/"], check=False)
        print(f"deployed {len(written)} docs -> {DEST}/docs/")
    print(f"done: {len(written)} docs rendered")


if __name__ == "__main__":
    main()
