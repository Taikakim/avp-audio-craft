---
name: lumi-eval-excludes-mir
description: LUMI post-training auto-clip generation must NOT include the MIR feature-extraction stage (too fragile to stand up on LUMI); MIR scoring runs locally/separately. Deployed eval clips need a latent-sanity gate.
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-08-12T07:24:49.506Z
---

Two standing constraints on the eval pipeline (Kim, 2026-08-12):

**1. LUMI auto-eval renders clips but does NOT run MIR.** The "models trained create their own clips afterwards in the same batch" step (LUMI post-training auto-eval) must **not** include the MIR feature-extraction stage. MIR is too fragile to stand up on LUMI and Kim won't spend the ~2 days to get its env working there. So: LUMI job = render only; **MIR scoring/metering runs locally/separately** where mir's env actually works (see [[my-role-overseer]] fleet lanes; mir project owns the extractor). Never add a MIR dependency to a LUMI job.

**Why:** mir needs essentia/madmom + a specific ROCm/interpreter setup that degrades silently to librosa otherwise; replicating it on LUMI is a multi-day yak-shave for a stage that runs fine on the local box. Keeps the LUMI allocation spent on GPU render, not env-wrangling.

**2. Deployed eval clips have a latent-sanity gate (ALREADY LIVE, W, commit 1d9a491).** `score_and_publish` runs a latent-sanity leg second, right after ingest, using C's z0-std diagnostic (non-finite OR global std > 2.0). It HALTS the run (nothing metered/published, per-clip verdict sidecar written), exceeding Kim's "at least flag me" bar. `--skip-sanity` overrides and reports "nothing was checked", not a bare OK. **Why:** the fullft_bigset drone case — the prior 4/4 green gates passed on latent-runaway-corrupted audio because every step verifies its own artifact and **none checked whether the audio is sane** (59/108 corrupt but scored+deployed).

**Gate-design lesson (W, 2026-08-12, commit d98a6ba) — the deepest form of the theme:** a gate must distinguish **"I could not look" from "I looked and it was bad."** The sanity gate reads z0.npy from Mantu; with Mantu offline (see below) its fail-closed branch would have BLOCKED every publish for the whole window — planned maintenance costumed as a safety property. Fix: ROOTS UNREACHABLE (drive unmounted) → PASS with a loud "sanity NOT CHECKED, infra state not evidence, re-run when drive is back"; ROOTS PRESENT but no z0 → still FAIL (there the absence IS evidence). Yesterday the same root cost a silent PASS on corrupt audio; today it would have cost a silent BLOCK on good audio — mirrored symptom, same root. Same family as [[feedback-pipeline-exit-code-trap]] "print statements are not evidence". **Follow-up owed:** any clips published DURING the Mantu-offline window carry an UNCHECKED sanity verdict → re-run the gate on them once Mantu is back (treat "published during Mantu window" as a state needing a follow-up pass, not a completed audit).

**Not memory-worthy but live 2026-08-12:** Mantu drive going offline for a while (Kim pulling DAW project files for CONTINUITY → clean stem/structure ground-truth for the melody/movement control targets) — don't launch Mantu-dependent work in that window; Lehto latents unaffected. Hall-of-Fame idea dropped (most models usable lately except drone-collapsed; Kim makes his own favourites tracklist).
