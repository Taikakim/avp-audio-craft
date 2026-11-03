---
name: mix-tempo-ramp-rules
description: Kim's standing rules for DJ-mix tempo handling (slow 0.25 BPM ramps, incoming pitched down max 5%, tracks near original BPM) and pre-morphing the outgoing track's key; he has repeated these several times
metadata:
  type: feedback
---

Tempo in the SAO DJ mixes (Kim 2026-11-03, "I've several times now suggested this", annoyed that agents forget):
- Nudge the OUTGOING track's BPM in increments of 0.25 BPM ramps, each over about 10 s, in less hectic sections where possible. Rapid BPM ramps sound very bad.
- Possibly also pitch the INCOMING down, so least pitch shifting is needed overall; incoming must not be pitched down more than 5%.
- Tracks should play at or close to their original BPM most of the time.
- Key/chroma: morph (or shift) the outgoing track's chroma toward the incoming's BEFORE the incoming starts mixing in, not only inside the bridge.

**Why:** these were suggested repeatedly and not implemented; Kim cannot track which agents forgot.
**How to apply:** before touching `--tempo-plan` (eval/render_v7_smoketest.py) or any mix planner, read EXPERIMENTS F7 where the rules are also written; implement them, do not re-propose. See [[fleet-comms-stay-responsive]].
