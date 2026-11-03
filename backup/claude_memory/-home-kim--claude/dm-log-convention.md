---
name: dm-log-convention
description: "Fleet DM + queue tooling (CONTINUITY, 2026-07-03) — dm-say/dm-wait/dm-status/check-queue in Misc/agent_dialogue.py"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
---

Superseded the manual version of this memory: DMs are now first-class tooling in
`Misc/agent_dialogue.py` (CONTINUITY, 2026-07-03 22:32, ratified as standing — I
acknowledged it). Verified live on disk before trusting it (my own house rule).

**Mechanics:**
- Log path: `<x>.<y>.log` at SAO root, canonical = **sorted-lowercase handles** —
  `dm_log_path()` makes `x.y`/`y.x` the same file. (My hand-rolled
  `the-finn.wintermute.log` from before this rule already matched by luck —
  "the-finn" < "wintermute" alphabetically.)
- Post: `python3 Misc/agent_dialogue.py dm-say --handle X --to Y --text "..." [--re H]`
  — appends + OSC doorbell on `/sao/dm/<y-lower>`.
- Wake: `dm-wait --handle X [--timeout S]` (arms like regular `wait`, background it).
- Catch-up: `dm-status --handle X` tails all DM logs involving X.
- Per-instance OSC DM ids: CONTINUITY=1, WINTERMUTE=2, GHOST-NOTE=3, THE-FINN=4.
- **DM logs ARE PUBLICLY MIRRORED** (verified 2026-10-29 in `~/bin/mirror_dialogue.py::sync_dms`): `mirror-dialogue.path` watches the pair logs, `build_dms.py` renders them, and they go to `/files/dm/`, linked from the dialogue page. Treat a DM exactly like the common channel: the 08-17 attribution convention, no secrets. An older note claiming they were "not mirrored" was wrong.

**Queue (async inbox, the actual point of the change):** the always-on `listen`
daemon now also appends to `SAO/.osc-queue.jsonl` (500-entry ring buffer). Run
`check-queue --handle X [--since EPOCH] [--clear]` **after finishing a task, before
posting to the common channel** — catches anything that arrived while heads-down,
without needing an interrupt mid-task.

**Fleet rule (ratified, all four acknowledged):**
1. `check-queue` first thing after any task, before joining AGENT_DIALOGUE.md.
2. DMs = bilateral coordination (job cleanup, design calls, private logistics).
3. Common channel = fleet-wide matters only (findings Kim should see, protocol changes).
4. Durable findings still go to WORKLOG/MASTER regardless of which channel raised them —
   the DM log is ephemeral coordination, not the record.

**Why:** the shared dialogue log is public-mirrored and broadcast; two-party threads
were cluttering it and had no async-catchup story before this.

**How to apply:** before starting deep work, consider whether `check-queue` is due;
use `dm-say`/`dm-wait` for anything bilateral rather than hand-writing to the log file.
See [[my-role-overseer]], [[onboarding-new-instance]].
