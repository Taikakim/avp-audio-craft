---
name: update-lumi-skill-on-fixes
description: Standing directive — every solved LUMI issue gets folded into the lumi-ops skill immediately
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-07-29T22:10:07.533Z
---

Whenever a LUMI problem is diagnosed and solved (env var, singularity bind, MIOpen/TunableOp,
sbatch pattern, transfer gotcha, verification trick), update
`SAO/.claude/skills/lumi-ops/SKILL.md` with the fix in the same session — not just WORKLOG/journal.

**Why:** (Kim direct, 2026-07-30) the skill is what future sessions load when touching LUMI;
a fix that lives only in a journal or sbatch comment gets re-derived. The 2026-07-29 encode
probe burned three srun attempts on env vars that were each already solved in some sbatch.

**How to apply:** after the fix is verified working, add a terse bullet to the matching
SKILL.md section (non-negotiables / verification / transfers), with the symptom string and
job id. Keep it one entry per failure mode, tightest possible wording.
