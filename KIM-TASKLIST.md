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
- **Multi-node/32-GPU smoke submit — this is now the gate on spending 58% of the remaining LUMI
  budget at all, not a speed optimization** (C building, W's arithmetic 08-09). With 14 days left
  and 2880 of 5000 GPU-hours remaining: 2880h / (14d × 24h) = 8.6 GCDs would need to run
  CONTINUOUSLY just to spend what's left — on a single 8-GPU node the budget is barely spendable
  even at 100% duty cycle with zero failures, and we've had two 2-day timeouts + one 9s failed
  render this week alone. At 32 GCDs the remaining budget fits in ~3.75 days of continuous
  compute — the only config that can actually consume the allocation before it expires. C has a
  4-node/32-rank rendezvous smoke built (isolates one variable: does DDP extend across nodes into
  one world_size=32 group, or hang at the inter-node fabric) — cheap, ~mins of a 4-node alloc, de-
  risking before betting hours. Needs your submit to run.
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
- **aug8: is it worth ~2 of our 14 remaining days?** (C, 08-08 — closes the old "confirm
  still-open or close" carry from 07-31.) Root cause **settled** (Kim's own
  `ls /scratch/.../runs/aug8_train_ddp/`, 08-08: only the two `*_smoke` dirs exist) — the 8 real
  arms (fullft/dora × goa/avp × fp32/bf16) never trained, which is why there are no clips. This
  is a **RE-TRAIN, not a re-render** (~2-day allocation, not a quick sbatch). *(Separately,
  `sa3_aug8_render` job `20792735` also FAILED — ExitCode 2:0, 9s, 08-07 — mechanism still
  unverified pending the `.out` log, but doesn't change the re-train conclusion either way.)*
  **W's cost-risk catch, 08-09 — read before submitting anything:** `sa3_fullft_bigset` has
  TIMEOUT-ed twice at exactly the 2-day walltime (`20687866` ended 08-06, `20784494` ended
  08-08). A naive 2-day aug8 submit has an empirically ~0% completion rate on this queue right
  now. Whoever picks this up needs checkpoint-resume or a segmented submission FIRST, or it just
  times out a third time. **Budget, corrected 08-09 (Kim direct — the earlier "~weeks"/purge
  framing here was wrong): 14 DAYS remain, not weeks.** 5000 GPU-hour allocation, 42.4% used →
  2880 h left; 14 days = 336 wall-clock hours; 2880/336 = 8.6 GCDs would need to run
  CONTINUOUSLY just to spend what's left — on a single 8-GPU node the budget is barely
  spendable even at 100% duty cycle with zero failures, and we've had two 2-day timeouts + a
  9s failed render this week alone. (This is also why C's multi-node/32-GPU smoke submit above
  isn't a speed optimization, it's the only path that can consume the remaining budget at all.)
  Your call, explicitly: still worth ~2 of the 14 remaining days on the aug8-vs-aug3
  augmentation question (parked since 07-31), given `#68` is already competing for the same
  hours and has failed to finish twice itself? The render sbatch is ready the moment any real
  arm actually checkpoints — no code blocker on that side.
- *Carried from the 07-31 return-notes — team to confirm still-open or close:* alpha campaign + GOA-node submits.

## 👂 Ear queue (needs Kim's ears)
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

## ⏳ In flight — FYI, no action
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
- **08-05** — scored the 7 unscored arms (x0eq/subloss/lreq, 2808 clips: DSP+Audiobox+CLAP); their DoRA rows + audit-board links now live (links 8→14 of 22 runs). — W
- **08-05** — audit-board audio fixed (Kim: "awfully many missing auditable clips"). Clips were
  never missing: already live under `/files/evals/`, but `/files/audit/` had no `model_matrix/`
  sibling and the page's clip base is relative. Fixed with symlinks, no re-upload. — W
- **08-05** — doc-oversight first pass (PR #1); DISCOVERIES regenerated 54→201; fleet skills committed; this tasklist stood up.
- **08-04** — repo consolidated to GitHub (`main` + `sa3-style-adapter` synced, 104 GB artifacts gitignored); E1a x0-equiv arms shipped + scored (weak/inconclusive); board clip-resolution fixed.

---
*Deeper state: `WORKLOG.md` (what landed / broke) · `docs/open-threads.md` (open/dropped work ledger) · `profiles/*.journal.md` (per-instance).*
