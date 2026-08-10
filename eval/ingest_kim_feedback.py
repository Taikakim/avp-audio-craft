#!/usr/bin/env python3
"""ingest_kim_feedback.py — file Kim's listening verdicts into each eval's run_meta.json.

MANIFEST v2 (Kim direct, 2026-07-12) requires every eval manifest to carry `kim_feedback`,
"appended verbatim and dated, when given", and the eval pages mark an eval with a red ❗
until that field exists. The mechanism was built and then never fed: on 2026-08-11 a sweep
of the render dirs found 29 manifests and ZERO with kim_feedback. Every eval on the site was
flagged unaudited, including ones Kim had listened to in detail — because his verdicts lived
in chat, and chat is not the record.

Kim now keeps them in SAO/EVAL_NOTES.txt as he works through the backlog. This reads that
file and files each verdict into the matching run dir.

    eval/ingest_kim_feedback.py --dry-run     # show what would be written
    eval/ingest_kim_feedback.py               # write it

RULES, each one deliberate:
  * VERBATIM. Kim's text is copied, never paraphrased or summarised. A summary of a listening
    verdict is a different claim from the verdict.
  * APPEND, never replace. Re-running adds only genuinely new text; an existing entry is left
    alone, so this is safe to run repeatedly as the notes file grows.
  * DATED, with the source named, so a reader knows when it was said and where it came from.
  * A note whose dir does not exist is REPORTED, not dropped. A verdict that silently matches
    nothing is worse than no tool at all.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path

SAO = Path("/home/kim/Projects/SAO")
NOTES = SAO / "EVAL_NOTES.txt"
RENDER_ROOTS = [Path("/home/kim/evals_aac/renders"),
                Path("/run/media/kim/Mantu/sa3_lora_runs"),
                Path("/run/media/kim/Mantu/sa3_control_runs")]

# A section starts at a line that is just a URL or file:// path to an eval index.
SECTION = re.compile(r"^\s*(?:https?://|file://)\S*/renders/([^/]+)/index\.html\s*$")


def parse(text: str):
    """-> [(dir_name, body)] in file order. Body is everything up to the next section head."""
    out, cur, buf = [], None, []
    for line in text.splitlines():
        m = SECTION.match(line)
        if m:
            if cur:
                out.append((cur, "\n".join(buf).strip()))
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(line)
    if cur:
        out.append((cur, "\n".join(buf).strip()))
    return out


def _verdict_of(entry) -> str:
    """The verdict text of a stored entry, whatever shape it was written in."""
    return (entry.get("verdict", "") if isinstance(entry, dict) else str(entry)).strip()


def dedupe(entries):
    """Drop repeated verdicts, keeping the earliest occurrence of each."""
    seen, out = set(), []
    for e in entries:
        k = _verdict_of(e)
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def targets(name):
    """Run dirs this note applies to. A note may name a family whose dirs are per-epoch
    (a2a_angelic_r64tiered_lr1e4 -> ..._ep5, ..._ep7), so a prefix match is intentional."""
    hits = []
    for root in RENDER_ROOTS:
        if not root.exists():
            continue
        exact = root / name
        if (exact / "run_meta.json").exists():
            hits.append(exact)
            continue
        hits += [d for d in sorted(root.glob(f"{name}*")) if (d / "run_meta.json").exists()]
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", type=Path, default=NOTES)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sections = parse(a.notes.read_text())
    print(f"[kim-feedback] {len(sections)} sections in {a.notes.name}")
    wrote = skipped = unmatched = 0
    for name, body in sections:
        if not body.strip():
            continue
        dirs = targets(name)
        if not dirs:
            print(f"  [?] {name}: NO run dir with a run_meta.json -- verdict not filed")
            unmatched += 1
            continue
        for d in dirs:
            p = d / "run_meta.json"
            m = json.loads(p.read_text())
            prior = m.get("kim_feedback")
            entries = prior if isinstance(prior, list) else ([prior] if prior else [])
            entries = dedupe(entries)          # heal any doubles a prior buggy run wrote
            # Compare the verdict FIELD, not str(entry): repr() escapes newlines, so a
            # multi-line verdict never matched itself inside str(dict) and every re-run
            # appended a duplicate. Caught by simply running the tool twice -- which is the
            # cheapest test an append-only tool can have, and the one worth always doing.
            if any(body.strip() == _verdict_of(e) for e in entries):
                skipped += 1
                continue
            entries.append({"date": str(date.today()), "source": a.notes.name,
                            "verdict": body})
            m["kim_feedback"] = entries
            # Print the ROOT, not just the basename: most evals exist TWICE -- the staging
            # copy under evals_aac that feeds the pages, and the canonical copy on the eval
            # drive (MASTER: eval output lives on the drive). Both need the verdict or
            # whichever one a reader opens still shows ❗ unaudited. Printing bare basenames
            # made that correct behaviour look like a double-write bug.
            print(f"  [+] {d.parent.name}/{d.name}: {len(body)} chars"
                  + (" (DRY)" if a.dry_run else ""))
            if not a.dry_run:
                p.write_text(json.dumps(m, indent=1, ensure_ascii=False))
            wrote += 1
    print(f"[kim-feedback] filed {wrote}, already present {skipped}, unmatched {unmatched}")
    return 1 if unmatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
