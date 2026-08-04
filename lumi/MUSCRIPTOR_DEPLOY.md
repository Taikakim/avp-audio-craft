# MuScriptor full-corpus batch — LUMI deploy (W, 2026-07-17; gate GREEN on section metrics)

Copy list (once, from local):
1. `muscriptor` package -> $CODE/muscriptor  (3.8 MB repo; pip not needed, PYTHONPATH'd)
2. MuScriptor weights -> $PROJ/hf_cache/hub/models--MuScriptor--muscriptor-medium (1.2 GB,
   from local ~/.cache/huggingface/hub/; HF_HUB_OFFLINE pattern as efp jobs)
3. `lumi/muscriptor_decode_task.py`, `lumi/muscriptor_shards/` + `muscriptor_shards.txt`
   (regen with gen_muscriptor_shards.sh), `lumi/muscriptor_ref_profiles.json` (~2 MB),
   `lumi/sbatch/muscriptor_full.sbatch`
4. mido into the container env if absent (pure-python; `pip install --user mido` works offline
   from a wheel — ship mido wheel alongside; it is the only non-container dep).
Latents: already on LUMI ($SCRATCH/latents_sa3 -> staged to /flash by the sbatch).

Submit: `sbatch lumi/sbatch/muscriptor_full.sbatch`  (1 node standard-g, ~17 h, 109 HQ shards)
Collect: `rsync $SCRATCH/muscriptor_full/ Mantu/sa3_lora_runs/muscriptor_full/` (~2 GB)
Then locally: musicology structure pass over the MIDIs (existing pipeline) -> section-character
labels; `integrity_flag` crops (expected ~5-10%, the fast-material failure mode) are excluded
from labels and listed in the collection report.
Queue position: behind fp32 campaign + task-50 per standing order — C slots it.
