---
name: git-push-policy
description: NEVER push to upstream (origin = Stability-AI) on the SA3 repos — push only to the personal forks; explicit per-push
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a76bbe73-5250-4a70-accd-5324dfe52aa8
---

**Never push to upstream under any circumstances unless Kim very explicitly asks.**
Stated emphatically 2026-06-28.

**Why:** in both SA3 repos, the remote named `origin` is the **upstream Stability-AI**
repo, not Kim's. Kim's own remotes are the forks. A bare `git push` is dangerous because
some branches track `origin`.

Remote map (verify with `git remote -v` before any push):
- `stable-audio-3`: `origin` = github.com/Stability-AI/stable-audio-3 (UPSTREAM, never
  push) · `fork` = github.com/Taikakim/stable-audio-3 (Kim's — push here).
- `stable-audio-tools`: `origin` = Stability-AI/stable-audio-tools (UPSTREAM, never push) ·
  `avp` = github.com/Taikakim/audio-tools-avp (Kim's — push here). **Gotcha:** local `main`
  *tracks* `origin/main`, so a bare `git push` would hit upstream — always push explicitly.
- `SAO` (avp-audio-craft) and `mir`: `origin` = Kim's own Taikakim repos (these are not the
  Stability upstream).

**How to apply:** always `git push <fork-remote> <branch>` explicitly (e.g.
`git push fork latch-sa3-phase1`, `git push avp main`) — never a bare `git push`, never
`git push origin` on sa3/sat. Don't merge upstream `origin/main` (the Stability syncs:
package rename, PQMF/transforms) without an explicit ask either. Related: [[latch-sa3-phase1]].
