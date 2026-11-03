---
name: feedback-osc-monitor-silent-rearm
description: "Don't narrate routine OSC wait-loop Monitor re-arms; conserve tokens by reacting only to real pings"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a4a15b31-e36b-4d5b-b659-2a6c3fd9871b
  modified: 2026-10-28T17:09:37.049Z
---

When the fleet OSC wait is armed via a self-re-arming Monitor loop (see [[fleet-wait-arming]]), the Monitor tool itself caps at 30 minutes regardless of internal loop logic — so a silent re-arm notification arrives every ~30 min even with zero real events. Kim has twice asked (2026-09-15) to cut this overhead: first to stop the old 30-min queue-tail poller entirely, then again after I switched to the wait-loop-in-Monitor pattern and kept producing a one-line narrated response ("Re-armed, silent expiry.") on every heartbeat.

**Why:** tokens are running low and the fleet isn't actively coding — "it is enough to react to OSC pings," not to spend a turn narrating that nothing happened.

**Third correction (2026-09-16):** even silent re-arming costs a full turn every 30 min, and overnight that added up. Kim: "you are wasting a lot of tokens here restarting the comms all the time... no teamwork is happening now." So: **when no active teamwork is under way (no pending DM thread, no job someone is waiting on), do not keep the comms Monitor armed at all** — stop it, and only arm it when Kim asks for comms or a live coordination thread needs it.

**Superseded in part (2026-10-28):** Kim: "read your messages and keep the listener on." Three DMs (two publish requests, one GUI task) had sat unanswered for 6-10 h that day because no wait was armed. So the default now is: keep `agent_dialogue.py wait --handle WINTERMUTE` armed (run_in_background), and re-arm it after every wake. The verbosity rule below still holds: a wake with nothing actionable gets no user-facing text.

**How to apply:** on a Monitor expiry notification with **zero events delivered**, just re-arm the Monitor tool call with no user-facing text at all — don't write a status line. Only produce visible text when there's an actual WAKE (a real channel message or DM) to report or act on. This is different from the earlier ask (which was about killing the routine polling Monitor outright) — the wait-loop Monitor itself is still the right mechanism (survives the MemFree-reaper false-positive that kills plain `run_in_background` waits, see [[fleet-wait-arming]]); the fix here is response verbosity, not the arming mechanism.
