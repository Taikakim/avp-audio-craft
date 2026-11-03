---
name: pkill-orphaned-subprocess-children
description: "pkill -f on a batch-job orchestrator's argv pattern doesn't kill its subprocess.run() children, causing them to survive and stack across restarts"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
---

When stopping/restarting a background batch-job orchestrator (e.g.
`extract_timbral_hdb.py --mode tracks --jobs N`, which fans out via
`subprocess.run()` calls to `--single <item>` children from a ThreadPoolExecutor),
`pkill -f "<script> --mode tracks"` only matches the orchestrator's own argv — the
already-spawned `--single` children have a different cmdline (`--single <item>`, not
`--mode tracks`) and survive the kill. Relaunching then stacks a fresh batch of
workers on top of the orphaned old ones.

**Why:** subprocess.run() children inherit the parent's process group by default but
are NOT re-signaled just because the parent dies — pkill only signals PIDs whose
*own* cmdline matches the pattern, not descendants.

**Consequence (2026-07-10, SAO/GHOST-NOTE session):** a "downshift jobs 12→8" request
(to relieve RAM pressure during a co-resident GPU training run that had already OOM'd
once) used the narrow pkill pattern, silently leaving the old 12 workers alive under
the new 8 — 15-20 workers running simultaneously, RAM climbed to 73GB used with swap
FULLY exhausted (511/511Mi), and every new extraction item started failing ("partial,
missing all 3 features" — memory-allocation failures inside librosa/scipy swallowed as
per-feature warnings, not surfaced as errors). This was very likely a real contributing
cause of a co-resident training job's OOM crashes, not just unlucky timing.

**How to apply:** when stopping a background job you started with `nohup ... &`
+ `disown` that internally spawns subprocess.run() children (any resumable
batch-extraction/render pattern in this codebase — reanalyze_variants.py,
extract_timbral_hdb.py, similar future scripts), kill by the *script's basename*
alone (`pkill -f script_name.py`), not by a narrower flag-specific pattern — that
catches the orchestrator AND every spawned child regardless of their own argv.
After killing, verify with `ps aux | grep <script_name>` before relaunching, and
check `free -h` if the kill was RAM-motivated — don't trust that pkill's exit code
or a first grep miss means everything is actually gone.
