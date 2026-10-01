# Fork patches for Latent Forge (stable-audio-3)

Two commits against `Taikakim/stable-audio-3` @ `latch-sa3-phase1` (6223be1), written and tested in a
cloud session on 2026-10-01 (`tests/test_latent_forge_hooks.py`: 5 passed on CPU, torch only).

| patch | what | plan |
|---|---|---|
| `0001-…scale_phi…` | forward `scale_phi` (CFG rescale) on the LatCH-guided path | M3 Task 3 |
| `0002-…init_latents…` | `generate(init_latents=, inpaint_latents=)` + `_fit_latents` | M8 Task 1 |

Apply in the fork worktree the plans name (`/home/kim/Projects/sa3-fork-forge`, branch
`latent-forge-hooks`, push to remote `fork` only):

    git am /path/to/docs/latent-forge/fork-patches/000*.patch

I did NOT push to the fork: that repository is outside this session's push scope. Re-run the hook
tests on the GPU box, and run `eval/tests/test_forge_*.py` with `PYTHONPATH` pointing at the fork
(the schedule test `test_array_schedule_through_build_schedule` exercises the real `build_schedule`).
