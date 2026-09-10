#!/usr/bin/env python
"""Re-extract SA3_STUDIO_PORT_MAP.md from the workflow journal.

The sa3-studio-plan workflow (run wf_91eb340d-2ae, 2026-09-10) wrote each agent's
structured result to journal.jsonl. Re-run this any time to fold in agents that have
since finished (the synthesis and the two critic passes were still running when the
run was parked). Safe to re-run; it overwrites the .md.

    python plots/explorer_sa3/extract_port_map.py
"""
import json, io, os, sys

JOURNAL = os.environ.get("SA3_WF_JOURNAL", r"C:\Users\kim.ake\.claude\projects\C--Users-kim-ake--local-bin\d97c0469-ca75-4658-bd3f-85770fdc68dd\subagents\workflows\wf_91eb340d-2ae\journal.jsonl")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SA3_STUDIO_PORT_MAP.md")

def esc(v):
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")

def main():
    if not os.path.exists(JOURNAL):
        sys.exit("journal not found: " + JOURNAL)
    res = []
    for line in open(JOURNAL, encoding="utf-8"):
        try: d = json.loads(line)
        except Exception: continue
        if (d.get("type") or d.get("event")) == "result":
            res.append(d.get("result"))
    maps  = [r for r in res if isinstance(r, dict) and "surface" in r]
    plans = [r for r in res if isinstance(r, dict) and "angle" in r]
    texts = [r for r in res if isinstance(r, str) and r.strip()]
    b = io.StringIO(); w = b.write
    w("# SA3 Studio - port map\n\n")
    w("*Machine-generated from workflow run `wf_91eb340d-2ae` (2026-09-10) by\n")
    w("`extract_port_map.py`. Agent output, NOT verified against the code by a human.\n")
    w("Re-run the extractor to fold in agents that finished later.*\n\n---\n\n")
    w("## Part 1 - Surface maps (%d)\n\n" % len(maps))
    for m in maps:
        w("### %s\n\n%s\n\n" % (m.get("surface", "?"), m.get("summary", "")))
        cs = m.get("controls") or []
        if cs:
            w("**Controls (%d)**\n\n| id | label | kind | payload field | notes |\n|---|---|---|---|---|\n" % len(cs))
            for c in cs:
                w("| `%s` | %s | %s | %s | %s |\n" % (esc(c.get("id")), esc(c.get("label")),
                  esc(c.get("kind")), esc(c.get("payload_field")), esc(c.get("notes"))))
            w("\n")
        for k, t in (("api_calls", "API calls"), ("behaviors", "Behaviors to preserve"),
                     ("hazards", "Rewrite hazards"), ("open_questions", "Open questions")):
            v = m.get(k) or []
            if v: w("**%s**\n\n" % t + "".join("- %s\n" % x for x in v) + "\n")
        w("---\n\n")
    w("## Part 2 - Build plans (%d)\n\n" % len(plans))
    for pl in plans:
        w("### Angle: %s\n\n**Architecture**\n\n%s\n\n" % (pl.get("angle", "?"), pl.get("architecture", "")))
        fp = pl.get("feature_parity") or []
        if fp:
            w("**Feature parity**\n\n| capability | in design? | disposition |\n|---|---|---|\n")
            for f in fp:
                w("| %s | %s | %s |\n" % (esc(f.get("capability")), esc(f.get("in_design")), esc(f.get("disposition"))))
            w("\n")
        ms = pl.get("milestones") or []
        if ms:
            w("**Milestones**\n\n")
            for i, x in enumerate(ms, 1):
                w("%d. **%s** - %s\n" % (i, x.get("name", ""), x.get("deliverable", "")))
                if x.get("depends_on"): w("   - depends on: %s\n" % x["depends_on"])
                if x.get("risk"): w("   - risk: %s\n" % x["risk"])
            w("\n")
        for k, t in (("design_corrections", "Design corrections"), ("backend_changes", "Backend changes needed")):
            v = pl.get(k) or []
            if v: w("**%s**\n\n" % t + "".join("- %s\n" % x for x in v) + "\n")
        w("**Biggest risk:** %s\n\n---\n\n" % pl.get("biggest_risk", ""))
    if texts:
        w("## Part 3 - Critic passes (%d)\n\n" % len(texts))
        for t in texts:
            w(t + "\n\n---\n\n")
    open(OUT, "w", encoding="utf-8").write(b.getvalue())
    print("wrote %s (%d bytes)" % (OUT, os.path.getsize(OUT)))
    print("maps=%d plans=%d critics=%d" % (len(maps), len(plans), len(texts)))

if __name__ == "__main__":
    main()
