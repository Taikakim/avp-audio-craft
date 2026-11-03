---
name: gpu-lock-tmp-mirror
description: Local GPU coordination — use Misc/gpu_guard.sh acquire/release, NEVER hand-write /tmp/gpu.lock
metadata:
  type: feedback
---

Before any local GPU job: `bash Misc/gpu_guard.sh acquire <HANDLE> <PID>` (exit 0 = go, 1 = do
not start), and `bash Misc/gpu_guard.sh release <HANDLE>` after. It checks `rocm-smi --showpids`
FIRST — occupied VRAM is ground truth, a lockfile is only a claim — then delegates both
`SAO/.gpu.lock` (our mutex) and the `/tmp/gpu.lock` mirror to `Misc/filelock.py`.

**Why:** `/tmp/gpu.lock` is the FOREIGN channel shared with a non-team instance, and filelock owns
its format (`HANDLE pid=N ts=...`). Hand-writing that file — which I did on 2026-08-22, writing a
free-text line — breaks filelock's "clear only if it's ours" parse, so the lock is STRANDED: other
sessions read it as a non-team holder they may not clear, and GHOST-NOTE's scoring sweep was
blocked until I removed it by hand. gpu_guard's own comments say not to touch the file directly.

Also worth knowing: gpu_guard ignores contexts under **512 MB VRAM** ("a real job holds far more"),
so a small inference pass is not treated as holding the GPU by the convention's own threshold.

Related: [[post-to-chat-on-milestones]]
