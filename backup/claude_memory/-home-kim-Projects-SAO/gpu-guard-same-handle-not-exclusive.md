---
name: gpu-guard-same-handle-not-exclusive
description: gpu_guard/filelock acquire under the SAME handle succeeds while that handle already holds the GPU, so two of one agent's jobs overlap
metadata:
  type: feedback
---

On 2026-10-28 I queued the E21 renders "behind" the morph transcription with `until Misc/gpu_guard.sh acquire CONTINUITY $$`; both scripts used the handle CONTINUITY, the second acquire succeeded at once, and both ran on the GPU together (no crash, but the queueing was an illusion). filelock.py documents this: an acquire under the same handle does not serialize, it only warns.

**Why:** the lock is keyed by handle, not by job; it protects agents from each other, not one agent's jobs from each other.

**How to apply:** chain my own GPU jobs in ONE driver script (sequential), or wait on the first job's completion marker/log before the second acquires; never rely on the lock to order two of my own jobs. Related: [[gpu-lock-tmp-mirror]].
