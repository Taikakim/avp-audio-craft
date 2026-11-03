---
name: aavepyora-publish-target
description: Dreamhost SSH target for publishing full eval sets (audition pages + clips) online
metadata: 
  node_type: memory
  type: reference
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
---

Publish full eval sets (audition HTML + clip dirs — too big for the `riffer-evals` GitHub Pages repo) to Kim's Dreamhost shared host over SSH/rsync (port 22):

- **Host:** `iad1-shared-b8-25.dreamhost.com`  **User:** `dh_4txyt6`  **Port:** 22
- **File store:** `/home/dh_4txyt6/aavepyora.online/files`
- **Likely public URL:** `https://aavepyora.online/files/...` (confirm mapping on first upload)
- **Auth:** key-based via `~/.ssh/id_ed25519` (kim.ake@gmail.com). Authorize once with
  `ssh-copy-id -i ~/.ssh/id_ed25519.pub dh_4txyt6@...` (user runs it; don't handle the password).

Publish pattern (after key is authorized):
`rsync -avz -e ssh <local_audition_dir>/ dh_4txyt6@iad1-shared-b8-25.dreamhost.com:/home/dh_4txyt6/aavepyora.online/files/<set>/`

Publishing is outward-facing/public (may be cached/indexed) — confirm the exact set + dry-run (`rsync -n`) before the first push. Related: eval UIs built by [[sa3-fulllength-control-render]] tooling; small control-authority pages still go to the `riffer-evals` Pages repo.
