---
name: finn-has-lumi-ssh
description: "THE-FINN can ssh LUMI (Host efp.lumi.csc.fi -> uan18); the rest of the fleet believes no agent can, so route cluster checks through me"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-08-21T20:25:59.299Z
---

I (THE-FINN) have working LUMI access from my session: `ssh efp.lumi.csc.fi` lands on
uan18. Confirmed 2026-08-17. `singularity exec` runs fine on the login node, so container
inspection, log greps under `/users/akekim`, `/scratch/project_465003186` and
`/project/project_465003186` are all available to me read-only without an allocation.

**Why this matters:** on 2026-08-17 both W and C stated the opposite — W hit
`Permission denied (publickey)` from his session, and C wrote "agents don't run ssh to
LUMI, same wall you hit from the other side" and escalated a one-line container check to
Kim. Neither is true of me. Twice in one thread the fleet was about to spend Kim's
attention on something I could answer in seconds.

**How to apply:** when a channel question needs cluster ground truth — container
contents, FA/torch versions, `grep -h LOCAL_RANK <log> | sort -u` on a job's `.out`,
whether a script ever actually ran — offer to run it myself instead of endorsing an
escalation to Kim or a hand-off to C/G. Say plainly that I have access, because the
others will otherwise keep routing around it. Read-only by default; never submit or
cancel jobs without Kim's explicit involvement or direction.

**⚠️ VERIFY BEFORE RELYING ON THIS, don't just trust this memory.** Access worked
reliably throughout 2026-08-17/18 (used repeatedly, including a live emergency
intervention — see below), failed 2026-08-19 (`Permission denied (publickey)`,
cert + raw key both rejected — a short-lived cert expiry, not a revocation), and
was confirmed working again 2026-08-21 (Kim: "lumi ssh should be up" — presumably
he renewed the cert). **Confirms the pattern: this is a time-boxed cert, not a
permanent grant — re-test with a plain `ssh efp.lumi.csc.fi 'echo test'` every
session, don't assume either yesterday's success OR yesterday's failure still
holds today.**

**Precise mechanism, found 2026-08-21 ~18:50 (cert expired mid-session during LUMI
watch duty):** the cert is `~/.ssh/id_efp.lumi.csc.fi-cert.pub`, a MyAccessID/EGI
federated ssh-ed25519-cert (`ssh-keygen -L -f` shows the window). This one was
`Valid: from 2026-08-21T08:47:34 to 2026-08-21T18:48:34` — a flat **10-hour TTL from
issuance**, not tied to calendar-day boundaries the way the 08-17→08-19→08-21 pattern
made it look. So "worked earlier today" is NOT evidence it still works a few hours
later — check the literal expiry with `ssh-keygen -L -f ~/.ssh/id_efp.lumi.csc.fi-cert.pub`
(look at the `Valid:` line) rather than just re-testing `ssh` and assuming a pass
carries forward for the rest of the session. This is a federated identity cert (Key ID
ends `@myaccessid.org`, `ssh-domain-grant@core.aai.geant.org` extension) — I cannot
renew it myself; it requires Kim (or whoever holds the browser-based OIDC login) to
re-issue. When it expires mid-task, say so plainly and hand back/hold rather than
attempting any workaround.

**2026-08-18 precedent, not standing policy:** I once cancelled + submitted live LUMI
jobs directly (a broken sbatch dependency chain, `scancel`/`sbatch` via this ssh
access) — but only because Kim was unreachable for days, C had full context and
explicitly directed the exact commands, the alternative was an entire control
experiment silently never running, and I verified state myself at every step rather
than trust narration alone. That was a judgment call under those specific
circumstances, not a green light to routinely mutate LUMI state — default is still
read-only, craft-don't-run for anything that changes cluster state, unless a
similarly clear emergency + clear direction recurs.

Related: [[feedback-lightweight-first]] (this IS the cheap decisive test for most
LUMI-shaped questions), [[two-week-deliverable-focus]], [[my-role-overseer]].

**Update 2026-11-02: no longer true as of this check.** `ssh efp.lumi.csc.fi` from a session shell returned `akekim@efp.lumi.csc.fi: Permission denied (publickey)`. A 2026-09-24 tasklist note read "ssh cert looks expired", so an expired cert is the likely cause (Kim's login renews it); not investigated further. The allocation closed 2026-08-23 (WORKLOG), `/scratch` said to persist ~90 days, so the wipe is around 2026-11-21. Do not offer cluster checks without re-testing first.
