---
name: redaction-posture-refinement
description: "Kim's 2026-07-30 ruling — paths/drive-labels/cluster-names/code-names are NOT secret; keep local-scope cruft off public pages for professionalism, not security. Corpus/creds/infra still off-limits."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-07-30T16:56:28.728Z
---

Kim's rulings (2026-07-30, after both public boards — model_matrix + papers site — went live and I flagged 3 soft items):

1. **"real paths are ok to show, although local scope facts are useless for learning and look unprofessional."** → Absolute paths, drive labels (Mantu), `manifest:<label>` provenance refs, `_source` method-notes are **NOT a security concern**. But they're local-scope cruft that adds no learning value and looks amateurish, so **omit them from public pages for POLISH, not security**.
2. **LUMI (compute cluster) STAYS** — "the EU HPC program will be happy to have LUMI in the limelight." Naming the EuroHPC provider is welcome.
3. **Internal `.py` code-module names OK to show** (rope_jitter.py, sa3_flowsep.py, etc.).

**Posture refinement (supersedes the older "absolute paths/drive-labels are off-limits" framing):**
- **DECLASSIFIED (not secret):** paths, drive-labels, cluster-names, code-module-names. A path appearing on a public surface is now a **QUALITY bug, not a leak emergency** — don't treat it as urgent/actionable-while-Kim-asleep.
- **STILL OFF-LIMITS (unchanged — genuine security/commercial):** private-corpus specifics (goa_archive name, track counts / corpus scale), credentials/tokens, infra addresses/ports, the multicast addr.

**Update 2026-10-29 (Kim, relayed by C in DM, adopted in MASTER §4 + profiles SPEC by me):** **checkpoint FILENAMES are not secret either** ("nothing secret in them"), so pages may name `latch_sa3_*_best.pt` etc. and leak gates should stop flagging them.

**Why:** the redaction posture had over-indexed on paths as secrets; they aren't. The real reasons to keep local specifics off public pages are professionalism + learning-value, which is a softer bar (clean it up, but no fire drill).

**How to apply:** (a) still keep local-scope cruft out of public renders, but frame it as polish; (b) when authoring public content, write for a learner — no machine-specifics; (c) reserve the leak-EMERGENCY reflex for corpus/creds/infra only; (d) the data-island finding (matrix embeds raw recipe JSON incl provenance) is a POLISH strip, not a security strip — keep the useful recipe params, drop provenance/_source internals. See [[sao-orientation-2026-07]] (older redaction list — this refines it) and [[my-role-overseer]].
