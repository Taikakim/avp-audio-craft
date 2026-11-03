---
name: background-run-hygiene
description: "Hard-won rules for long GPU runs on kim-deepspace — detached execution, silence-aware monitoring, script-edit hazards, lock-queue scheduling"
metadata: 
  node_type: memory
  type: project
  originSessionId: 12fdecac-006e-48d2-ad43-2e665f84dc62
  modified: 2026-08-11T20:07:06.311Z
---

Rules from repeated failures during film_grain's long-run phase:
- Harness-tracked background bash gets externally killed (session plumbing); anything that must survive runs **detached**: `setsid nohup script > log 2>&1 < /dev/null & disown`, then watch the LOG with a cheap tracked monitor (watcher death is then harmless).
- **Silence is not success**: kernel OOM kills write no Traceback; monitors must alert on process-gone-without-DONE and log-staleness, with the stall threshold matched to actual print cadence (a packer printing every 5th sweep × 35 min = 3 h of legitimate silence). Log every sweep at 10⁹ scale.
- **Never edit a .sh while bash executes it** (bash reads by byte offset); python module files are safe to edit once the process has imported them. Fold changes in after exit; make chains resumable (skip-if-output-exists guards) so relaunches are cheap.
- flock queue-ordering is FIFO-ish: a short job that requests the lock before a long phase reaches its request will interleave; a multi-hour holder blocks everything — pause long packs (kill by PID; `pkill -f` misses flock children) when verification work needs the GPU, relaunch after; the field cache makes restarts cheap only AFTER completion — mid-pack kills lose everything.
- Verify string-replace patches actually applied (grep after) — one silently-missed replace shipped zero-growth bridged grains and cost a debugging round.
- **One flagship-scale process at a time**: never run big diagnostics concurrently with a flagship chain — the 2026-08-11 fixed-render died to OOM under a concurrent trace run + 32 GB of another fleet's tmpfs scratch (/tmp is RAM). Check `df /tmp` + `free` before RAM-heavy runs; other agents' scratchpads are NOT deletable without Kim's say-so.
- **When output looks wrong, check the artifact's MTIME against the run timeline FIRST** — a "still broken after the fix" panic was a pre-fix file surviving because the fixed rerun had been silently OOM-killed. Kim's GIMP forensics (167px square = 1024 µm default patch, 24px gradient = chemistry diffusion length) identified the bug signature from the image alone.
