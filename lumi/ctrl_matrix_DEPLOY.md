# ctrl_matrix campaign — DEPLOY note

Deploy prerequisites for `lumi/sbatch/ctrl_matrix_hq.sbatch` + `lumi/gen_ctrl_matrix_tasks.sh`
(60-task control-matrix fan-out: 20 features x 3 variants across one standard-g node's 8 GCDs).

## The gap
The current `lumi/pack_data.sh` code snapshot ships **stable-audio-3** and **stable-audio-tools**
(git-archive) plus a copy of **lumi/**. It does **NOT** ship `control/`. This campaign runs
`sa3_control.train`, so `control/` MUST be added to the LUMI `/code` tree. Also the just-built
changes must be present:
- `control/sa3_control/train.py` — `--encoded-dirs`, `--control-mode dual_scalar`,
  `--scalar-from-timeseries <F>_ts` (dual-scalar path). These may be **uncommitted** locally —
  use a working-tree tar (below), not `git archive HEAD`, or commit first.
- `stable-audio-3/scripts/latch/train_latch.py` — `--latent-dirs` multi-root + `--target-source npz`.

## Local dirs that must be in the code tarball
Target tree on LUMI: `CODE=/project/project_465003186/code` — the sbatch reads
`${CODE}/control`, `${CODE}/stable-audio-3`, `${CODE}/lumi/vendor`,
`${CODE}/lumi/gen_ctrl_matrix_tasks.sh`.

| Local dir | Why | Container path used |
|---|---|---|
| `/home/kim/Projects/SAO/stable-audio-3` | LatCH trainer + `stable_audio_3` pkg (multi-root latch change) | `${CODE}/stable-audio-3` (PYTHONPATH + `train_latch.py`) |
| `/home/kim/Projects/SAO/control`        | `sa3_control` pkg (dual-scalar change) — **NEW, was not shipped** | `${CODE}/control` (PYTHONPATH -> `python -m sa3_control.train`) |
| `/home/kim/Projects/SAO/lumi`           | generator, this sbatch, vendored FusionOpt, env | `${CODE}/lumi` (`vendor` on PYTHONPATH, generator, sbatch) |

`control/sa3_control/__init__.py` exists, so `PYTHONPATH=${CODE}/control` makes
`python -m sa3_control.train` importable. The sbatch sets
`PYTHONPATH=${CODE}/control:${CODE}/stable-audio-3:${CODE}/lumi/vendor` for every task.

## Build + extract
Working-tree tar (captures the just-built, possibly-uncommitted flags):
```bash
cd /home/kim/Projects/SAO
tar -czf ctrl_matrix_code.tgz \
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  control lumi stable-audio-3
# ship it (rsync to a login node), then on LUMI:
mkdir -p /project/project_465003186/code
tar -xzf ctrl_matrix_code.tgz -C /project/project_465003186/code
```
This lands `.../code/control`, `.../code/lumi`, `.../code/stable-audio-3` — exactly the paths the
sbatch expects. (If only latch/control changed and the rest is already on LUMI, tar just
`control` + `lumi` + `stable-audio-3/scripts/latch/train_latch.py` and extract over the top.)

## Also required on LUMI (already the standard deployment, unchanged)
- Container: `/project/project_465003186/containers/sa3.sif` (cotainr).
- Models pre-staged under `/project/project_465003186/models` (`HF_HUB_OFFLINE=1`).
- `latents_sa3.tar.gz` + `latents_avp.tar.gz` on `/scratch/project_465003186` (Kim rsync) — the
  sbatch stages both to `/flash` once at job start.
- HyperQueue: `module use /appl/local/csc/modulefiles && module load hyperqueue` (LUMI 0.18.0);
  or set `HQ_BIN=/project/project_465003186/code/lumi/bin/hq` to a downloaded static binary.
