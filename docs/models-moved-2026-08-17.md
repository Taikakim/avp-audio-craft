# Where the big model artifacts live (2026-08-17)

Kim, 2026-08-17: *"We should maybe move all of the models out of the repo. they could live in
/run/media/kim/9a410a1d-…"* — done. The repo tree went **236 GB → 84 GB**.

| was (in-repo)                     | now                                  | size  | symlinked back? |
|-----------------------------------|--------------------------------------|-------|-----------------|
| `onnx/exports/`                   | `<drive>/sao_models/onnx_exports/`   | 66 GB | yes (dir)       |
| `stable-audio-tools/models/`      | `<drive>/sao_models/sat_models/`     | 13 GB | yes (dir)       |
| `stable-audio-3/*.onnx{,.data}`   | `<drive>/sao_models/sa3_onnx/`       | 50 GB | yes (per file)  |
| `.essentia_sweep_*.log`           | deleted (completed-sweep logs)       | 24 GB | n/a             |

`<drive>` = `/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d` — the same removable drive the
LUMI pulls land on.

**Nothing in the code changed.** Every reference still resolves through the symlinks: `latch/*.py`
hardcode `models/checkpoints/small/base_model.ckpt`, and 12 call sites name `dit_medium-base_L256*`.
Verified after the move — those paths, plus `models/checkpoints/model.ckpt`, all still open.

**When the drive is NOT mounted, these are dangling symlinks.** That is deliberate: an ENOENT on a
named path is a loud, obvious failure, unlike a silently-absent file. If something can't find a
model, check `mount | grep 9a410a1d` before anything else.

**Two gotchas this move produced, both already fixed here:**
1. `.gitignore` needed BOTH `onnx/exports/` and `onnx/exports` — a trailing-slash pattern matches
   directories only, and git does not follow a symlink to decide what it is. The instant the
   directory became a link it fell out of the ignore and appeared as untracked.
2. The `lumi-ops` code-refresh recipe's exclude-list no longer bounded the tarball (it was building
   30+ GB "code" archives off these same artifacts). Fixed there to an allowlist.

To undo: `rm` the symlink, `mv` the directory back. The move used `rsync --remove-source-files`,
so nothing was ever deleted without being written first.
