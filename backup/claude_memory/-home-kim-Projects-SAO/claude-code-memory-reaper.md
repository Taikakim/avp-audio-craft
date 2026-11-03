---
name: claude-code-memory-reaper
description: "running low on memory" kills of background tasks come from Claude Code's own reaper, not baloo/OS OOM — long run_in_background jobs die on this box
metadata:
  type: project
---

On Kim's desktop, `run_in_background` tasks get killed with "stopped because the system is running low on memory" while MemAvailable is ~85 GB. Verified 2026-09-15: no kernel OOM, systemd-oomd/earlyoom inactive, the systemd listener (`sao-listen-continuity`) survived untouched — only harness-spawned tasks die. Kim's read: Claude Code's reaper looks at MemFree, not counting page cache. Baloo (16 GB RSS) was blamed earlier but only lowers the numbers; it kills nothing.

**Why:** renders/waits/wake listeners launched as background tasks can silently vanish.
**How to apply:** don't loop re-arming a killed `wait`; for anything long, prefer a systemd --user unit or nohup/setsid outside the harness, and verify output files rather than task status. Kernel-side mitigation (root, Kim's call): raise `vm.min_free_kbytes` so the kernel keeps more memory free. Related: [[bash-sequencer-gotchas]].
