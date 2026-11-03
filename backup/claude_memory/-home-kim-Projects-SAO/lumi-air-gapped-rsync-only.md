---
name: lumi-air-gapped-rsync-only
description: "LUMI compute/login nodes have no internet -- never suggest git pull there; code syncs via rsync from Kim's local terminal only"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-08-16T09:08:22.047Z
---

LUMI compute/login nodes are air-gapped (no internet at all) — `git pull` (or any network
command) run inside a LUMI session fails outright. Code reaches LUMI only via `rsync` run from
Kim's **local** machine:

```
rsync -avR -e "ssh -i ~/.ssh/id_EFP" <relative-path> akekim@efp.lumi.csc.fi:/project/project_465003186/code/
```

(`-R` preserves the relative path structure so it lands at the right spot under `code/`; propose
a `-n` dry-run first.)

**Why:** Kim caught me telling him to `git pull` inside his LUMI session after adding a new
sbatch script — wasted a round-trip. This was already documented in
`.claude/skills/lumi-ops/SKILL.md` (the lumi-ops skill, §"Access model") but `CLAUDE.md` never
pointed to it, so I never surfaced it. Fixed by adding `.claude/skills/lumi-ops/SKILL.md` as a
read-first item in `CLAUDE.md` (commit `9e08f25`, 2026-08-16).

**How to apply:** Never suggest `git pull`/`git fetch`/any internet-dependent command inside a
LUMI session — the air-gap half of this memory is unchanged and permanent.

**⚠ UPDATED 2026-08-31 (Kim direct) — the access half is NO LONGER TRUE as originally written.**
Agents **may now run read-only `ssh` and PULL `rsync`** to LUMI themselves; the key is loaded in
the ssh-agent, so `-o BatchMode=yes` works with no passphrase prompt. Verified working
2026-09-02 (`ssh-keygen -lf ~/.ssh/id_EFP` fingerprint matches `ssh-add -l`; logged into
`uan18`). Two limits still hold:
- **Never WRITE to LUMI scratch**, and never prune anything there — a future allocation may need
  the resume state. Pushing code to LUMI is still Kim's command to run.
- **Multiplex one ssh for a bulk pull** (`ControlMaster=auto` + `ControlPath` + `ControlPersist`).
  A per-file reconnect tripped LUMI's throttle and produced `Permission denied (publickey)` with
  a perfectly valid key. Diagnostic: matching `ssh-keygen -lf` / `ssh-add -l` fingerprints mean
  throttling, not a dead key. See `Misc/pull_resume.sh` and the lumi-ops SKILL section
  "Bulk PULLS: multiplex ONE ssh".
