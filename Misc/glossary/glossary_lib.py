# Owner: WINTERMUTE (created 2026-10-26)
# Last edited: WINTERMUTE 2026-10-26 -- type checks for text fields, options, papers (bad entry = build error, not traceback)
"""Shared glossary pieces: the blog's inline renderer, entry loading and the build-time validator."""
import html
import json
import re
from pathlib import Path

REQUIRED = ("id", "term", "plain", "quiz")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def inline(t: str) -> str:
    """Inline syntax shared by blog posts and glossary entries: `code`, **bold**, *em*, [text](https://...)."""
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    # [text](https://...) links; http(s) only, so a relative or local path in a draft stays visible text
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    return t


def load_glossary(directory) -> list:
    """All entries of every *.json in `directory` (sorted by file name). Raises ValueError on bad files."""
    entries = []
    for f in sorted(Path(directory).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{f.name}: not valid JSON ({exc})") from exc
        if not isinstance(data, list):
            raise ValueError(f"{f.name}: the top level must be a JSON list of entries")
        entries.extend(data)
    return entries


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).lower()


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _sentence_count(text: str) -> int:
    text = re.sub(r"`[^`]*`", "x", text).strip()
    return len(re.split(r"(?<=[.!?])\s+(?=[A-Z\"(\[])", text)) if text else 0


def _check_question(label: str, n: int, q, errors: list) -> None:
    where = f"{label}: question {n}"
    if not isinstance(q, dict):
        errors.append(f"{where} is not an object")
        return
    for f in ("q", "options", "answer", "why", "level"):
        if f not in q or q[f] in (None, "", []):
            errors.append(f"{where}: missing required field '{f}'")
    if "level" in q and q["level"] not in (None, "") and not (_is_int(q["level"]) and 1 <= q["level"] <= 3):
        errors.append(f"{where}: level must be 1, 2 or 3")
    opts = q.get("options")
    if opts not in (None, "", []) and not (isinstance(opts, list) and len(opts) == 5):
        got = len(opts) if isinstance(opts, list) else "not a list"
        errors.append(f"{where}: needs exactly 5 options, found {got}")
    elif isinstance(opts, list):
        for k, o in enumerate(opts):
            if not isinstance(o, str):
                errors.append(f"{where}: option {k} must be a string")
    for f in ("q", "why"):
        if f in q and q[f] not in (None, "", []) and not isinstance(q[f], str):
            errors.append(f"{where}: '{f}' must be a string")
    ans = q.get("answer")
    if "answer" in q and ans is not None and not (_is_int(ans) and 0 <= ans <= 4):
        errors.append(f"{where}: answer {ans!r} is out of range (0-4)")
    wrong = q.get("wrong")
    if wrong is not None:
        if not isinstance(wrong, dict):
            errors.append(f"{where}: 'wrong' must map option indexes to text")
            return
        for k in wrong:
            if not (isinstance(k, str) and k.isdigit() and 0 <= int(k) <= 4):
                errors.append(f"{where}: 'wrong' key {k!r} is not an option index (0-4)")
            elif _is_int(ans) and int(k) == ans:
                errors.append(f"{where}: 'wrong' is given for the correct option ({k})")
            if not isinstance(wrong[k], str):
                errors.append(f"{where}: 'wrong' text for {k!r} must be a string")


def validate(entries, known_viz, publish: bool, used_ids=None):
    """Check every entry against the spec's build errors. Returns (errors, warnings).

    known_viz: set of animation module names that exist (file stems under site/help/viz/).
    publish:   unknown viz modules and unreviewed quizzes are errors instead of warnings.
    used_ids:  ids of the entries a page actually uses (including entries reachable from them).
               The quiz_reviewed rule applies to these only; None skips the rule.
    """
    errors, warnings = [], []
    seen_ids = {}
    owners = {}          # normalised term/alias -> (entry index, kind)
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            errors.append(f"entry #{i}: not an object")
            continue
        label = str(e.get("id") or f"entry #{i}")
        for f in REQUIRED:
            if f not in e or e[f] in (None, "", []):
                errors.append(f"{label}: missing required field '{f}'")
        eid = e.get("id")
        if isinstance(eid, str) and eid:
            if not _SLUG.match(eid):
                errors.append(f"{label}: id must be a lowercase slug (a-z, 0-9, hyphen)")
            if eid in seen_ids:
                errors.append(f"{label}: duplicate id (also entry #{seen_ids[eid]})")
            seen_ids.setdefault(eid, i)
        names = []
        if isinstance(e.get("term"), str) and e["term"].strip():
            names.append((e["term"], "term"))
        aliases = e.get("aliases") or []
        if not isinstance(aliases, list):
            errors.append(f"{label}: aliases must be a list")
            aliases = []
        names += [(a, "alias") for a in aliases if isinstance(a, str) and a.strip()]
        for text, kind in names:
            n = _norm(text)
            if n in owners:
                j, prev_kind = owners[n]
                other = str(entries[j].get("id") or f"entry #{j}")
                if j == i:
                    errors.append(f"{label}: duplicate alias '{text}' (repeats its own {prev_kind})")
                else:
                    errors.append(f"{label}: {kind} '{text}' collides with {prev_kind} of '{other}'")
            else:
                owners[n] = (i, kind)
        for f in ("plain", "ours", "deeper"):
            if e.get(f) not in (None, "", []) and not isinstance(e[f], str):
                errors.append(f"{label}: '{f}' must be a string")
        papers = e.get("papers")
        if papers not in (None, "", []):
            if not isinstance(papers, list):
                errors.append(f"{label}: papers must be a list")
            else:
                for k, pp in enumerate(papers):
                    if not (isinstance(pp, dict) and isinstance(pp.get("title"), str) and pp.get("title")
                            and isinstance(pp.get("url"), str) and pp.get("url")):
                        errors.append(f"{label}: papers item {k} needs a 'title' and a 'url' (strings)")
        if isinstance(e.get("plain"), str) and _sentence_count(e["plain"]) > 1:
            warnings.append(f"{label}: 'plain' should be one sentence ({_sentence_count(e['plain'])} found)")
        quiz = e.get("quiz")
        if isinstance(quiz, list) and quiz:
            if not 3 <= len(quiz) <= 5:
                errors.append(f"{label}: needs 3-5 quiz questions, found {len(quiz)}")
            for n, q in enumerate(quiz, 1):
                _check_question(label, n, q, errors)
        elif quiz not in (None, "", []):
            errors.append(f"{label}: quiz must be a list of questions")
        viz = e.get("viz")
        if viz:
            mod = viz.get("module") if isinstance(viz, dict) else None
            if not isinstance(mod, str) or not mod:
                errors.append(f"{label}: viz needs a 'module' name")
            elif mod not in known_viz:
                (errors if publish else warnings).append(f"{label}: unknown viz module '{mod}'")
        if used_ids is not None and eid in used_ids and not e.get("quiz_reviewed"):
            (errors if publish else warnings).append(f"{label}: quiz_reviewed is empty but a page uses this entry")
    return errors, warnings
