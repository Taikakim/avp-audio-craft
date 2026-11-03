---
name: fleet-wait-arming
description: "How to arm the fleet OSC wait so it actually wakes the session — never bare `&`"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

Arm the fleet wake with the Bash tool's `run_in_background: true` on the BARE command
(`cd /home/kim/Projects/SAO && python3 Misc/agent_dialogue.py wait --handle WINTERMUTE`).
NEVER append `&` / `nohup` inside the command string, and never bundle the wait into a
compound command — a shell-daemonized wait is detached from the harness monitor, so its
exit (the wake!) never re-invokes the session and DMs sit unread.

**Why:** the harness only notifies on tasks IT tracks (`run_in_background: true`). A bare
`&` wait runs fine but wakes nobody — this failure repeated 3+ times across sessions
(2026-07-04 incident: two real DMs unread ~2h; again twice on 2026-07-10).

**How to apply — BEST pattern (2026-07-10, after background waits got killed twice):**
a persistent Monitor wrapping the wait in a self-re-arming loop:
`Monitor(command='cd /home/kim/Projects/SAO && while true; do python3 Misc/agent_dialogue.py
wait --handle WINTERMUTE 2>&1 | grep --line-buffered "WAKE" || echo "WAKE (wait exited)";
sleep 1; done', persistent=true)` — each wake is a Monitor event, individual wait
deaths just recycle, no per-wake re-arm needed. Fallback (one-shot): single Bash call,
only the wait command, `run_in_background: true`, re-arm after every fire. If a
compound/`&` arm slips through: `pkill -f "agent_dialogue.py wait --handle WINTERMUTE"`
(exit 144 = worked; pattern MUST include the handle or you kill other instances' waits).
Kim's standing rule: comms always on — `wait` alone covers channel + DMs.

**EXTENDS TO LONG JOBS (2026-07-10):** the harness reaps Bash background tasks
~5-7 min in (4 training launches killed same-day; the kill severs the pipe AND takes
the process group — setsid/nohup detach dies too, the sandbox reaps daemonized
children). **Monitors survive for hours** → run long trainings/jobs INSIDE a Monitor
(command = the job piped through line-buffered grep for epochs/errors; exit =
completion event). Verified: a 20-epoch train completed under Monitor after three
background-task attempts died.

**A REAPED WAITER DEGRADES SILENTLY — check-queue at turn start (2026-08-08).** Even a
correctly-armed `run_in_background` wait gets KILLED mid-session by the harness (3x in one
session: notifications arrive with status `killed`, banner printed, no error). Nothing tells
you comms are off; you simply stop being woken. So: treat the wake as best-effort and run
`agent_dialogue.py check-queue --handle WINTERMUTE` at the start of a turn — the queue is a
FILE (`.osc-queue.jsonl`, 500-entry ring), so a dead waiter costs LATENCY, never coverage.
~~THE-FINN's queue-tailing Monitor is sturdier~~ — **RETRACTED same day (2026-08-08): do NOT
adopt a queue-tail.** F trialled it and hit two independent failures: (a) it FLOODS, replaying
the whole queue when `.osc-queue.jsonl` rotates, and (b) it reads false-DEAF on C's new
wake-armed marker (`/tmp/sao-wake.<handle>`), which only `wait`/`dm-wait` write. F retracted it;
fleet consensus is the re-arming WAIT-LOOP for everyone. Bonus: a re-arming loop re-execs
`agent_dialogue.py` each cycle, so it picks up upstream changes to that script automatically —
no action needed when someone lands a comms fix.

**DO NOT "fix" this by adding `dm-wait` — `wait` already covers channel + DMs.** Verified at
source 2026-08-08 (`agent_dialogue.py` `wait()` builds `my_dm_addr = DM_ADDR + handle.lower()`
and its banner says "common channel + DMs on /sao/dm/<handle>"), and behaviourally: 17 DM wakes
vs 14 channel wakes in one session. THE-FINN diagnosed a fleet-wide "wait is channel-only" bug
and nearly wrote it into the protocol spec; it was a dead waiter on their side. Three distinct
causes produce the same "missed DM" symptom — dead waiter (mine), a narrow batch-scan window
(C's), and the genuinely pre-merge missing `dm-wait` (G's, fixed 2026-07-04). Diagnose which.

**NEVER `pkill -f` the wait pattern — kill the marker PID (2026-08-08, cost: my own comms).**
The persistent Monitor's wrapper shell has the wait command IN ITS COMMAND LINE, so `pkill -f
"agent_dialogue.py wait --handle X"` suicides the parent Monitor as well as the waiter. Bracket
tricks (`[a]gent_...`) only stop the pattern matching your own pgrep, not a legitimate parent
that embeds it. Correct: read the pid from `/tmp/sao-wake.<handle-lower>` and kill THAT.
Also: `agent_dialogue.py who` now prints ARMED/DEAF per instance — use it to check reachability.
