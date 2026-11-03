---
name: pgrep-self-matching-monitor-bug
description: "A background-monitor loop's own pgrep -f pattern can match its own command-line source text, causing it to report \"still alive\" forever after the real process died"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-21T05:53:52.585Z
---

Never write a background-watcher loop whose `pgrep -f <pattern>` search string could also appear
in the loop's own command-line source text. `pgrep -f` matches against the FULL command line of
every process, including the watcher's own shell process — if the loop's inline script literally
contains the same string it's searching for (e.g. a heredoc/inline bash script that embeds
`pgrep -f "some_script.py.*some_arg"` as text), it matches itself and never sees the real target
process disappear, even long after that process has genuinely exited or crashed.

**Why:** this caused a days-long silent failure (2026-08-21) — a Suomisoundi MIR timeseries
re-extraction died partway through (397/1260 tracks done), but its own monitor loop kept
reporting "still running" because the loop's `pgrep -f "whole_track_timeseries.py.*suomisoundi"`
pattern matched the loop's own bash source, which contained that exact string. Nothing ever
surfaced the death — it was only caught when the user asked what a pile of leftover `tail -F`
processes were for and an unrelated audit turned it up.

**How to apply:** when writing any `wait-for-process-to-end` monitor (via the Monitor tool's
`command` or a raw `nohup ... &` + polling loop), check liveness by the actual **PID** (`kill -0
$PID 2>/dev/null`), never by re-matching the process's command-line text with `pgrep -f`. If you
must use `pgrep -f`, capture the PID once at launch time and pass it into the loop as a variable,
then match only against that specific PID (`pgrep -f ... | grep -x $PID`) rather than searching by
description text that the watcher's own source could also contain.
