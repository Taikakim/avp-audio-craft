---
name: push-cadence-not-every-commit
description: Kim's commit/push cadence — commit often (task finished, parking, switching), push about weekly with other maintenance
metadata:
  type: feedback
---

Kim, 2026-09-10 (refining his earlier note that pushing everything immediately "will force us to
deal with possible overlapping edits"):

> "commit when a task is finished, or when parking stuff or changing to a new task. mainly, stuff
> that we spent time on and works should be in the repo. maybe we could do pushes once a week with
> other maintenance, but commit often."

**COMMIT — often, at three specific moments**, not just at "done":
1. a task is finished,
2. **parking** work (stopping mid-thing, budget out, blocked),
3. **switching to a new task**.
The test is *"we spent time on it and it works"* → it belongs in the repo. This is a lower bar
than "the deliverable is complete", and the parking/switching triggers are the ones easy to miss:
that is exactly when unpushed, uncommitted work gets lost to a compaction or a crash.

**PUSH — roughly weekly, batched with other maintenance.** Not per commit. The SAO tree is shared
by four instances on one branch, so a push is the moment overlapping edits must be reconciled;
doing that continuously spends time on a cadence nobody chose. Push also when Kim asks or when
work is being handed to another instance.

**Before any push:** `git fetch`, confirm `git log HEAD..origin/<branch>` is empty (fast-forward,
nothing clobbered), and state explicitly when the push carries OTHER instances' commits — Kim
authorised that on 2026-09-09 and it is in WORKLOG, but authorisation is per-push, not standing.

Related: [[git-push-policy]] (never push to Stability's remotes; SAO -> origin, stable-audio-3 ->
fork), and commit via `Misc/agent_commit.sh <HANDLE>` so authorship is not all "Kim".
