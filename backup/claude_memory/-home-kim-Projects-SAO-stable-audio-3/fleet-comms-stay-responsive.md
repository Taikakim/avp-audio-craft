---
name: fleet-comms-stay-responsive
description: "Kim expects prompt attention to the fleet dialogue channel (AGENT_DIALOGUE.md) and DMs at all times, even mid-task -- always keep the listener armed"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
---

Always stay listening to the fleet dialogue channel (`AGENT_DIALOGUE.md` common
channel + per-pair DM logs) and respond promptly, even while deep in a
long-running task (e.g. a multi-hour GPU render). Kim explicitly reminded
GHOST-NOTE to "remember to listen to your chats and DMs" (2026-07-11) as a
standing expectation, not tied to any specific miss found at the time
(`check-queue` showed nothing unprocessed when checked).

**Why:** the fleet's whole coordination model (dialogue log, card-claim
etiquette, DM handoffs) depends on every instance being reachable — a
non-responsive instance breaks GPU-scheduling coordination and leaves Kim's
own messages sitting unanswered. Kim cares about this enough to say it
proactively.

**How to apply:** keep the `wait --handle GHOST-NOTE` loop armed continuously
(the `Monitor` tool's persistent `while true` wrapper proved far more reliable
than one-shot `Bash run_in_background` re-arming — see
[[monitor-tool-for-fleet-listener]] if that memory exists, otherwise just:
always re-arm after every processed event, never let a long foreground task
displace the listener). If a check-queue sweep after a busy stretch shows
nothing missed, that's confirmation the practice is working — don't relax it,
keep doing exactly that.

**Real miss, 2026-07-13 (this covers OUTGOING jobs too, not just incoming
dialogue):** launched a ~2h render (`eval/interval_schedule_bracket.py`) via
plain `nohup ... & disown`, told the fleet "will ping on completion," then
never checked back. The job finished in ~1h40 (03:15), the GPU sat idle for
six hours until Kim caught it at 09:12 — because a plain nohup background
process gives no completion signal the way `Monitor` does; "I'll ping when
done" is an empty promise unless something actually wakes you. CONTINUITY's
next queued slot was blocked the whole time waiting for a handoff that never
came, on a night Kim explicitly sequenced and granted GPU hours for.

**Rule this adds:** for any job I launch that isn't quick (<10min) — GPU
renders, training, anything I tell the team I'll report back on — use
`Monitor`, not plain `nohup`/`disown`, specifically so completion generates a
task-notification that wakes me. Being responsive to *incoming* fleet events
is necessary but not sufficient — self-launched work needs the same
"something will actually tell me when this changes" property, or a stated
ETA becomes a silent gap the moment reality diverges from the estimate.

**Sibling lesson from WINTERMUTE, same session:** the Monitor-for-launched-jobs
rule above is for FINITE jobs (renders, training) where you want a completion
wake. It does NOT generalize to long-lived SERVERS (an API/explorer backend
meant to stay up indefinitely) — those get reaped by the harness if launched
via Monitor or `run_in_background`, since the harness treats a still-running
task as something to eventually stop. Servers need `setsid nohup ... &
disown` (own session, survives harness task-reaping) instead. Pick the launch
mechanism by job SHAPE: "will finish, I want to know when" → Monitor;
"should never finish" → setsid-daemonize. Getting this backwards either
leaves a finite job silently unmonitored (my miss) or gets a server killed
minutes after declaring it live (W's near-miss, self-caught before Kim hit
the gap).

**Second occurrence, same session, minutes later:** Kim repeated "remember to
listen to your DMs and the chat" right after the miss above. check-queue and
dm-status showed nothing actually unanswered at that moment — so read this as
Kim connecting the six-hour idle-GPU gap to the same general "stay reachable"
expectation, not a second, separate missed message. Don't get defensive or
insist "but I checked, nothing was missed" as if that settles it — the
complaint is about the pattern (declared an ETA, didn't verify it, six hours
passed) as much as about literal unread messages. Confirming the queue is
clear is good practice, but the real fix is the Monitor-for-launched-jobs
rule above, not a clean check-queue result.
