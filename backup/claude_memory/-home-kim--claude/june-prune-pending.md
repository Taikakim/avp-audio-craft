---
name: june-prune-pending
description: "Kim 2026-11-03: prune June experiment checkpoints + audio (not fine-tunes). Manifest ready, 152.9 GB; my delete was blocked by the permission classifier, Kim must run or allow it"
metadata:
  type: project
---

**Kim, 2026-11-03:** prune older June experiment checkpoints and their audio; NOT fine-tunes; keep scripts, docs, other files and folders.
Overrides the ckpt-prune skill's "all checkpoints are kept" for this scope only. Ready at `/home/kim/sao_runs/june_prune/`: run from SAO root
`python3 /home/kim/sao_runs/june_prune/june_delete.py /home/kim/sao_runs/june_prune --apply`, then `verify.sh`. Review list: SAO docs/pruning/2026-11-03-june-review.md. The 'longer Fusion has vibe' favourite (onset_FUSION_lr2e5_40epoch + onset_eval_lr2e5_*) is held out for Kim's decision, in held_favourite.tsv.
Kept by design: `onset_Fusion_lr1e-4_randomcrop` (server's default FiLM), `onset_FUSION_lr2e5_40epoch/{soup_exppeak,riffer_final}.pt`, `soups_vibe`, `sa3_lora_runs`, `model_matrix`, `latents_sa3_stem_chroma`, evals_aac, riffer-evals.
**After it runs:** gzip june_delete_final.tsv into SAO docs/pruning/, add a WORKLOG line and a note in the ckpt-prune skill, post to channel. Then delete this memory.

**Kim 2026-11-03, later: 'we don't delete unaudited stuff.'** The prune is on HOLD until Kim has looked. Kim's view on the beat adapter (`onset_Fusion_opb_*`): probably old and not that good, leave only the last checkpoint of each. Manifest updated to spare those finals.

**Update 2026-11-03:** Kim reorganised sa3_control_runs into __theme folders; I finished it (map: __MOVED_MAP.json). __onsets wavs are gone, AAC kept. __onsets checkpoints still pending: plan in /home/kim/sao_runs/june_prune/onsets_ck_plan.json keeps finals plus code-named ones. Audit: eval/audit_run_evaluations.py, CSV in /home/kim/sao_runs/run_audit/. Manifest june_delete_manifest.tsv is stale after the moves: rebuild before use.
