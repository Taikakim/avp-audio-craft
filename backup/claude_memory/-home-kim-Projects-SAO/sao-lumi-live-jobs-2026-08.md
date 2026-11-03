---
name: sao-lumi-live-jobs-2026-08
description: "LUMI live job IDs + the DDP-formation rule (torchrun, not SLURMEnvironment) — check/act on resume"
metadata:
  node_type: memory
  type: project
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-08-17T17:55:55.592Z
---

**LUMI project_465003186. Check `squeue --me`; verify `R` != frozen via train.log MTIME.**

## THE RULE THAT SUPERSEDES EVERY EARLIER DDP NOTE (verified 2026-08-17)

`srun --gpus-per-task=1` + relying on Lightning's `SLURMEnvironment` **silently fails to form a
DDP group** — every rank logs `LOCAL_RANK: 0`, giving N uncoordinated single-GPU trainers writing
colliding `-vN` checkpoints. No crash, no hang. Adding `--devices N>1` does NOT fix it (cgroup
isolation ⇒ each process sees exactly one GPU ⇒ `MisconfigurationException`). Earlier memories and
in-file comments calling this "Pattern 1 / VERIFIED" were wrong — that was evidence about one job,
never checked.

**Working pattern:** `srun --ntasks=1` (all GPUs visible) + `torchrun --standalone
--nproc-per-node=N`, plus `train_lora.py`'s `torch.cuda.set_device(int(os.environ["LOCAL_RANK"]))`.
Two arms on one node: add a **per-arm rdzv port** + explicit `ROCR_VISIBLE_DEVICES` + `srun --overlap`.

**Universal cheap check — run on ANY multi-GPU log before trusting it:**
`grep -h LOCAL_RANK <log> | sort | uniq -c` → want `0..N-1`, not N zeros.

⚠️ **Any conclusion drawn from an earlier multi-GPU run may be confounded** (incl. parts of the
drone / weight-decay diagnosis). Not re-audited.

## Jobs (2026-08-17)

- **21330736 — dora256_mixed_2x4gpu, FULL RUN, live.** Two DoRA arms on one node, 4 real DDP GPUs
  each, mixed avp+goa T4096, fp32, 8ep, warmup 0.5ep, AGC. A: r256 α196 lr1e-4 (GPUs 0-3, port
  29511). B: r256 α128 lr5e-5 (GPUs 4-7, port 29521). 48h walltime. **EMA is a no-op here** —
  `train_lora.py` force-disables it for LoRA/DoRA (full-FT only). Smoke 21330059 PASSED.
- **21251551 — fullft mixed avp+goa wd03, COMPLETE.** First trustworthy full-FT: real DDP
  (LOCAL_RANK 0-7, zero `-vN` dups, 244 steps/ep = 1948/8), 3h41m vs 1d8h. ep0-ep7.
  Rendered as job 21329730 (108 cells, `fullft_mixed_wd03__*`) — **pull + score still pending**;
  this is the run that tells us whether the droning was the DDP bug, the WD, or both.
- **21244499 — big-goa preencode, COMPLETE.** 12523/12523 latents, RSS flat ~1GB. **NOT yet
  trainable:** latent ids are synthetic (`{shard}{batch}{i}`), so a caption sidecar keyed by track
  relpath misses everything and training would use EMPTY prompts. Two-step fix: regenerate captions
  (`eval/build_goa_archive_sidecar.py`) → re-key onto latent ids
  (`lumi/build_bigset_caption_sidecar.py --report-only` first). Gated on G's granite revisions.
- **21172226 — sa3_cont, long-running** (was the only thing in the queue for days).
- Granite bigset caption revision: G's lane (v5 submitted as 21255037).

## Standing gotchas re-confirmed this month

- `--epochs` omitted ⇒ `max_steps` falls back to `--steps` (default 10000) ⇒ on a resumed run past
  10k it trains ZERO steps and reports `COMPLETED 0:0`. Always pass `--epochs`.
- PYTHONPATH inside multitorch must **APPEND** (`${PYTHONPATH:+:${PYTHONPATH}}`) — bare `export`
  drops the container's `/opt/venv` where torch lives ⇒ `ModuleNotFoundError: No module named
  'torch'`. Overlay still goes FIRST; both hold at once.
- `#SBATCH` parsing stops at the first non-comment non-blank line.
- FA2 refuses fp32 — the fp32 DoRA arms cannot use flash-attn regardless of container.

Related: [[goa-corpus-quality-flac-plan]], [[lumi-air-gapped-rsync-only]],
[[update-lumi-skill-on-fixes]], [[lumi-project-purge-deadline]].
