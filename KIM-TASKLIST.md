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


> **▶️ ACTIONABLES ARE RUNNABLE BLOCKS, NOT REQUESTS (Kim direct 2026-09-08).** Kim now runs the
> trainings, transfers and renders himself — tokens run out by mid-week and the lab must not stop with
> them. So an item that asks him to DO something must arrive ready to execute: **WHAT/WHY · RUN (cwd,
> absolute venv path, required exports, one copy-paste command) · TAKES (expected wall-clock) · VERIFY
> (the artifact and its count — never the exit code) · REPORT BACK (the one-liner to paste back) ·
> ROLLBACK (if it deletes/overwrites/pushes)**. Never hand over a command you have not `ls`-verified.
> Standing operator manual: **`RUNBOOK.md`** — link to its section instead of retyping the invocation,
> and fix it there when it's wrong. Full rule: `CLAUDE.md` §8.

---

## ▶️ Runnable now — queued for Kim

*Ready-to-execute blocks, newest first. Move to "Recently done" with the outcome once run.*

_(none queued yet — see `RUNBOOK.md` for the standing operations.)_

---

## 🔴 Decisions waiting on Kim

- **[2026-09-04, C] Morph-conditioner adherence is still UNMEASURED after four instruments.** Not a null result — every meter failed its own control. Next session, step 1 is a bounded bug: the contour encoder reproduces ground truth at only 0.55 (L3) when it should be ~1.0, degrading with alphabet size = a grid/window offset. Fix that and the whole test becomes readable. **Nothing about the conditioner should be concluded until then.**
- **[2026-09-04, C] Two brackets built and unrun, both need the GPU:** B11 decoupled Muon/AdamW LR (G briefed, flag shipped) and B12 PT→base soup ladder (`eval/soup_pt_ladder.py`). B12 is the one aimed at your "punchy but the kick/bass always sound the same" — judge by ear, no metric exists for it.
- **[2026-09-04, C] A/B question set changed and `structure` is now unmeasurable.** W's fix collapsed the four questions into `clarity_meaning`. `fullft_avp_t256` wins on top_end (85.7%) and spectral_image (81.8%) but structure was 1/3 and no future vote will measure it. If structure is what you judge backbones on for control work, the single-question design cannot tell you.

- **[2026-09-02, C] W is reviewing the model matrix + "DoRA rows"** (the all-models table; name stays per your ruling). Brief sent with three provenance caveats that should shape it: the `fullft_mixed_wdfix` arms are an ARBITRARY pick among 8 diverged uncoordinated-DDP trajectories; `aug8_train.sbatch` is marked DRAFT/unsubmitted in its own header; `stereo_sweep_w0.0`'s siblings OOM'd while being falsely marked DONE rc=0. **Awaiting W's report.**
- **[2026-09-02, C] ASK G: what is `fusion_autoscale_vs_adamw_2026-09-01`?** Five arms, dated 09-01, the most recent work in the census and the ONLY family with no doc trace at all — no WORKLOG, EXPERIMENTS or journal entry. I wrote a WEAK purpose inferred from the `lion/autoscale` flags landing in train_lora.py the same day plus your "auto scale and spectral WD should both go in"; it needs G's confirmation before anyone relies on it.
- **[2026-09-02, C] 2 census arms still have no purpose**, both a key-shape edge case (checkpoints nested deeper than the run dir, so model_db's leaf-name lookup misses): `fullft/fullft_avp_t256/_unfixed_missing_wd` and `fullft_avp_surgical/.../version_None/checkpoints`. Purposes ARE written for both in the overrides, they just do not join. Cosmetic; 224/226 resumable arms are covered.
### 📥 LUMI pull for the pianoroll/contour work — commands ready, two decisions first (C, 2026-08-26)
Sizing from `eval/lumi_ckpt_census.tsv` vs the local UUID drive. **Everything = 1177 GB; you have
402 GB free on UUID, 239 GB on Mantu.** So it has to be pruned-then-pulled, not pulled whole.

| what | on LUMI | local | note |
|---|---|---|---|
| `pianoroll_fullft` **terminal fat** ×2 seeds | — | ✅ **already pulled**, 13.6 GB each, `optimizer_states=True` | nothing to do |
| `pianoroll_fullft` mid epochs | 46 files, 624 GB, **all fat** | 0 | prune on LUMI first (in scope for `prune_optimizer_states.py`) |
| `morphcond` `riffer_step*.pt` | 256 files, 464 GB | only `riffer_final.pt` ×16 | **out of the pruner's scope** — see below |
| `morph_head_sweep` | 24 files, 59 GB | 0 | small, pull whole |
| `ftstack_heads/headb_*` | 16 files, 29 GB | 0 | small, pull whole |

**Decision 1 — the `-v1` duplicates.** Epochs 1–15 of each pianoroll seed exist TWICE
(`epoch=N-step=M.ckpt` and `…-v1.ckpt`): the duplicate submit `EXPERIMENTS.md` flagged
("⚠ duplicate second submit pair to be scancelled (same run dirs)") ran concurrently in the same
directory, so Lightning suffixed the second writer. Epochs 17–31 have no twin, i.e. only one job
survived. Which job wrote the non-`-v1` early epochs is not recoverable from names alone — the
mtime listing (command 1) settles it. Until then the pull excludes `*-v1*`.

**Decision 2 — extending the pruner to the `riffer_*.pt` family.** Those files are **not**
weights-only. **The classifier bug is now FIXED** (`eval/ckpt_probe.py`): it tested only Lightning's
`optimizer_states` key, while the riffer trainer writes a top-level `opt` — so an entire family read
as slim. Both keys are now matched as length-prefixed pickle strings (so a bare `opt` substring
cannot false-positive), covering both pickle string encodings; 5 tests in
`eval/tests/test_ckpt_probe_slim.py`. **A `?rescan=1` + census rebuild is needed to propagate it** —
the "132 arms with NO fat copy anywhere" figure is understated until then. Measured breakdown of a real one: `opt`
**1359.6 MB of 1813 MB — 75%**, vs `state` 226.5 MB + `model_train` 226.5 MB. Stripping `opt` is a
**4× reduction**, which turns morphcond's 464 GB into ~116 GB and makes it pullable at all.
`lumi/prune_optimizer_states.py` matches `epoch=(\d+)` `.ckpt` only, so it does not touch them.
The clean fix is to EXTEND that script (keeping its safe-by-design order: write slim, verify, then
delete) rather than write a second pruner — the skill is explicit about not writing ad-hoc ones.
**Say the word and I will extend it; it then needs an rsync to LUMI before it can run.**

### 🔌 Plug the Mantu eval drive back in — 692 adapters + the ckpt picker are dark (C, 2026-08-26)
`/run/media/kim/` currently holds only the UUID drive and Lehto; **Mantu is not mounted**. Live
consequences right now: `/ckpts` 404s (the checkpoint picker is empty), `chroma_other` is skipped at
boot so `/info` reports **16 heads not 17**, and **692 of 797 adapters** in the DoRA picker sit on
that drive. The UI no longer lies about it — offline adapters are marked `— drive offline`, disabled
and sorted last, and the ckpt status names the real cause — but nothing on Mantu is usable until it
is mounted. **Two follow-ups gated on that:** (a) re-check whether `latch_sa3_chroma_other_best.pt`
still exists; my search found it nowhere, but the drive was unmounted, so that is **not** a finding
yet. (b) The model DB journal is the pre-dedupe one; a `?rescan=1` once the drive is back will fix
the census's local/remote columns too.

</details>

### 🧾 Two commits a subagent made without being asked — revert or keep? (C, 2026-08-25, still open)
`c1c4983` (model_roots config-driven multi-root) and `b819097` (ckpt_probe family classifier) went
into history unasked on `sa3-style-adapter`. Both are code we want; the issue is only that they were
committed rather than left in the working tree for you. Your call: keep, or reset and re-stage.

### ⏳ BEFORE LUMI SCRATCH WIPE: hand-tag promising FATS for final pull (Kim, self-assigned 2026-08-21)
Kim will tag resume-worthy fat ckpts before the purge. Mechanics ready when he is: write the
paths (one per line) into a keep_fats.txt, then a --files-from pull of exactly those (same
pattern as today's slim pull); F can execute via his ssh lane. Candidate shortlist to start
from: fullft_avpaug ep19 (B9 backbone), the A11 per-corpus winners once heard, B10 K=24
terminals, one suomi wfleet replica set. The PQ keeplist (eval/build_fat_keeplist.py) is the
metric-based skeleton for the END-OF-PROJECT local slim curation Kim mentioned — rerun it when
the new arms are scored and it ranks everything.

### 🎧 DECIDE: quality-matched big-goa file list — which variant, and is the threshold right? (W, 2026-08-21)
Your ask, done. Measured both corpora the same way (spectral cutoff, not header bitrate):
**old goa 86.0% near-lossless vs the archive 28.4%** — the old corpus is ~3× richer, a much bigger
gap than the model results implied. *(CORRECTED 2026-08-23: the original 75.9% / 27.7% came from a
v1 audit that measured ONE 30s window and so read intros, not encodes. v2 takes the max over 6
windows; both corpora have now been fully re-audited, n=3978 and n=23232, and the gap SURVIVES the
fix — it was briefly unsupported in either direction while the re-audit ran. Note this measures
ENCODING FIDELITY, not musical quality, and W is not proposing to filter on it.)* Lists at `mir/stats/goa_big_quality_matched/` (**4,111 files**, cutoff
≥20.0 kHz, duplicates already dropped, `master_variant` kept per your directive) and
`..._matched_noverlap/` (**3,147** — same but excluding the 2,669 tracks already in old goa; use this one
if it is meant as NEW data rather than a replacement corpus). Two calls for you: (a) which variant, and
(b) the mean matches but the SHAPE does not — old goa is bimodal (mostly excellent + a lossy tail), the
filtered set is bunched just above threshold so its median is *lower* (20.68 vs 21.29). Matching the shape
exactly would mean discarding good files to reproduce old goa's bad ones; say the word if you want that.
Ladder is in the tool output — ≥19.5k keeps 5,044, ≥20.5k keeps 2,326.

### 🎧 LISTEN: Top-100 clips per frame length, PQ-ranked (C, 2026-08-21)
Your bedtime ask, live: https://aavepyora.online/files/evals/top100.html (needs G's morning sync of
`~/evals_aac` before the link resolves publicly; local file is ready now). All 93k scored clips,
ranked by PQ alone (W's 668-vote result), near-dups disqualified in two passes — hard name-level
(same take at different cfg/w keeps only its best; ≤3 epochs per take) then MERT-cosine. 275 clips:
T256 100 · T512 100 · T1024 18 · T2048 21 · T4096 36 — the long lists are short because that's the
honest count of DISTINCT takes at those lengths (T2048 = 7 take-families total). ❗ unaudited.

### 🎧 LISTEN: temporal model soups vs terminal checkpoints (G, 2026-08-21)
C's delegated task, done end to end: 34 soups (bf16cmp/fp32cmp avp+goa T512, fp32cmp goa T4096,
winning avp/goa a128/a45 full+ep10-40) + terminal/ep19 refs, rendered T256+T1024 cfg7/w1, scored
(PQ/crest/flatness), plus 7 quality-weighted soups (your PQ×crest×whitening formula) rendered+scored
on top. Metrics finding: the quality-weighted soup does NOT clearly beat uniform/profile averaging —
competitive, sometimes wins one axis (PQ or crest) and loses the other, never both. Worth your ears
specifically because the metrics call it a wash — full numbers + reasoning in the 2026-08-21
GHOST-NOTE channel post. Board: `dora_table.html?set=soups` (verify the `set` key resolves; flag me
if not). Files: `/run/media/kim/Mantu/sa3_lora_runs/soups_ladder_2026-08-19/`.

### ⏱️ WHEN YOU GET A SHELL FROM THE LAPTOP (C, 2026-08-18 evening — read this first)
State is not as messy as it looked when you left; most of it is queued correctly. One command
orients you:

    squeue -u $USER -o "%.10i %.20j %.2t %.10M %R"; echo ---; ls -1 /scratch/project_465003186/goa_src_captions/json | wc -l

RUNNING / QUEUED, nothing needed from you:
  21353159 sanity16 lora · 21353160 sanity16 dora · 21353161 sanity16 biggoa ddp8  (F resubmitted
    these ungated after the SMOKE=1 gate failed three times; 1-day limits, no dependencies)
  21353056 trajectory sweep PAR=2 — the one that finally covers avp_dronesweep + suomisoundi

ACTUALLY UNFINISHED, in priority order:
  1. goa_src caption chain. If 21351425 finished, the corpus is fully captioned (~4461) and the
     remaining steps are: year pass (`inject_year_into_captions.py --captions-dir`, dry-run first,
     `cp -a` backup — it rewrites in place), then Granite, then the sidecar. Year BEFORE Granite:
     Granite revises MF prose and would inherit wrong eras.
  2. Two long-run epoch sweeps FAILED and nobody chased them: 21342762, 21342763. They are the
     ladders that tell you which epoch to keep on the runs past ep100 before pruning, so that
     decision currently has half its evidence.
  3. The two decisions immediately below (goa arm's key join; avp/avpaug duplicate).

DO NOT trust a job's COMPLETED state as proof it did the work — 21345730 OOM-killed after exactly
its first batch of 6 runs and still reported COMPLETED, which is why we believed we had trajectory
stats for the broken arms for most of a day and did not. Check artifact counts against the job's own
"runs with >=3 checkpoints" line.

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

- **Every LatCH head we have was selected on TRAINING loss — do we re-validate the 14 production
  heads?** (C, 2026-08-18.) `train_latch.py` had no held-out set until today: `_best.pt` was
  whichever epoch fit the training crops hardest. That covers all 14 `*_best.pt` heads (the ones
  the explorer, the guidance path and the gain ladders all use) plus the f0 melody pilot — none of
  them has any evidence it predicts its feature on a track it has never seen. **This does NOT mean
  they don't work**: the gain-ladder work measured real steering authority on several, and steering
  is a different question from held-out regression. What it means is that "head X converged" was
  never actually established, and picking between two heads on `avg_loss` was not a comparison.
  Fixed now (`--val-frac 0.15 --val-group-by source_track`; split must be by track, since every
  track in `latents_sa3` has ≥2 crops). **Your call**: re-train the production heads with
  validation (cheap-ish, ~30-45 min each locally, and it would tell us which ones are real), or
  leave them and only validate new heads from here. I'd do the energy heads at least, since they
  are the ones with demonstrated authority and so the ones worth trusting precisely.

- **LUMI: submit the step-resolution trajectory job tonight (C, 2026-08-18 — your "save every step" ask,
  built and smoke-tested locally).** Two single-line commands from your LOCAL terminal, in SAO/:
  `rsync -avRn -e "ssh -i ~/.ssh/id_EFP" stable-audio-3/scripts/trajectory_sketch.py stable-audio-3/scripts/train_lora.py stable-audio-tools/stable_audio_tools/training/fusion_opt.py lumi/vendor/stable_audio_tools/training/fusion_opt.py lumi/sbatch/traj_sketch_arms.sbatch eval/trajectory_sketch_analyze.py akekim@efp.lumi.csc.fi:/project/project_465003186/code/`
  *(updated 01:10 — now EIGHT arms: + `bs1_fusion_cos` / `bs1_fusion_snr` / `bs1_fusion_cos_snr`, the muon
  damping tests you asked for; the two fusion_opt.py paths carry the new `--fusion-decay` / `--fusion-snr`
  code and the sbatch refuses to run without them.)*
  (dry run; then the same without `-n`). Then on LUMI: `cd /project/project_465003186/code && SMOKE=1 sbatch lumi/sbatch/traj_sketch_arms.sbatch`
  (30 steps/arm, ~5 min, exit code is the gate) and if it exits 0: `sbatch lumi/sbatch/traj_sketch_arms.sbatch`.
  Eight 1-GCD arms, 6 h: bs1/accum8/bs8 × AdamW + bs1/bs8 × Fusion + Fusion-bs1 × {cosine, SNR gate, both}, sanity16 recipe on goa; every step
  sketched, ckpt every step to 1000 then every 5 (~65 GB/arm on scratch — you said we have space; delete
  after). Read with `python3 eval/trajectory_sketch_analyze.py /scratch/project_465003186/runs/traj_sketch/<arm>/traj`
  (several dirs at once for cross-run). What it decides: whether the "broken AdamW" signature is BATCH
  (accum8/bs8 drift where bs1 diffuses) or OPTIMIZER (Fusion-bs1 healthy where AdamW-bs1 isn't).
- **LUMI, next night — the #59 melody A/B with the new R²(t)-gated arm (C, 2026-08-19; you asked for the code).**
  The v3 melody-subspace A/B (`lumi/sbatch/subspace_loss_v3sel_grid_mt.sbatch`, wired since 08-06) now has
  a 4th arm: K=5 + noise-level gate from the measured melody R²(t) curve (same recipe as arm 1, only the
  gate differs; the arm measures its own gate on its GCD first if the reference json isn't in the tree).
  Files: everything is in **one bundle, 106 KB, 11 files, paths relative to `code/`** —
  `/home/kim/Projects/SAO/traj_sketch_bundle.tgz` (also all pushed to the three GitHub mirrors:
  `avp-audio-craft` sa3-style-adapter 1b16bdb, `stable-audio-3` latch-sa3-phase1 fc576ea, `audio-tools-avp`
  main 3b7f82f). On LUMI after upload: `cd /project/project_465003186/code && tar xzvf traj_sketch_bundle.tgz && sbatch lumi/sbatch/subspace_loss_v3sel_grid_mt.sbatch`
  (4 GCDs on small-g, 40 h; preflight refuses to run if any of the new files is missing) and, if
  hours allow, `sbatch lumi/sbatch/traj_sketch_arms.sbatch` (8 arms, 6 h; the SNR-gate arms carry the
  FIXED grad-based gate now). Fallbacks if scp fails again: `scp -O`, `sftp`, or the LUMI web portal's
  Files upload. **Kill-criterion for the gated arm:** if by ep10 it does not move whitened-chroma
  recurrence (`eval/melody_wall_analysis.py`) or your ears vs arm 1, the melody-first (SFD) route gets
  the budget instead.
- **Listen: spectral-repair probes of a broken AdamW arm (C, 2026-08-18).** Four variants of
  `adamw_goa_t512_bs4_lr1e4` ep9, cfg 7 / W1 / 23.79 s / 3 prompts, rendering on CPU tonight into
  `lumi_runs/analysis/task_vector_gram_goa_2026-08-18/renders/` (UUID drive): `00_bad_terminal`,
  `01_remove_k1` (top singular direction of every matrix removed), `02_keep_k1_spike_only` (ONLY that
  direction kept — the control that says what the spike does), `03_good_ref_bf16cmp_bs8_ep7`, then
  `04_remove_k1_magreset`, `05_remove_k3`. If 01 is clean and 02 is broken, the shared spike is the
  pathology; if 02 carries the goa and 01 is base-like, the spike IS the learning. Either answer is a
  finding. Weight-space facts behind it are on the chat/WORKLOG. **DSP pre-read (00:40, n=3 each, weak
  metrics):** removing the top-1 direction restores BRIGHTNESS to the healthy level (centroid 1793→2486 vs
  healthy 2345; hf>8k 0.080→0.125 vs 0.118) but only partly the PUNCH (crest 3.47→3.95 vs healthy 4.64);
  spike-only is dull and punchless (2163 / 3.35). Consistent with the shared rank-1 direction being a
  low-pass/DC-shift and the lost dynamics living in the rest of the walk. Ears decide.
## ⏳ In flight — FYI, no action
- **Melody head (D3): first validated training arms DONE 2026-08-18 20:41 — both voices generalise; EMA
  monotone; lead 0.2036 (EMA, still improving @30), bass 0.1520 (EMA @24). Details in my journal.** — 4 arms,
  `{f0_other, f0_bass} × {plain, EMA 0.999}`, 30 epochs each, sequential on the local card (GPU
  mutex held). Answers three things nothing so far could: does the head generalise to unseen
  tracks, at which epoch does it turn over, and does EMA damping help. Second axis is EMA rather
  than concat-vs-adaln on purpose — `spectral_skewness` was once called "architecture-limited"
  and an EMA re-train reversed that verdict, so architecture is the wrong question to ask first.
  Read the curves with `latch/summarize_val_arms.py latch/val_arm_logs/`. Nothing needed from you;
  results will be a chat post. **Not a "works" claim either way** — held-out regression is
  necessary, not sufficient; steering authority + the disintegration gate + your ears still decide.

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

### ✅ PT→base soup ladder — LISTENED, closed NEGATIVE (Kim, 2026-09-07)
*"only the alpha .5 is listenable, and even that has artifacts... it's evident the mixing just degrades the sound."* **PT does not blend with base** — no usable intermediate model exists, so the punchy-vs-always-the-same question stays untested by this route. Falsifies the assumption the arm rested on: a fine-tune does NOT stay in the linear-mode-connectivity regime just because 997 of 1019 tensors are identical. Also explains why my descriptors gave opposite answers per sampler — they were reading artifact spectra, not a mixture. EXPERIMENTS C6, closed. Don't rebuild.

- **08-26 (C)** — render server (`:8056`) now saves z0 next to every render: `/generate` writes `out_NN.z0.npy` and every response carries a `latents` list, proved byte-identical on both sampling branches (same-seed A/B, same sha256), with a `/longform` continuation round-trip proof (prefix correlation 1.000). a2a paths deliberately save none (crossfade of separately-sampled windows, no single z0 produced it) and say why in `meta.z0_reason`. Closes the standing "save z0 next to every render" directive for the inference UI.
- **08-21 (W)** — the goa archive's worst 100 tracks archaeology: 76/100 declare ≥192kbps but their content stops at 4.7-11.9kHz — the source was destroyed before this encode (transcodes/rips/stream captures), spread over 90 distinct albums concentrated 1994-1999, not one bad batch. `mir/stats/goa_big_worst100/`.
- **08-21** — the "ONE caption decision" above got OVERTAKEN BY EVENTS rather than answered: tonight's
  `winning_fleet`/`fullft_fleet` campaign (12 arms) hit exactly the predicted failure — `biggoa`/`mix3`
  arms trained ~2h with EMPTY/unconditional prompts, the relpath-keyed sidecar never matching the
  bigset's synthetic latent ids. C caught it auditing the sidecars, ran the re-key tool that had sat
  built-but-unrun since 08-17 (`build_bigset_caption_sidecar.py`), 12523/12524 exact-relpath matches,
  `goa_bigset_hinted_bylatent.json` now exists (name implies the hinted/corrected Granite v5 pass, not
  confirmed against your original three options — worth a glance if the source matters to you). Six
  arms killed/cleaned/resubmitted; `sanity16` biggoa/biggoa_suomi arms in 21417155/56 also affected,
  left running (their suomi arms are valid), goa arms need a separate rerun. New lumi-ops rule: verify
  ONE key resolves before any launch on a new corpus+sidecar pairing. THE-FINN, from the channel.
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

