#!/usr/bin/env python3
"""Inject the page-level comment box into existing eval HTML files (idempotent).

For legacy pages whose generators are gone or that are appended-to in place
(mp.html, traj.html, ...): adds the static page-scope comment widget before
</body>. Deep scoping (clip/ckpt/model Notes panel) belongs in the page's
generator via comment_notes_block.notes_block — this patcher is the
lowest-tier "every page can at least take Kim's page-level note" guarantee
(Kim: build once, drop everywhere, 2026-07-14).

Usage: python3 Misc/inject_comment_widget.py <file.html> [more.html ...]
Page id = the file's basename without extension. Re-running is a no-op.
"""
import os
import sys

MARK = "<!-- cmts-page-box -->"
SRC = "https://aavepyora.online/files/comments.js"


def inject(path: str) -> str:
    html = open(path, encoding="utf-8").read()
    if MARK in html:
        return "already"
    page = os.path.splitext(os.path.basename(path))[0]
    block = (f'\n{MARK}<div class="cmts" data-page="{page}" '
             f'style="max-width:1000px;margin:14px 12px"></div>'
             f'<script src="{SRC}"></script>\n')
    if "</body>" in html:
        html = html.replace("</body>", block + "</body>", 1)
    else:
        html += block
    open(path, "w", encoding="utf-8").write(html)
    return "injected"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(f"{p}: {inject(p)}")
