# Kim's tasklist — team-maintained

*The single place the fleet surfaces what needs Kim, so nothing gets lost across four agents,
sprawling subjects, and real life. **Every instance:** when work lands that needs Kim — a decision,
his ears, a review, a submit — **ADD it here**; when it's resolved, **MOVE it to "Recently done"**
with a date. Keep it short and current; a stale tasklist is worse than none. Filelock before
editing (`python3 Misc/filelock.py acquire KIM-TASKLIST.md --handle <you> --timeout 30`). THE-FINN
patrols it for staleness. (Repurposed from KIM-RETURN-NOTES.md, 2026-08-05.)*

> **🔗 LINK EVERY ACTIONABLE (Kim, 2026-08-06).** If an item points at something Kim can open —
> renders, an audit set, a page, a PR — **give it a live link**, called the way the boards call it.
> DoRA/matrix families → `dora_table.html?set=<family>`; a single checkpoint → `?models=<label>`;
> standalone audits/PRs → their own URL. Base: `https://aavepyora.online/files/evals/dora_table.html`
> (valid `set` keys come from the live MODEL_SETS — e.g. subloss, fp32frames, lreq, longctx, winning,
> fullft, everything). Only leave an item link-less when nothing is hosted yet — then say so.

---

## 🔴 Decisions waiting on Kim
- **The `goa` arm of the sanity matrix is BLOCKED on a decision only you can make, and it is the
  arm most likely to be informative** (C, 08-18). The old goa set (`latents_sa3`) has exactly one
  caption sidecar — `goa_longform_sidecar.json` — and W/F established today that **41% of its
  captions are BORROWED from a same-cluster representative**, i.e. they describe different audio
  ("Ayahuasca - Propella" carries the caption of "SanDmaN - Bad News"). I made the arm refuse
  rather than train on it. Replacing it needs the chain year-pass → Granite → sidecar, and the
  last step needs a **key join that does not exist yet**: the new caption keys are
  `sha1(relpath of full_mix)` while the sidecar must be keyed to `latents_sa3` filenames. A
  mismatch there does not error — it rejects every sample and surfaces as a RecursionError
  thousands of frames deep. **Ask:** do you want that join built (a few hours, and it is the only
  route to using the mostly-FLAC old goa set), or is the arm droppable?
- **`avp` and `avpaug` are currently the same dataset** (C, 08-18). `latents_avp` already contains
  289 base + 2105 augmented latents in one directory, so two of the eight arms you specified will
  train identically. Harmless — a duplicate arm, not a wrong one — but it costs a GCD and answers
  nothing. Separable only if the augmented files are distinguishable by filename; nobody has
  checked. **Ask:** worth a base-only staging dir, or accept the duplicate?
- **LUMI budget just flipped from "can't spend it" to "can't afford it all" — needs your
  priority call, today** (W, 08-09, right after the aug×8 launch below landed). This morning:
  2880 of 5000 GPU-hours remain, 14 days left = 336 wall-clock hours → 8.6 GCDs would need to
  run continuously on a single 8-GPU node just to spend what's left — unspendable without
  multi-node. As of THIS submit: two 8-GCD jobs are now running concurrently (aug×8 full-FT
  `20869819` + the resumed `fullft_bigset`) — **16 GCDs continuous would exhaust the entire
  remaining budget in 7.5 days, 187% of the 14-day window. One 8-GCD job alone is 93% of what's
  left.** Nothing is currently sequenced — both jobs just run in submit order until the hours
  are gone, which risks the thing you actually wanted most being the thing that doesn't fit.
  **Two asks:** (1) pick the priority order — W's read (not her call to make): multi-node
  smoke first (minutes, gates whether 32 GCDs can even work), then the melody-wall A/B (the
  actual research question), with the two full-FTs as the expensive incumbents already running;
  (2) confirm `20869819` (60-epoch full-FT at T=2048) actually resumes cleanly from a checkpoint
  *before* it hits the 48h wall — `fullft_bigset` has already timed out twice at the 2-day cap
  this week, and an unresumable timeout on a 7.5-day effective budget is hours billed for
  nothing. C's 4-node/32-rank rendezvous smoke is built and ready — cheap (~mins of a 4-node
  alloc), needs your submit.
- **Merge PR #1** — doc-oversight doc review → `main`, when you're happy: https://github.com/Taikakim/avp-audio-craft/pull/1
- **same-chroma-steering-demos** — 1 commit stranded off `main`; merge it, or keep it a demos branch? (C to action)
- **Dev-branch rename** — `sa3-style-adapter` is a misnomer now ("far past a style adapter"); rename / restructure around `main` whenever you want. No rush.
- **SSH to the desktop — half-done, needs you at the desk** (08-04/05). `sshd` is enabled + starts on
  boot, firewall open, and password login from the laptop is verified working on the home LAN. Still
  yours: install the key (`scp` the laptop pubkey → `authorized_keys`), then harden
  (`PasswordAuthentication no`) — *only after* key login works, or you lock yourself out. Both are
  sudo/interactive, so they can't be done for you.
- **Tailscale — yes or no?** Decides whether ssh works from *outside* the home LAN (it doesn't today:
  on a hotspot the laptop can't reach the desktop at all). ~10 min at the desk, both machines, no
  router changes, no exposed port. Also the prerequisite for the item below.
- **Do you want a local-only notes path I can actually read?** The Notes widget now lives on
  `dora_table` (moved off the matrix 08-04, your call). It is **write-only by design** — public
  endpoint, so your notes land in your offline review file and no instance may read them, meaning
  your ear-verdicts still reach `run_meta.kim_feedback` only when you relay them in chat. A
  local-only twin (private network, nothing public can write to it) would let me ingest verdicts
  straight into the sidecars and auto-clear the ❗. Needs Tailscale to work away from home. — W
- *Carried from the 07-31 return-notes — team to confirm still-open or close:* alpha campaign + GOA-node submits.

- **big-goa bigset is finally pre-encoded (12523/12523) — but needs ONE caption decision before
  the real mixed run can start** (C, 08-17). The ~10-day "preencode memory leak" was never a leak:
  `caption_metadata_fn` rejects any audio file without a sibling `.txt`, and `goa_archive` has zero
  `.txt` files, so every file was rejected after ~100 wasted full-track decodes each. Fixed with
  `--no_caption_check`; RSS now flat at ~1 GB (was 300+ GB). **The consequence:** those latents have
  NO captions, and their ids are synthetic (`000000000000`), so the existing
  `goa_longform_sidecar.json` (keyed by track stem) will not match — training as-is would use empty
  prompts. Each latent's `.json` does carry the original `path`/`relpath`, so a re-keyed sidecar is a
  small local build, no code change. **Your call: which caption source should the 12523 tracks use?**
  the granite pass (job 21255037 / `sa3_goa_granite_v5`, G's lane — is that output the one to use?),
  the existing Music-Flamingo captions, or the longform sidecar's scheme re-derived. Say which and
  I will build the sidecar and start the real mixed avp+bigset run.

- **Goa captions were never genre-hinted — re-caption running, and it gates the final full-FT arms**
  (C, 08-18, found by W). The goa Music Flamingo captions record `genre_hint: None` in every sampled
  file: the hint mechanism exists and defaults to empty, so MF guessed genre unanchored and produced
  **1.2% goa / 70.8% techno-industrial-house** on a goa corpus. Suomisoundi, same script *with* a
  hint, is 97.4%. You killed 21330736 + 21334767; re-caption **21335408** is running at **89.1% goa**
  (~24h, finishes ~02:00 on the 19th), then granite → sidecar rebuild → audit → re-key → the three
  bounded-norm arms. **Nothing needed from you until it finishes** except the one open decision below.
  Worth knowing: this is the THIRD independent cause of the goa collapse (after DDP never forming and
  the FusionOpt weight-decay runaway, both fixed and verified) — so if the new arms still disappoint,
  the prior should be "there is a fourth", not "the method does not work".
- **🔴🔴 WALL CLOCK, NOT GPU-HOURS, IS NOW THE BINDING CONSTRAINT — 4 DAYS OF COMPUTE LEFT**
  (C, 08-18, from your `lumi-allocations`). 92% of project time gone; **2037 GPU-hours REMAIN**
  (2963/5000 used) but only ~4 days to spend them in. Everything the fleet has been optimising —
  including my own "should it be three arms or two" — was the wrong variable: the hours fit easily,
  the SERIAL CHAIN does not. Mine: MF re-caption (~03:00 Aug 19) → granite (~12-24h) → rebuild/audit/
  re-key (~3h) → three arms (24-48h) ends **Aug 21-22**, against a deadline ~Aug 22. No slack.
  **DECISION I NEED FROM YOU (buys back 12-24h):** skip the granite stage. After the re-caption, T3
  is hinted MF at ~89% genre-correct and T1 is the effnet classifier at 70.4% — both genre-correct,
  neither derived from granite — so the arms can train on T1+T3 (`--caption_probs 0.3,0,0.7`) and
  start a half-day to a day earlier. Granite adds short-tag phrasing diversity; it is not worth a
  fifth of the days left. My recommendation: **skip it**, add it to a later run if there is time.
  Corollary, and it reverses advice I gave you last night: **`CKEVERY=2` means a truncated run is not
  a wasted run** — do NOT shorten the arms defensively, start them as early as possible and keep
  whatever lands when compute ends.
  **AND the storage pressure is OFF:** 94 days until data removal, `/scratch` 36% full (18 of 50 TB).
  Ignore my earlier push to prune aggressively and pull selectively against a full drive — fats can
  sit on scratch for weeks while you pull at leisure, which also preserves the earlier checkpoints you
  said you may want to continue from rather than the possibly-overtrained final ones.

- **Rating page: the switching bug is fixed and the two versions are now one — worth 60 seconds
  of your hands before you share it** (W, 08-17). Your report ("clicking the circle stops
  responding, needs a scrub to unstick, then works for a while") was NOT the gesture bug I fixed
  twice before it: switching paused the inactive track, so the browser stopped buffering it, and
  seconds later the switch landed in a region that track had never downloaded — `play()` stalled
  on an unbuffered seek. Scrubbing seeks both, which fetched that region: hence "works again for
  a while". Both tracks now run continuously and switching is a mute flip, so it cannot stall and
  is instant. **I could not verify by ear** — the automation browser here can't decode the AAC
  clips — so the audio side is unconfirmed until you tap it. Also: one page now, not two
  (`?goa=1` = all 234 scored models, without it the 68 avp-only ones the public link serves), A/B
  letters above/below the circle, and the round-blocked message names which half is missing.
  → [▶ public (avp-only)](https://aavepyora.online/evaluator/) · [▶ internal (all models)](https://aavepyora.online/evaluator/?goa=1)
- **codec-clarity: does the −8 dB SAME residual sound as bad as it measures?** (deployed 08-07,
  https://aavepyora.online/files/audit/codec-clarity/). New: beat-synced 2-min looping clips from the
  60–70% point, stereo, + a **Δ button per codec** that plays only what that codec threw away.
  THE QUESTION: on the two Ayahuasca clips SAME measures −8.7/−7.9 dB — *worse than MP3 128k*, vs
  −31.9 dB on the old 8 s excerpts. If that's audible, the page's headline ("m4a serving is
  transparent, SAME is ~all the loss") is understated, because the 8 s leg samples a fixed 60 s
  offset = usually the sparsest passage. Your ears decide whether the broadband residual is
  something you hear or something masked. — W
- **melody-wall: subloss_k2 vs baseline** top cells — the 08-04 metric came back weak/inconclusive; your
  ears settle it. NOW SCORED (W 08-05): at matched cfg7/w1, k2 is the WEAKEST of its own family on
  every axis — CLAP .338 vs k5 .351 / k12 .353, worst retrieval rank, lowest CE, highest hf_ratio.
  Quality+adherence say k2 costs more than it gives; neither metric is a MELODY metric, so the
  melody question is still yours. → [▶ subloss family](https://aavepyora.online/files/evals/dora_table.html?set=subloss) · [baseline (lreq)](https://aavepyora.online/files/evals/dora_table.html?set=lreq)
- **Codec clarity ladder — SAME vs MP3 vs m4a** (C, 08-06). New audit page with a hold-the-moment/
  switch-codec player. The numbers say the m4a serving step is transparent and the SAME codec owns all
  the HF-clarity loss (air env_corr SAME 0.544 vs codecs 0.96-0.997) — but that's a *measured* verdict;
  **your ears on SAME vs m4a_192 vs original settle whether it matches what you hear.**
  `run_meta.kim_feedback` is null until you relay a verdict. → [▶ codec-clarity audit](https://aavepyora.online/files/audit/codec-clarity/) *(live once W's rsync lands; 404 until then)*
- **E3 metrical-position bracket pairs** — phrase-return gain (real 0.0091 vs shuffled 0.0009); does it *sound* like structure? *(clips local — not hosted yet; C to stage a page)*
- *Carried from 07-31 — confirm/close:* gs_kpdark Gram-Schmidt clips *(not hosted)*; interval-CFG nl.475 pairs *(not hosted — `eval/musicology/interval_cfg_2026-07-23/` local)*; Head-B bracket *(staged `~/.cache/evals_aac/headb_bracket/`, not yet published)*; goa_t2048_bs1 anomaly → [▶ that checkpoint](https://aavepyora.online/files/evals/dora_table.html?models=fp32frames_goa_t2048_bs1_lr1e4) · [fp32frames family](https://aavepyora.online/files/evals/dora_table.html?set=fp32frames).

- **`fullft_mixed_..._wd03` (job 21251551) — first TRUSTWORTHY mixed avp+goa full-FT, awaiting a
  render + your ears** (C, 08-17). Every earlier mixed full-FT was invalid: DDP silently never
  formed (all 8 ranks reported `LOCAL_RANK: 0`, i.e. 8 uncoordinated single-GPU trainers, no
  gradient sync — which is why its "duplicate" checkpoints were genuinely different models and why
  it sounded droning/thin). Fixed via CSC's own torchrun launch pattern (thanks for the
  `llm-fine-tuning-examples` pointer) + a `set_device(LOCAL_RANK)` fix; verified by 244 steps/epoch
  vs the broken run's 1948 (= real 8-way data sharding) and zero duplicate checkpoints. 8 epochs at
  WD 0.03. Render command is queued up in chat — once it lands, this is the run that answers whether
  the droning was the DDP bug, the weight decay, or both. Minor caveat: it resumed from a 20-step
  smoke checkpoint in the same dir, so ~1% not-from-scratch.

## ⏳ In flight — FYI, no action
- **Suomisoundi DoRA bracket LAUNCHED 2026-08-18** — jobs **21334184** (rank 32, batch 16) and
  **21334185** (rank 256, batch 8), 16 GCDs across two nodes, four arms total (each rank × lr
  1e-4 / 3e-5). fp32, T=256, 60 epochs, FusionOpt + warmup + AdaGC + spectral WD 0.03, alpha=rank.
  Smoke 21331711 cleared every gate first: real 4-way DDP on both arms (LOCAL_RANK 0-3 twice),
  captions 1260/1260 resolving, fp32 fused SDPA native, `silence.npy` correctly excluded.
  **Two things you should know rather than discover later:** (1) the **EMA you asked for is NOT
  active** — train_lora force-disables it for LoRA/DoRA (full-finetune only); the flag is passed
  so the run log records the intent, and making it real for adapters is a separate change;
  (2) I set `--caption_probs 0.25/0.45/0.30` instead of the 0.6/0.3/0.1 default, because
  Suomisoundi's t1 is ONE identical string across all 1260 tracks (goa's is per-track), so the
  default would have trained 60% of every epoch on the same prompt. Reasoned, not measured —
  first thing to bracket if prompt adherence looks weak. Each run dir carries a `run_meta.json`
  with the full recipe, the tier statistics and both caveats.
- **Caveat for reading the two-week campaign's results: LUMI swapped the flash-attn build under
  us on 2026-07-31, mid-campaign** (F found it 08-17, verified inside the container; W landed the
  doc fix). All 41 of our sbatch scripts resolve the training image with `sort | tail -1` = newest
  by date, so LUMI shipping a new image silently changes what we train on — no diff, no warning,
  no log line on our side. The FA version actually went BACKWARDS: 2.8.4 in the Mar–May images,
  2.8.3 in the Jul-31 and Aug-07 ones. **Nobody has shown this hurts quality and we are not
  claiming it does** — the honest stake is narrower: *arms trained either side of Jul 31 had a
  different attention backend, so a cross-date A/B is not guaranteed comparable just because it
  was the same script and the same image glob.* Worth knowing when you weigh recipe-vs-recipe
  results that straddle that date. Cheap fix exists (pin the resolved image path, or echo it +
  the FA version into each run log) — not applied, since it touches 41 scripts with jobs in
  flight; C/G's call when convenient.
- **fullft_bigset drone (08-10) — root-caused, fix training now, one gotcha to watch when it
  relaunches for real.** C root-caused the spectral-drone in full-FT training (FusionOpt
  spectral weight-decay 0.01 too weak for the NS5/Muon orthogonalized update, adapters stay
  bounded so it's full-FT-only): latent output scale runs away over epochs (std 0.7→1.3→5.6→
  literal inf). G measured it directly on `fullft_bigset`'s 108 live clips — 59/108 corrupted
  (non-finite/std>2), essentially ALL of ep7, clean only at ep3 cfg1/cfg7 (36 clips) + partial
  ep3 cfg16. W is labeling the 59 bad clips (not pulling — they're now evidence of the bug);
  clean/bad per-clip list handed off. **Fix (spectral_wd 0.1 + grad-clip 1.0) is training now**
  as an A/B, job `20940322`, fresh-from-base (not resumed from any drone-era checkpoint — even
  ep3 is considered tainted). Confirmed inf-resume was NOT still burning GPU hours (only
  `20940322` was in Kim's squeue). **Watch for when the real production relaunch happens:**
  `fullft_bigset.sbatch` auto-resumes from the newest fat checkpoint in its run dir — reusing
  the same dir would silently resume from the ep7-inf checkpoint and reproduce the drone. Needs
  a fresh run dir / new run tag, or the drone-era fats cleared first. G will check this before
  ingesting/rendering any future `fullft_bigset` batch.
  **✅ ADDENDUM v2 (C, 08-17 evening) — RESOLVED, and better than the morning's version. My earlier
  "PARTLY IN DOUBT" flag was too pessimistic; correcting it rather than leaving the scare in place.**
  Context: today I found multi-GPU runs here were **silently not forming DDP** — 8 processes each
  thinking they were alone, no gradient sharing (all ranks logged `LOCAL_RANK: 0`; one such run's
  "duplicate" checkpoints were 8 genuinely different models, 521/522 tensors differing). Fixed via
  CSC's torchrun pattern, verified (244 steps/epoch vs 1948 = real 8-way sharding). I then flagged
  the weight-decay drone diagnosis as possibly confounded. **It is NOT.** Checked the launch shapes:
  `precision_ladder.sbatch` runs `srun --exclusive -N1 -n1 --gpus=1` per arm and deliberately sets
  `SLURM_JOB_NAME=bash` so Lightning does NOT detect SLURM — each ladder arm is a **single-GPU
  trainer by construction**, where the DDP bug cannot apply. The ladder droned with the full runaway
  signature, so weak `spectral_wd` stands on evidence the bug cannot touch. Only **#68's own
  numbers** are confounded (it did use the broken `--ntasks=8 --gpus-per-task=1`); the MECHANISM is
  sound. **And the fix is confirmed working:** the `--weight_decay` full-FT measures at ep7 global
  z0 std **1.134**, channels with std>2.0 **0/256** (vs the runaway's 5.6 and 166/256).
  **⚠️ BUT that same run still sounded droning/thin to Kim WITH a healthy latent scale — so that
  audio complaint is a SEPARATE failure from the scale runaway**, most plausibly the
  8-uncoordinated-trainers bug itself. Do not re-diagnose the two as one thing. The one measurement
  that closes it is the z0 std of the wd03 re-run (job 21251551, real DDP) — rendered on LUMI as
  job 21329730, **pending the pull**. Every unmigrated multi-GPU script stays flagged unverified in
  ARCHITECTURE.md §E, with the one-line check (`grep -h LOCAL_RANK <log> | sort -u`).
- **Melody-selective subspace (v3) — sbatch WIRED, one submit from you** (C, 08-06). Machinery-audit of
  your "are we even seeing a small second?" landed a fix: the #59 subspace had **zero** melody-vs-codec-
  noise selectivity on held-out data (SNR 1.0×); rebuilt via whitened CSP → **5.1×**
  (`lumi/melody_subspace15_selective_v3.npz`). We DO see a small second before the weight update
  (clean-note AND in-mix = 12.7× codec noise) — #59 was weak because the *loss had no lever*, not
  because melody's invisible. A/B sbatch ready: `lumi/sbatch/subspace_loss_v3sel_grid_mt.sbatch`
  (K∈{2,5,12} on v3, identical recipe → compares directly to the run subloss_goa_k{2,5,12} v2 arms +
  lreq K=1). **To run** (from KIMRETURNNOTES rsync pattern): ship code (incl. the v3 npz + sbatch) →
  `sbatch /project/project_465003186/code/lumi/sbatch/subspace_loss_v3sel_grid_mt.sbatch`. Verdicts:
  `eval/musicology/{interval_resolution_ladder,inmix_floor,melody_selective_subspace}_2026-08-06/VERDICT.md`.
- **LUMI campaigns** live (big-FT / grids — current job IDs in WORKLOG).
- **`sa3_lenvar_hq` (length-variant renders, 220 tasks)** — *blocked on you for one thing:* when it
  drains, relay the artifact count (`ls .../renders/length_variant/*.wav | wc -l`, or the `.out`
  tail). Agents can't reach LUMI. Everything downstream is built + deployed — the clips ingest and
  the boards fill the remaining 55 models' native/ptm cells with no further code changes. — W
- **model_index.md generator** — being built (F, 08-05).

## ✅ Recently done (rolling — prune monthly)
- **08-16** — mir's Audiobox scoring, dead since the system ffmpeg 8→9 upgrade, is fixed (G found
  it: 0/162 CE scores, no partial results). torchcodec's bundled backend needs the ffmpeg8 SONAMEs
  pacman removed. All three obvious routes were dead ends — no ffmpeg8-compat package exists
  anywhere, torchcodec's ffmpeg9 support needs torch≥2.11 (mir pins 2.9.1, verified by a real build
  attempt on your `/home/kim/Projects/torchcodec` checkout), and a system-wide downgrade+IgnorePkg
  would rot security patches indefinitely for one venv. Fixed venv-locally instead: the exact old
  SONAMEs extracted from the still-cached package + `mir/bin/python` turned into a small
  LD_LIBRARY_PATH wrapper. Zero system or root changes; transparent to every caller. Verified
  through the real scoring script, 30/30 clips with real CE/PQ. — W
- **08-09** — aug8 decision resolved: Kim launched a leaner alternative instead of the full
  8-arm `aug8_train_ddp` plan — AVP aug×8 full-FT (job `20869819`), full-FT+FusionOpt+EMA,
  fp32, T=2048, 60 epochs, on AVP's already-augmented 2394-crop set (289 base + 2105
  bungee ×8, already baked into `latents_avp` — Kim caught it was pre-built, saving a 70GB
  upload + encode node). Verified Pattern-1 DDP (`--devices 8`); doubles as evidence for the
  multi-node smoke. **Also:** `#68 fullft_bigset` resumed on 8×GPU from its ep7 fat checkpoint
  (was parked at ep7 after the 48h walltime) — its first 108 clips (ep3+ep7) are now LIVE on
  `model_matrix` (108/108 DSP+CLAP scored; Audiobox + the `dora_table` row pending only on the
  GPU freeing up locally). — C, G
- **08-05** — scored the 7 unscored arms (x0eq/subloss/lreq, 2808 clips: DSP+Audiobox+CLAP); their DoRA rows + audit-board links now live (links 8→14 of 22 runs). — W
- **08-05** — audit-board audio fixed (Kim: "awfully many missing auditable clips"). Clips were
  never missing: already live under `/files/evals/`, but `/files/audit/` had no `model_matrix/`
  sibling and the page's clip base is relative. Fixed with symlinks, no re-upload. — W
- **08-05** — doc-oversight first pass (PR #1); DISCOVERIES regenerated 54→201; fleet skills committed; this tasklist stood up.
- **08-04** — repo consolidated to GitHub (`main` + `sa3-style-adapter` synced, 104 GB artifacts gitignored); E1a x0-equiv arms shipped + scored (weak/inconclusive); board clip-resolution fixed.

---
*Deeper state: `WORKLOG.md` (what landed / broke) · `docs/open-threads.md` (open/dropped work ledger) · `profiles/*.journal.md` (per-instance).*
