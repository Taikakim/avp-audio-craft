---
name: lumi-pull-discipline
description: "Before pulling data from LUMI, check what's already local and whether a pull is already in flight"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-08-21T11:36:26.154Z
---

Before pulling anything from LUMI (rsync/scp of checkpoints, latents, renders, etc.), check two things first: (1) whether the data already exists locally (don't re-pull what's already here), and (2) whether a pull is already underway (`ps aux | grep -i rsync`) — don't start a competing/duplicate transfer against the same remote path.

**Why:** Kim (2026-08-21) flagged this after I was mid-LUMI-watch-duty without having checked for his own concurrent pull — he had an rsync actively running (`.weights.ckpt` slims from `/scratch/project_465003186/runs/` to `/run/media/kim/Mantu/lumi_runs/runs/runs/`) that I hadn't noticed. Redundant pulls waste LUMI-side I/O (already a scarce/contended resource this session — see the FLASH contention finding during [[finn-has-lumi-ssh]]'s B9 saga) and local bandwidth, and can race/corrupt a partial transfer if two processes write the same destination.

**How to apply:** Any time I'm about to `rsync`/`scp` FROM LUMI (not just uploading scripts/configs TO LUMI, which is low-risk and routine), first run a quick `ps aux | grep -iE "rsync|scp"` check and a quick existence check on the destination. If a relevant pull is already running, wait for it or coordinate rather than duplicating it.
