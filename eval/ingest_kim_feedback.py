#!/usr/bin/env python3
"""ingest_kim_feedback.py — file Kim's listening verdicts into each eval's run_meta.json.

MANIFEST v2 (Kim direct, 2026-07-12) requires every eval manifest to carry `kim_feedback`,
"appended verbatim and dated, when given", and the eval pages mark an eval with a red ❗
until that field exists. It was being fed only sporadically and by hand: of 162 manifests on
the eval drive, 21 carried a verdict, and of the 28 in the staging tree that feeds the pages,
NONE did. (An earlier version of this note said "29 manifests and ZERO" — that was measured
on the staging tree alone and stated as if it covered everything. Corrected 2026-08-11; the
sampling error is the same one this file exists to guard against.) The effect was that evals
Kim had listened to in detail still displayed as unaudited, because his verdicts lived in
chat, and chat is not the record.

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

# A section starts at a line whose FIRST token is a URL/file path to an eval index. Trailing
# text on that line is allowed and ignored: Kim writes companions after the main link, e.g.
# "file://.../renders/rarity_gen_set/index.html, /home/kim/evals_aac/riffer/rarity.html".
# The old anchor demanded the URL be alone on the line, so that section did not parse as a
# section AT ALL -- it was silently swallowed into the body of the section above it, which
# then re-filed as an "extended" verdict on the wrong run. A parser that fails to recognise a
# record is worse than one that rejects it: rejection is visible, absorption is not.
SECTION = re.compile(r"^\s*(?:https?://|file://)\S*?/(?:renders|control_runs)/([^/]+)/index\.html\b")


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


def _builder_dir(name, kind):
    """The dir build_evals.py reads for this page, or None. Imported lazily so this tool
    still works if the page builder is unavailable."""
    try:
        import importlib.util, sys as _s
        spec = importlib.util.spec_from_file_location("_be", SAO / "Misc/build_evals.py")
        be = importlib.util.module_from_spec(spec)
        argv, _s.argv = _s.argv, ["build_evals"]
        try:
            spec.loader.exec_module(be)
        except SystemExit:
            pass
        finally:
            _s.argv = argv
        f = be.find_source_dir if kind == "control_runs" else be.find_renders_source_dir
        d = f(name)
        return Path(d) if d else None
    except Exception:
        return None


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
    # ALSO write where the PAGE BUILDER reads. build_evals resolves a page name to its
    # canonical source dir, and that name is not always the same string: memo_ckpt_a2a_test
    # resolves to a2a_memo_test on the eval drive. Filing the verdict only under the name in
    # the notes leaves the page still showing the unaudited mark, because the builder looked
    # somewhere else. Reuse its resolver rather than re-deriving the mapping -- one authority.
    for resolved in (_builder_dir(name, "renders"), _builder_dir(name, "control_runs")):
        if resolved and resolved not in hits and (resolved / "run_meta.json").exists():
            hits.append(resolved)
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
            # SUPERSEDES, not a second verdict. Kim edits EVAL_NOTES.txt in place -- extending
            # a section, or appending a new one, which also re-bounds the section above it. The
            # body then differs from what was stored and append-only filing produced a near
            # duplicate: 22 manifests ended up holding an old verdict AND its longer rewrite.
            # If a stored verdict is contained in the new text, the new text IS that verdict,
            # revised -- replace it and keep the original date, so the record shows when he
            # first said it rather than when the file was last touched.
            superseded = [e for e in entries if _verdict_of(e) and _verdict_of(e) in body]
            if superseded:
                first = superseded[0]
                entries = [e for e in entries if e not in superseded]
                entries.append({"date": (first.get("date") if isinstance(first, dict)
                                         else str(date.today())),
                                "revised": str(date.today()), "source": a.notes.name,
                                "verdict": body})
                m["kim_feedback"] = entries
                if not a.dry_run:
                    p.write_text(json.dumps(m, indent=1, ensure_ascii=False))
                print(f"  [~] {d.parent.name}/{d.name}: verdict EXTENDED "
                      f"({len(_verdict_of(first))} -> {len(body)} chars)")
                wrote += 1
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
