# Work-through plan, 2026-07-22 (CONTINUITY, Kim's "fallen off the cart" reset)

Four lanes; each item names its owner. Principle per Kim: **LUMI-offload everything that
doesn't need his ear or the local card.** Status legend: 🔥 running · ⏳ queued · 🧍 Kim.

## Lane 1 — local card (mutex-gated, ONE chain at a time)
1. 🔥 `recovery_chain2.sh` (C, running, `.recovery_chain2.log`): ptm pass-A refill (~41) →
   W's avp 18-cell fill → goa `_repr` ep5/ep6 lates → full resumable sweep = re-render the
   62 local native cells with TRUE windows (sample_size fix) → board rebuild.
2. ⏳ W ships the board after rebuild (his lane; alignment fix retained).
3. ⏳ G: audiobox CE resume on `_ptm` (54/149) + DSP metrics + stats page (delegated, DM'd).
4. ⏳ #35 breathing-noise GPU validation render (C or G, one short render, after 1–3).

## Lane 2 — LUMI (now trusted; the offload target)
1. 🧍 Resubmit **native_cells + fullft_cells** with the fixed workers (scp + purge + sbatch
   block already given in chat 2026-07-22 ~01:5x). Success = the jobs' own NEXPECT lines.
2. 🧍 **Muscriptor**: pull partials + resubmit (resumable — skips existing `.mid`):
   pull: `rsync -av -e "ssh -i ~/.ssh/id_EFP" akekim@efp.lumi.csc.fi:/scratch/project_465003186/muscriptor_full/ /run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/muscriptor_full/`
   resubmit: `cd /project/project_465003186 && sbatch code/lumi/sbatch/muscriptor_full.sbatch`
   (integrity check after: `.mid` count vs shard manifest — C crafts it on completion.)
3. 🧍 #54 health check (never done, 23h in): `tail -4 /scratch/project_465003186/runs/fp32frames_goa_t4096_bs4_lr1e4/train.log`
4. ⏳ **#46 part 2 — ARC-Forcing continuation FT** (C specs sbatch tonight): rollout-dataset
   build on LUMI (arc_rollout_dataset.py, GPU) → fine-tune → drift eval over successive
   extensions. OPEN (🧍): base choice — DoRA-on-medium-base (composable, recommended) vs fullft arm.
5. ⏳ #53 LatCH+FiLM campaign (+ HF-drift-penalty arm from #56) — next LUMI campaign after #46,
   or before it if Kim prefers (both are sbatch-ready patterns now).
6. ⏳ t3072 (+1024) context arm — only if #54's sweep shows monotone gains (else skip).

## Lane 3 — CPU / no-GPU (C + F, background)
1. ⏳ `model.py` sample_size footgun fix (pooled since 07-15, now cost 103 renders): honor
   duration up to model max + loud warning. C does it; W reviews (it was his POOL item).
2. ⏳ `eval/disintegration_metrics.py` shared module (owed to W).
3. ⏳ sa3_control multi-source dropout check (StemGen export; cheap read of train.py).
4. ⏳ todos.md triage → kill-list for Kim (19 checkboxes + 4 POOL, several 07-07-era stale).
5. ✅ Re-download real 2505.18186 PDF — DONE/moot (F verified 07-22 04:xx): real PDF
   already present at `papers/` root (07-11), pdftotext page-1 confirms `arXiv:2505.18186`
   + correct title; mislabeled 2607.17624 quarantined in `reviewed-low-relevance/`. No
   download needed.

## Lane 4 — Kim's ear / rulings (nothing moves without you)
1. 🧍 `_ptm` rows listening verdict (#55's final judge — feature-space already refutes the
   Discord "no different" claim; your ear decides).
2. 🧍 avp arm stack priority ruling (#28/#29/#36/#37/#39; C's read: keep #36 BoRA + #39
   freeform, fold/kill the rest).
3. 🧍 #46 base choice (Lane 2.4).

Standing: #26/#34/#49/#50 stay parked until the above clears; #44/#56 are DONE (see journals).
