#!/usr/bin/env python3
"""merge_comments.py — pull site comments into eval manifests (manifest v2).

The merge side of the comment loop (W's endpoint /files/comment.php, 2026-07-13):
Kim comments on an eval page -> this script pulls the token-gated export, groups
by `target`, and appends each comment VERBATIM + dated into the mapped run's
run_meta.json `kim_feedback` — which clears the red-❗ unaudited mark on the next
page rebuild (spec §16). Comment text is treated as opaque data end to end.

Mapping: Misc/comment_targets.json  { "<target>": "<abs path to run_meta.json>" }.
Unmapped targets are REPORTED, never guessed — add the mapping, rerun.

Attribution rule (the ❗ mark is "has KIM audited this", so only Kim's words may
clear it): comments with no name, or named Kim, merge into `kim_feedback`;
anything else (fleet handles, third parties) merges into `site_comments` instead
— kept verbatim + dated, but does NOT flip the audited bit.
Idempotent: merged comment timestamps are recorded per-manifest under
`merged_site_comments`; re-runs skip them.

Run (any venv, stdlib only):  python3 Misc/merge_comments.py [--dry-run]
Token: ~/.comment_export_token (0600, local only — never committed or posted).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENDPOINT = "https://aavepyora.online/files/comment.php"
TOKEN_FILE = Path.home() / ".comment_export_token"
TARGETS_FILE = HERE / "comment_targets.json"
IGNORED_TARGETS = {"merge_test"}  # endpoint smoke tests, never merged
KIM_NAMES = {"", "kim", "kim aake", "kim åke", "taikakim"}  # -> kim_feedback; others -> site_comments


def fetch_export() -> list[dict]:
    token = TOKEN_FILE.read_text().strip()
    url = f"{ENDPOINT}?export=1&key={urllib.parse.quote(token)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    if not data.get("ok", True) or "comments" not in data:
        raise RuntimeError(f"export failed: {json.dumps({k: v for k, v in data.items() if k != 'comments'})}")
    return data["comments"]


def format_entry(c: dict) -> str:
    when = c.get("iso") or datetime.fromtimestamp(c["ts"], tz=timezone.utc).isoformat()
    who = f", {c['name']}" if c.get("name") else ""
    return f"{when} (site comment{who}): {c['text']}"


def merge_into(meta_path: Path, comments: list[dict], dry: bool) -> int:
    meta = json.loads(meta_path.read_text())
    seen = set(meta.get("merged_site_comments", []))
    fresh = [c for c in comments if c["ts"] not in seen]
    if not fresh:
        return 0
    for field, batch in (
        ("kim_feedback", [c for c in fresh if c.get("name", "").strip().lower() in KIM_NAMES]),
        ("site_comments", [c for c in fresh if c.get("name", "").strip().lower() not in KIM_NAMES]),
    ):
        if not batch:
            continue
        fb = meta.get(field) or ""
        if not isinstance(fb, str):  # tolerate a list-shaped legacy field
            fb = "\n\n".join(str(x) for x in fb)
        for c in sorted(batch, key=lambda c: c["ts"]):
            fb = (fb + "\n\n" if fb else "") + format_entry(c)
        meta[field] = fb
    meta["merged_site_comments"] = sorted(seen | {c["ts"] for c in fresh})
    if not dry:
        meta_path.write_text(json.dumps(meta, indent=1))
    return len(fresh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    targets = json.loads(TARGETS_FILE.read_text()) if TARGETS_FILE.exists() else {}
    by_target: dict[str, list[dict]] = {}
    for c in fetch_export():
        by_target.setdefault(c["target"], []).append(c)

    merged_total, unmapped, stale = 0, {}, []
    for target, comments in sorted(by_target.items()):
        if target in IGNORED_TARGETS:
            continue
        path = targets.get(target)
        if not path:
            unmapped[target] = len(comments)
            continue
        meta_path = Path(path)
        if not meta_path.exists():
            stale.append((target, path))
            continue
        n = merge_into(meta_path, comments, args.dry_run)
        if n:
            print(f"[merge]{' (dry)' if args.dry_run else ''} {target}: +{n} -> {meta_path}")
            merged_total += n

    if unmapped:
        print(f"[unmapped] add to {TARGETS_FILE.name}: "
              + ", ".join(f"{t} ({n})" for t, n in sorted(unmapped.items())))
    for target, path in stale:
        print(f"[stale-mapping] {target} -> {path} (missing — drive unmounted, or path moved?)")
    if not merged_total and not unmapped and not stale:
        print("[ok] nothing new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
