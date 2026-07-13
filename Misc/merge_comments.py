#!/usr/bin/env python3
"""merge_comments.py — pull site comments into eval manifests (manifest v2).

The merge side of the comment loop (W's endpoint /files/comment.php, 2026-07-13):
Kim comments on an eval page -> this script pulls the token-gated export, resolves
each record's SCOPE, and appends the comment VERBATIM + dated into the matching
manifest field — which clears the red-❗ unaudited mark AT THAT LEVEL ONLY on the
next page rebuild (eval-tables spec §16/§16a). Comment text is opaque data end to end.

Scopes (endpoint v2 record: {ts, iso, ip, name, text, page, model, ckpt, clip};
model/ckpt/clip are empty strings when unset; bare `target` = legacy page alias).
Resolution order clip > ckpt > model > page:

  model set  -> run dir = sa3_lora_runs/<label> or sa3_control_runs/<label>
                (same label source as models.html / the matrix dropdowns);
                  clip set -> comments_clips.json sidecar next to run_meta,
                              {clip: {kim_feedback, site_comments}}
                  ckpt set -> run_meta.json ckpt_feedback[ckpt] / ckpt_site_comments[ckpt]
                  else     -> run_meta.json kim_feedback / site_comments (run level)
  model unset -> page mapping via comment_targets.json { "<page>": "<run_meta path>" };
                 clip set routes into that manifest's comments_clips.json sidecar.

(Per-ckpt eval-dir manifests — onset_eval_<run>_<step>/ — are a later upgrade once
ckpt tags are canonical across pages; until then ckpt comments live in the run-level
manifest under the per-ckpt keys, which is what builders should read for per-ckpt ❗.)

Attribution rule (the ❗ mark is "has KIM audited this", so only Kim's words may
clear it): comments with no name, or named Kim, merge into the kim_feedback-family
field; anything else (fleet handles, third parties) merges into the site_comments
sibling — kept verbatim + dated, but does NOT flip the audited bit.

Idempotent: merged comment timestamps are recorded in the run_meta.json
(`merged_site_comments`); re-runs skip them. Unmapped pages/models are REPORTED,
never guessed.

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
MODEL_ROOTS = (Path("/run/media/kim/Mantu/sa3_lora_runs"),
               Path("/run/media/kim/Mantu/sa3_control_runs"))  # = build_model_index LORA/CTRL
IGNORED_PAGES = {"merge_test"}  # endpoint smoke tests, never merged
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


def is_kim(c: dict) -> bool:
    return c.get("name", "").strip().lower() in KIM_NAMES


def model_run_meta(label: str) -> Path | None:
    for root in MODEL_ROOTS:
        d = root / label
        if d.is_dir():
            return d / "run_meta.json"
    return None


def resolve(c: dict, page_targets: dict) -> tuple[Path, str, str | None] | str:
    """(run_meta_path, scope, subkey) for a record, or an error tag string."""
    page = (c.get("page") or c.get("target") or "").strip()
    model = (c.get("model") or "").strip()
    ckpt = (c.get("ckpt") or "").strip()
    clip = (c.get("clip") or "").strip()
    if model:
        meta = model_run_meta(model)
        if meta is None:
            return f"unmapped-model:{model}"
        if clip:
            return (meta, "clip", clip)
        if ckpt:
            return (meta, "ckpt", ckpt)
        return (meta, "model", None)
    if page in IGNORED_PAGES:
        return "ignored"
    if page not in page_targets:
        return f"unmapped-page:{page}"
    meta = Path(page_targets[page])
    return (meta, "clip", clip) if clip else (meta, "page", None)


def append_text(existing, entry: str) -> str:
    if existing and not isinstance(existing, str):  # tolerate a list-shaped legacy field
        existing = "\n\n".join(str(x) for x in existing)
    return (existing + "\n\n" if existing else "") + entry


def merge_group(meta_path: Path, group: list[tuple[str, str | None, dict]], dry: bool) -> int:
    """Merge this manifest's comments: [(scope, subkey, record)]. Returns #new."""
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    else:
        # pre-v2 run dir without a sidecar: create a minimal one rather than drop feedback
        meta = {"purpose": f"(created by merge_comments.py for site comments on {meta_path.parent.name})"}
    seen = set(meta.get("merged_site_comments", []))
    sidecar_path = meta_path.parent / "comments_clips.json"
    sidecar = json.loads(sidecar_path.read_text()) if sidecar_path.exists() else {}
    n, sidecar_dirty = 0, False
    for scope, subkey, c in sorted(group, key=lambda g: g[2]["ts"]):
        if c["ts"] in seen:
            continue
        field = "kim_feedback" if is_kim(c) else "site_comments"
        entry = format_entry(c)
        if scope == "clip":
            slot = sidecar.setdefault(subkey, {})
            slot[field] = append_text(slot.get(field), entry)
            sidecar_dirty = True
        elif scope == "ckpt":
            slot = meta.setdefault("ckpt_feedback" if field == "kim_feedback" else "ckpt_site_comments", {})
            slot[subkey] = append_text(slot.get(subkey), entry)
        else:  # model / page -> run-level
            meta[field] = append_text(meta.get(field), entry)
        seen.add(c["ts"])
        n += 1
    if n and not dry:
        meta["merged_site_comments"] = sorted(seen)
        meta_path.write_text(json.dumps(meta, indent=1))
        if sidecar_dirty:
            sidecar_path.write_text(json.dumps(sidecar, indent=1))
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    page_targets = json.loads(TARGETS_FILE.read_text()) if TARGETS_FILE.exists() else {}
    groups: dict[Path, list] = {}
    problems: dict[str, int] = {}
    for c in fetch_export():
        r = resolve(c, page_targets)
        if isinstance(r, str):
            if r != "ignored":
                problems[r] = problems.get(r, 0) + 1
            continue
        meta_path, scope, subkey = r
        groups.setdefault(meta_path, []).append((scope, subkey, c))

    merged_total = 0
    for meta_path, group in sorted(groups.items()):
        n = merge_group(meta_path, group, args.dry_run)
        if n:
            scopes = ",".join(sorted({s for s, _, _ in group}))
            print(f"[merge]{' (dry)' if args.dry_run else ''} {meta_path.parent.name} [{scopes}]: +{n} -> {meta_path}")
            merged_total += n

    for tag, count in sorted(problems.items()):
        print(f"[{tag}] {count} comment(s) — add the mapping / check the label, rerun")
    if not merged_total and not problems:
        print("[ok] nothing new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
