---
name: gpu-lockfile-convention
description: "Machine-wide GPU lock — flock /tmp/gpu.lock around all GPU-heavy runs; user's other agent swarms follow it too"
metadata: 
  node_type: memory
  type: project
  originSessionId: 12fdecac-006e-48d2-ad43-2e665f84dc62
  modified: 2026-08-07T10:06:50.897Z
---

On kim-deepspace (single 16 GB ROCm GPU shared by multiple agent instances), all GPU-heavy work must hold an exclusive `flock` on `/tmp/gpu.lock` for the duration of GPU use, so jobs queue instead of colliding/OOMing each other mid-run. Kim reported this as a global rule to their other agent swarms (working on unrelated projects) on 2026-08-07.

**Why:** an unrelated instance grabbed the GPU during a film_grain render window; the idle-gate pattern only protects run *start*, not mid-flight.

**How to apply:** wrap every GPU-touching command: `flock /tmp/gpu.lock <cmd>` or use `film_grain/renders/with_gpu_lock.sh <cmd>`. Keep the pre-run idle gate too (checks GPU%, VRAM, loadavg for 10 quiet minutes) — the lock handles agents that follow the rule, the gate handles anything that doesn't. Never edit a queue/chain .sh file while bash is executing it (bash reads incrementally); fold changes in after the run exits.
