---
name: bash-sequencer-gotchas
description: "Two bash bugs that OOM'd the GPU + logged false success when sequencing render jobs (2026-07-21)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
---

Two bash gotchas that caused a real GPU OOM collision + a false "rc=0" on a crashed render
(caught by WINTERMUTE, 2026-07-21, avp 18-cell fill fired into a running ptm chain):

1. `pgrep -f "a\|b\|c"` NEVER matches — pgrep patterns are ERE, where `\|` is a literal, not
   alternation. A card-clear gate built on it exits instantly (false-fire). Use plain `|`, or
   separate `pgrep` calls OR'd in shell.
2. `echo "$(date): rc=$?"` always logs rc=0 — the `$(date)` command substitution runs first and
   clobbers `$?`. Capture `RC=$?` on its own line immediately after the command, then echo.

**Why:** both bugs are silent — the gate "works" (fires), the log "succeeds" (rc=0) — so a
crashed render ships. WINTERMUTE nearly shipped 0/18 cells as done.

**How to apply:** in any job-sequencing script: gate GPU work on measured free VRAM
(rocm-smi, >9GiB sustained over 3×30s polls) plus per-pattern pgrep; never trust an rc echoed
in the same line as command substitution; verify renders by counting outputs (manifest cells /
wavs), never by rc alone — same spirit as the [[sa3-onnx-amd-inference]] HQ exit-code trap.
