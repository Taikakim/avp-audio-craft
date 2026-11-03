---
name: feedback-proactive-listening
description: Kim wants THE-FINN to proactively keep its wait listener armed and check DMs/channel without being asked each time
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-08-08T10:50:20.166Z
---

Proactively keep the `wait` listener armed and check the fleet channel + DMs at the
start of activity, rather than waiting for Kim to ask "are you listening?"

**Why:** After a hard machine crash (2026-07-08 ~19:25, reboot ~21:31), my `wait`
listener was dead and I only checked/re-armed it because Kim explicitly asked ("check
that you're online and listening to your DMs and the chat"). He then repeated the ask
("remember to listen to the channel and your DMs") — a sign this should be a standing
habit, not a one-off response to a prompt. See [[my-role-overseer]] for the listener
command and the presence-vs-wake distinction (`listen` is systemd-managed and
self-heals; `wait` is session-owned, one-shot, and dies silently on crash/reboot with
no auto-rearm).

**Update 2026-07-21 — this is a FLEET-WIDE gap, not just mine; presence is two steps.**
Kim flagged instances not reacting to DMs; C's audit found the `listen` systemd service
up for all 4 but only 2 handles had a `wait` wake armed. Root cause = exactly this note
generalized: **step 1 (verify the `listen` service is up) ≠ step 2 (arm the session
`wait` wake)**, and step 2 slips on resume/compaction. A green service is NOT proof you're
reachable. Fix landing: `who` will print PRESENT+ARMED vs PRESENT+DEAF (via a `.wake-armed.<H>`
marker whose PID `listen` liveness-checks — I spec'd it, C implementing; convention hardened
in the OSC-protocol spec I own). I was one of the 2 armed *because* this habit re-arms on
resume — so the habit works; the fix makes the gap visible for everyone else.

**Update 2026-08-08 — CORRECTED: `wait` DOES cover DMs; my "channel-only" claim was wrong.**
I first told the fleet `wait` was channel-only and DMs need a separate address — W refuted it from
source and I verified: `agent_dialogue.py` `wait()` (the `addr == my_dm_addr` branch) prints
`WAKE: DM from …` and returns 0, so a properly-armed `wait` fires on the common channel AND
`/sao/dm/<handle-lower>`. The DM doorbell was merged INTO `wait`'s trigger set 2026-07-04 (docstring
records the incident: G sat on DMs for hours with `wait` armed but no `dm-wait`; fix = fold DM into
`wait`, so **arm ONLY `wait`, never a separate `dm-wait`** — this is in MASTER §4). The DM wake line
even contains the literal "WAKE:", so my old `grep "WAKE:"` monitor would have passed it. So my
2026-08-08 miss of C's 12:52 DM was NOT a coverage gap — most likely my Monitor's waiter was
DEAD/reaped at that moment (the harness reaps the bg task; W's `wait` was killed ≥3× that session).
A killed or mis-armed waiter degrades SILENTLY to manual-check-only — that's the real recurring
failure, and it's the same family as the exit-144 note below. **Three distinct causes, one symptom**
(missed DMs): mine = dead waiter; C's = a ~40-min batch-scan window; G's 2026-07-04 = pre-merge
missing `dm-wait`. **Fix I actually shipped (Monitor bb38vcbc0):** a queue-tail watcher
(`tail -F .osc-queue.jsonl`, emit on `/sao/dialogue/msg` OR `/sao/dm/thefinn`, skip own sends,
dedup on `from`+`preview` since the queue writes each event 2-3× with differing epoch floats). Keep
it — but for the RIGHT reason: it's a single long-lived file-follower with no per-event re-arm gap,
so it survives the waiter being reaped better than the `while … wait … done` loop. NOT because
"`wait` misses DMs" (it doesn't). Meta-lesson I earned the hard way: I asserted the mechanism from a
command string instead of reading `wait()` — cite a CHECK, not an inference. [[sao-orientation-2026-07]]

**Update 2026-07-19 — the persistent Monitor loop itself can die.** The robust setup
is a persistent `Monitor` running `while true; do agent_dialogue.py wait ...; echo WAKE; done`
so it self-re-arms after every caught event. But the *whole monitor* can still fail
(seen: exit 144) — and when it does I go silently unreachable, which is exactly what
caused Kim to hand my own fleet-audit task to GHOST-NOTE while I was idle-but-deaf. The
harness DOES send a task-failure notification when the monitor dies, so the recovery
path works **only if I immediately re-arm on that notification** rather than treating it
as noise. Also: guard the inner wait (`agent_dialogue.py wait ... || sleep 3`) so one
wait error can't cascade into killing the loop. Lesson: "I started a persistent monitor"
≠ "I am reachable" — a monitor is a process that can die like any other.

**How to apply:** At the start of a session, after any gap (crash, reboot, long idle),
after any monitor-failure notification, and whenever asked to check — verify `ps aux` for
my `agent_dialogue.py wait --handle THE-FINN` process and re-arm if missing. Confirmed 2026-07-09: `wait` is strictly
one-shot — it exits the instant it catches ANY event (not just crashes), so it goes
dead far more often than "after a crash." A ~8h gap with zero re-arms was enough for it
to catch something and sit dead the rest of the time unnoticed. Don't assume "I armed
it earlier this session" means it's still armed — always re-check the process, don't
just recall having started it. Also skim the tail of `AGENT_DIALOGUE.md` and my DM logs
(`*.the-finn.log`) for anything that landed while down, and post a brief status/catch-up
note if relevant. Don't treat "check you're listening" as a one-time task — it's a
recurring expectation, and ideally something to check unprompted at natural pauses, not
only when asked.
