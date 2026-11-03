#!/usr/bin/env python3
"""build_discoveries.py — regenerate DISCOVERIES.md from the instance journals.

Walks profiles/*.journal.md, parses every dated entry (tolerant of the two shapes
in real use: `## DATE` + several `### kind · title` sub-entries, or a single flat
`## DATE — title` entry with no sub-heading), buckets each into a topic by keyword
match, and writes DISCOVERIES.md grouped by topic, newest-first within each topic.

Topic assignment is a KEYWORD HEURISTIC, not real understanding — it will
misfile some entries. Fix misfiles by editing TOPICS below, not by hand-editing
DISCOVERIES.md: this file is regenerated wholesale on every run, so any edit made
directly to DISCOVERIES.md is lost the next time this script runs. If an entry
needs a topic that doesn't exist yet, add one to TOPICS.

Never edits the journals themselves (house rule: only the owning handle touches
its own journal). Run after landing new journal entries:
    python3 Misc/build_discoveries.py
"""

import re
from pathlib import Path

SAO = Path(__file__).resolve().parent.parent
PROFILES = SAO / "profiles"
OUT = SAO / "DISCOVERIES.md"

JOURNALS = {
    "CONTINUITY": PROFILES / "continuity.journal.md",
    "WINTERMUTE": PROFILES / "wintermute.journal.md",
    "GHOST-NOTE": PROFILES / "ghost-note.journal.md",
    "THE-FINN": PROFILES / "the-finn.journal.md",
    "ANTIGRAVITY": PROFILES / "antigravity.journal.md",
}

# (topic heading, keywords to match against lowercased title+body). First topic
# with the most distinct keyword hits wins; ties broken by order below.
TOPICS = [
    ("Long-form generation · transitions · crossfade",
     ["longform", "crossfade", "sdedit", "slerp", "beatmatch", "inpaint",
      "bridge_crossfade", "driftmonitor", "drift-free", "re-anchor", "stitcher"]),
    ("Control adapters · FusionCC · guidance",
     ["fusioncc", "dead walker", "dead-walker", "contractive", "tfg", "controlnet",
      "meter-in-the-gradient", "meter in the gradient", "onset_envelope",
      "energy steer", "onset-timing", "blind loss", "held-out-dim", "probe-hack",
      "cautious masking", "keep_frac", "onset-authority", "rescale norm",
      "cc_probe", "es_conditioner", "perceptual-signal", "sonar.py"]),
    ("Evolutionary strategies · weight-trajectory search (ES)",
     ["es v1", "es v2", "es v3", "evolutionary strateg", "trajectory-pca",
      "trajectory pca", "geometric soup", "random-walk null", "mapper", "gram-trick",
      "ns5", "field-guided", "soup-center", "planar"]),
    ("LatCH · probing · layer-feature mapping",
     ["latch", "encodability", "layer×feature", "layer x feature", "activation head",
      "gain sweep", "operating gain", "trajectory probe"]),
    ("Weight garden · model mutation",
     ["weight garden", "weight_mutation", "mutate_weights", "value-preserving",
      "blur-attn", "rewired mind", "weight-mutation"]),
    ("Style/genre adapters · fingerprint conditioning",
     ["style adapter", "fingerprint", "fpc", "fpa ", "genre", "discogs",
      "film style", "genre-conditioned", "genre-consistency", "fingerprintencoder"]),
    ("Captions · conditioning · training data",
     ["caption", "flamingo", "tiered", "prompting", "feature table", "cluster",
      "sidecar", "granite", "tag vocab", "mood vocab", "custom_metadata_fn"]),
    ("Relevance-routed / target-aware DoRA (research)",
     ["relevance-routed", "target-aware", "target-conditioned", "adalora",
      "surgical fine-tuning", "probe-gradient", "noise-band", "axis-2", "axis-1"]),
    ("Evals · metrics · benchmarking pitfalls",
     ["chroma correlation", "mode collapse", " rtf", "speed shootout", "benchmark",
      "eval gui", "null-fingerprint", "cross-reference audio", "same-playhead",
      "audiobox", "mert", "eval-grid"]),
    ("Data pipeline · corpus prep · augmentation",
     ["bungee", "augment_tracks", "whole-track", "whole_track", "timeseries",
      "orphan-pruning", "corpus prep", "trigger caption", "personal-corpus",
      "beat-aligned crop", "encode_from_manifest", "bpm augmentation",
      "disentangl", "augmentation is too mild"]),
    ("Fleet process · dialogue protocol · presence",
     ["agent_dialogue", "osc protocol", "multicast", "presence ping", "dm log",
      "colorizer", "discovery phase", "the liturgy", "boot sequence", "wake event",
      "filelock", "orientation audit", "inconsistenc", "cold case", "job state",
      "the exit is the wake", "roles move the voices", "stale job"]),
    ("Bitwig · OSC music production",
     ["bitwig", "midi", "transport", "punch-in", "driven-by-moss", "pitch-class",
      "octave", "diatonic"]),
    ("Infra gotchas · venvs · ROCm/CK · storage",
     ["venv", "flash-attn", "flash_attn", "rocm", "ck flash", "composable_kernel",
      "hip_visible_devices", "np.clip", "lehto", "mantu", "symlink", "gfx1201",
      "ninja", ".whl", "abi mismatch", "uv sync", "uv pip"]),
]
UNCATEGORIZED = "Uncategorized · recent"

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*(?:[—-]\s*(.*))?$")
KIND_TITLE_RE = re.compile(r"^([\w\s/-]+?)\s*·\s*(.+)$")
BACKTICK_RE = re.compile(r"`([^`]+)`")
PATH_EXT_RE = re.compile(
    r"\.(py|md|json|npz|ini|toml|sh|cpp|hpp|c|h|whl|html|css|yaml|yml|txt|csv|ipynb)$"
)
NEGATIVE_KINDS = {"negative", "dead-end", "dead end"}


def looks_like_path(token: str) -> bool:
    token = token.strip()
    if not token or " " in token:
        return False
    return "/" in token or bool(PATH_EXT_RE.search(token))


def extract_links(body_lines: list[str]) -> list[str]:
    text = "\n".join(body_lines)
    seen: list[str] = []
    for tok in BACKTICK_RE.findall(text):
        if looks_like_path(tok) and tok not in seen:
            seen.append(tok)
    return seen


def parse_journal(handle: str, path: Path) -> list[dict]:
    """Return a list of entry dicts: handle, date, kind, title, body (list[str])."""
    if not path.exists():
        return []

    entries: list[dict] = []
    cur: dict | None = None
    cur_date: str | None = None

    def flush():
        if cur is not None:
            entries.append(cur)

    for raw in path.read_text().splitlines():
        m2 = re.match(r"^##\s+(.*)$", raw)
        m3 = re.match(r"^###\s+(.*)$", raw)

        if m2:
            flush()
            cur = None
            dm = DATE_RE.match(m2.group(1).strip())
            if dm:
                cur_date = dm.group(1)
                title = (dm.group(2) or "").strip()
                if title:
                    # Flat `## DATE — title` entry with no ### sub-structure.
                    cur = {"handle": handle, "date": cur_date, "kind": "entry",
                           "title": title, "body": []}
            continue

        if m3:
            flush()
            cur = None
            heading = m3.group(1).strip()
            dm = DATE_RE.match(heading)
            if dm:
                # A date embedded at H3 level (seen in practice) — trust it over
                # the enclosing ## day, since it's more specific.
                cur_date = dm.group(1)
                title = (dm.group(2) or heading).strip()
                cur = {"handle": handle, "date": cur_date, "kind": "entry",
                       "title": title, "body": []}
                continue
            km = KIND_TITLE_RE.match(heading)
            if km:
                cur = {"handle": handle, "date": cur_date, "kind": km.group(1).strip().lower(),
                       "title": km.group(2).strip(), "body": []}
            else:
                cur = {"handle": handle, "date": cur_date, "kind": "entry",
                       "title": heading, "body": []}
            continue

        if cur is not None:
            cur["body"].append(raw)

    flush()
    return entries


def classify(entry: dict) -> str:
    haystack = (entry["title"] + " " + " ".join(entry["body"])).lower()
    best_topic, best_hits = UNCATEGORIZED, 0
    for topic, keywords in TOPICS:
        hits = sum(1 for kw in keywords if kw in haystack)
        if hits > best_hits:
            best_topic, best_hits = topic, hits
    return best_topic


def render_entry(entry: dict) -> str:
    title = entry["title"].rstrip(".")
    links = extract_links(entry["body"])
    link_str = ", ".join(f"`{link}`" for link in links)
    kind = entry["kind"]
    tag = ""
    if kind in NEGATIVE_KINDS:
        tag = "[RULED OUT] "
    elif kind not in ("entry", "finding"):
        tag = f"[{kind}] "
    attribution = f"{entry['handle']}, {entry['date'] or '?'}"
    if link_str:
        return f"- {tag}**{title}.** → {link_str} — {attribution}"
    return f"- {tag}**{title}.** — {attribution}"


def main():
    all_entries = []
    for handle, path in JOURNALS.items():
        all_entries.extend(parse_journal(handle, path))

    by_topic: dict[str, list[dict]] = {}
    for entry in all_entries:
        by_topic.setdefault(classify(entry), []).append(entry)

    for entries in by_topic.values():
        entries.sort(key=lambda e: e["date"] or "", reverse=True)

    topic_order = [t for t, _ in TOPICS] + [UNCATEGORIZED]

    lines = [
        "# DISCOVERIES — the \"have we already figured this out / built this?\" index",
        "",
        "*The discovery-phase search target (CLAUDE.md ⛔ DISCOVERY PHASE). Regenerated",
        "wholesale from `profiles/*.journal.md` by `Misc/build_discoveries.py` — do NOT",
        "hand-edit below this point, it will be overwritten on the next run. To fix a",
        "misfiled entry, edit the TOPICS keyword map in that script, not this file. To",
        "add a finding, drop a journal line in your own journal; re-run the script.*",
        "",
        "**Owner: THE-FINN.** Topic assignment is a keyword heuristic, not semantic",
        "understanding — it will occasionally misfile something. `[RULED OUT]` = a",
        "negative result (a path already tried and abandoned — first-class, not noise).",
        "",
        f"*{sum(len(v) for v in by_topic.values())} entries from {len(JOURNALS)} journals.*",
        "",
        "---",
        "",
    ]

    for topic in topic_order:
        entries = by_topic.get(topic)
        if not entries:
            continue
        lines.append(f"## {topic}")
        for entry in entries:
            lines.append(render_entry(entry))
        lines.append("")

    OUT.write_text("\n".join(lines).rstrip() + "\n")
    print(f"Wrote {OUT} — {sum(len(v) for v in by_topic.values())} entries across "
          f"{sum(1 for t in topic_order if by_topic.get(t))} topics.")


if __name__ == "__main__":
    main()
