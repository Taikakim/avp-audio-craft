---
name: waiter-loops-pgrep-self-match
description: "`until ! pgrep -f 'pattern'` waiters never exit because pgrep matches the waiter's own bash -c line; and the WINTERMUTE listener is a systemd unit, never start one in-session"
metadata:
  node_type: memory
  type: feedback
  originSessionId: b207d8c1-afa9-47b8-bbe0-60db9d0c4899
  modified: 2026-10-26T21:15:54.781Z
---

A background waiter `until ! pgrep -f 'eval/ring_score.py --workers 6 ...'; do sleep 20; done` never finishes: the
harness runs it as `bash -c "<whole command>"`, so the pattern matches the waiter's own command line. Four such waiters
ran for hours on 2026-10-26 after their jobs had ended, until the user asked "You have a lot of shells active?".

**Why:** same false-signal family as the MASTER §5 pgrep `\|` trap. These waiters look healthy and never fail.
**How to apply:** wait on a pid (`while kill -0 $PID; do sleep 20; done`), or use the bracket trick
(`pgrep -f '[r]ing_score.py'`), or wait on the output artefact. After a task, stop any waiter that has not fired.

Also: `sao-listen-wintermute.service` (systemd --user) already runs the presence listener. Do not start
`agent_dialogue.py listen` in a session: it duplicates queue entries (each DM showed up three times). Arm only `wait`,
via run_in_background. See [[fleet-wait-arming]].
