# Handover — batched LoRA-TSD optimizer for our DoRA adapters (draft implementation)

**From:** CONTINUITY (desktop), 2026-09-24. **To:** Flatline — the remote CONTINUITY instance
(`continuity.flatline`; commit as **CONTINUITY**). **Asked by:** Kim. **Scope:** a working DRAFT with
CPU tests. No training runs: our GPU, data and checkpoints are on the desktop and you don't have them.
We benchmark and run it here afterwards.

---

## 1. Why this exists (read once, then don't re-derive)

We fine-tune SA3 `medium-base` (1.4B DiT, rectified flow, audio) with **DoRA, rank 128, on 229 layers**
using our modular optimizer (Muon-family: orthogonalised steps for 2-D params, sign steps for 1-D). Three
measured problems motivate LoRA-TSD:

1. **A is frozen.** A's row space stayed 99.2% unchanged from step 240 to 1440 (B's column space: 35%).
   The adapter reads a random 128-d slice of each layer's input all run. Cause: A starts large (norm
   ≈99), and fixed-size steps are a tiny fraction of it. Multiplying A's step ×20 made it rotate (overlap
   0.67), but ‖B·A‖ also grew 2.3× and one render went NaN. That test is confounded.
2. **Gauge drift.** A and B move in ways that don't change B·A (B·A = (BX)(X⁻¹A)). It's 4.8% → 12.4% of
   step energy over a run (chance 2%).
3. Both come from optimising A and B **separately**. **LoRA-TSD** (arXiv 2609.02734,
   https://github.com/brain-lab-research/LoRA-TSD, MIT) computes a Muon-style spectral step for the
   product **ΔW = B·A on the tangent space of the rank-r manifold**, then maps it back to A and B. So the
   step is sized on what the model actually sees, and gauge motion is handled explicitly (optional
   ‖A‖=‖B‖ rebalancing).

**Measured on our 229 adapters with the reference code, unbatched, on RX 9070 XT / ROCm:**
**8.5 s per optimizer step at `ball_iters=1`, 31 s at 5** (their paper setting). Cause: ~6 small
linalg calls per adapter per step, each latency-bound on ROCm. `torch.linalg.qr` takes 12–17 ms per call
whatever the size; CholeskyQR2 takes ~2 ms (orthogonality error ~1e-6); a 256×256 `inv` ~2 ms; the large
matmuls 0.07–0.43 ms. **The whole job is batching.** Target: well under 0.5 s per step.

DoRA compatibility is already checked. The loss depends on A and B only through B·A: W' = m ⊙ (W0 +
s·BA)/‖W0 + s·BA‖_row, with the per-row magnitude m a separate parameter. The reference `LoRATSD.step`
with B = 0 (our init) produced finite values on steps 1 and 2 for all 229 adapters.

## 2. The reference algorithm (from `src/optimizers/lora_tsd.py`, read in full)

Per pair (A: r×n, B: m×r), each step:

1. Momentum on the factor grads: `bufA = μ·bufA + (1−μ)·G_A`; same for B. Use the buffers as G_A, G_B.
2. `U_B = qr(B).Q` (m×r), `V_A = qr(Aᵀ).Q` (n×r); `BtB_i = inv(BᵀB + ridge)`, `AAt_i = inv(AAᵀ + ridge)`,
   with ridge = eps·mean(diag).
3. Tangent-projected weight gradient in factored form, L_g (m×2r) · R_g (2r×n):
   `Mc = BtB_i (G_A Aᵀ) AAt_i`; `L_g = [B, G_B AAt_i]`; `R_g = [BtB_i G_A − Mc A ; A]`.
4. `ball_iters` times: `Q_L,R_L = qr(L)`; `Q_R,R_R = qr(Rᵀ)`; `T = NS5(R_L R_Rᵀ)` (2r×2r Newton-Schulz,
   coefficients 3.4445, −4.7750, 2.0315); `L,R = P_T(Q_L T, Q_Rᵀ)`, where `_proj_T_factored` gives
   `L' = [U_B, L D]`, `R' = [C R − (C D) V_Aᵀ ; V_Aᵀ]` with `C = U_Bᵀ L`, `D = R V_A`.
5. `X_fro = sqrt(sum((LᵀL) ∘ (R Rᵀ)))`.
6. Factor updates: `dB = −lr·(L (R Aᵀ)) AAt_i`; `dA = BtB_i (−lr·(Bᵀ L) R − (Bᵀ dB) A)`.
7. Clip: if `lr·X_fro > max_delta_norm`, scale dA and dB by `max_delta_norm / (lr·X_fro)`.
8. Apply; optional `_rebalance_group` ("norm": scale A by c = √(‖B‖/‖A‖) and B by 1/c, momentum buffers
   inversely; "whiten" mode exists too).

Quirk to preserve: **`lr_A` is used for both factors**; `lr_B` only feeds the unused `alpha` default and
diagnostics. Their run settings (`scripts/main/run_1b.sh`, Llama-3.2-1B, rank 16): lr 5e-3,
max_delta_norm 0.1, momentum 0.95, ball_iters 5, NS steps 5, balance norm every step. Ours will need an
LR bracket; don't tune, just expose.

Note the reference groups each (A, B) pair as its own param group, with exactly `[A, B]`. Ours can't:
Lightning/our trainer hands in one flat parameter list.

## 3. What to build

**Files (stable-audio-tools repo, `Taikakim/audio-tools-avp`, branch `main` — see §6 for the branch you
work on):**

- `stable_audio_tools/training/lora_tsd/reference.py`: the upstream algorithm ported as-is, one pair at
  a time. MIT header + attribution to brain-lab-research/LoRA-TSD (commit e6ef0e1). It's the correctness
  oracle for tests, not for training.
- `stable_audio_tools/training/lora_tsd/batched.py`: `BatchedLoRATSD(torch.optim.Optimizer)`:
  - **Pairing:** constructed from `named_parameters`; pair `X.lora_A` with `X.lora_B` by name prefix.
    Real key example: `model.to_timestep_embed.0.parametrizations.weight.0.lora_A`.
  - **Batching:** group pairs by `(A.shape, B.shape)` and stack each group into 3-D tensors for the big
    matmuls (`torch.bmm` / batched `@`). **All r×r and 2r×2r work (inv or Cholesky, Newton-Schulz, the
    R-factors) batches across ALL pairs at once**, because r = 128 everywhere.
  - **QR:** replace `torch.linalg.qr` with batched CholeskyQR2 (Q = Y·L⁻ᵀ with L = chol(YᵀY), done
    twice), plus a fallback to real QR for any batch whose Cholesky fails (e.g. B ≈ 0 on step 1, where
    BᵀB is singular). The first step with B = 0 **must** work, because that's our init.
  - **1-D parameters:** anything unpaired, i.e. the DoRA `*.magnitude` vectors (229 of them), takes a
    simple **multiplicative sign step**, `m ← m·exp(−lr_mag·sign(momentum))`. Same rule as
    `ModularOptimizer(magnitude_update="multiplicative")` in `modular_opt/optimizer.py::_magnitude_step`;
    reuse it. Own lr (`lr_magnitude`), no weight decay. (Why: fixed-size additive sign steps walked
    small magnitudes through zero and NaN'd a run. `docs/training-findings.md` in the SAO repo,
    entry A1.)
  - **Settings:** lr, momentum, ball_iters, ns_steps, max_delta_norm, balance (off/norm), ridge_eps,
    lr_magnitude. fp32 math internally, whatever the param dtype.
  - **Checkpointing:** `state_dict` / `load_state_dict` must round-trip: momentum buffers per param,
    keyed so a resume re-pairs correctly.
- `tests/test_lora_tsd_batched.py`, CPU, small shapes (r = 8, a few different n/m), fp64 where useful:
  1. **Equivalence:** batched vs reference, same inputs, several steps, all settings on; match to
     ~1e-5 relative (fp32) or ~1e-10 (fp64). THE key test. Include unequal shape groups.
  2. **Zero-B step:** B = 0, finite output, B becomes non-zero.
  3. **Gauge:** for a pure-gauge perturbation of the inputs (A→XA, B→BX⁻¹ with X near identity), the
     resulting ΔW = B'A' − BA agrees to first order (the method is designed to be step-invariant under
     reparameterisation; tolerance loose). If it doesn't hold even in the reference, drop the test and
     say so in a note rather than weaken it silently.
  4. **Clip:** ‖ΔW‖_F ≤ max_delta_norm + ε per pair.
  5. **Magnitudes:** stay positive under a consistent push toward zero for 1000 steps; relative change
     identical for 0.13 and 2.4.
  6. **state_dict round-trip:** resume, and the next step is identical.
- `stable_audio_tools/training/lora_tsd/bench.py`: a CLI that builds the 229 pairs from the shape table
  below with random data and prints ms/step for the reference and the batched version at ball_iters
  1 and 5. **We run it on the GPU here.** Make it runnable on CPU too, so you can smoke it.

**Our 229 adapter shape pairs (from a real checkpoint; r = 128 for all):**

| count | A | B |
|---|---|---|
| 76 | 128×1536 | 1536×128 |
| 24 | 128×1536 | 7680×128 |
| 24 | 128×1536 | 3072×128 |
| 24 | 128×1536 | 4608×128 |
| 24 | 128×1536 | 12288×128 |
| 24 | 128×6144 | 1536×128 |
| 24 | 128×257 | 1536×128 |
| 2 | 128×256 | 1536×128 |
| 2 | 128×768 | 1536×128 |
| 2 | 128×256 | 256×128 |
| 1 | 128×1536 | 256×128 |
| 1 | 128×1536 | 9216×128 |
| 1 | 128×256 | 768×128 |

Plus 229 `*.magnitude` vectors of length = B's first dim.

**Trainer wiring (stable-audio-3 repo, `Taikakim/stable-audio-3`, `scripts/train_lora_modular.py`):**

- `--optimizer lora_tsd` alongside `modular/fusion/adamw/lion`. `ModularTrainingWrapper.configure_optimizers`
  (≈ line 119) already dispatches on `opt_type`; add a branch that builds `BatchedLoRATSD` over
  `self.diffusion` named params (same route root as the modular branch: conditioner LoRA params included).
- Flags: `--tsd-ball-iters` (default 1), `--tsd-max-delta-norm` (0.1), `--tsd-momentum` (0.95),
  `--tsd-balance {off,norm}` (norm), `--tsd-lr-magnitude` (default = `--lr`). Reuse `--lr`,
  `--warmup-steps` (linear warmup on lr, like the modular branch). Record them in the
  `optimizer_config` dict, so `run_meta.json` captures them automatically (it dumps all args).
- **Things that must keep working** (read these before wiring):
  - `stable-audio-3/stable_audio_3/training/diffusion.py`: `_fusion_opt()` (strict FusionOpt check) and
    `_sf_opt()` (duck-types `uses_sf_averaging` + `train`/`eval`). LoRA-TSD has no Schedule-Free, so
    expose neither and both become no-ops. Don't give it a `set_loss` unless it needs one.
  - `stable-audio-3/scripts/mechanism_audit.py`: reads modular telemetry; make it skip cleanly (no
    false "INERT" warnings) when the optimizer isn't ModularOptimizer.
  - `stable-audio-3/scripts/eval_demo_callback.py`: offloads optimizer state under OOM pressure
    (`_run_with_oom_guard`); check that it handles your state layout.
- **Docs:** add every new flag to `SAO/docs/train_lora_modular.md` (§5). `SAO/Misc/check_train_manual.py`
  fails otherwise, and that's the drift check we rely on.

## 4. Acceptance for the draft

- All tests in `tests/test_lora_tsd_batched.py` pass on CPU: equivalence to the reference is the gate.
- `bench.py` runs on CPU and prints both timings.
- `train_lora_modular.py --help` shows the new flags; `check_train_manual.py` passes;
  `python -m py_compile` on everything touched.
- A short `NOTES.md` in the package: what's batched, what isn't, anything in the reference you changed
  or didn't understand, and open questions. **Say plainly what you did not verify.** We'll check the rest
  on the GPU.
- Out of scope: training runs, LR tuning, the "whiten" balance mode, torch.compile, Triton kernels.

## 5. Traps that bit us (don't re-learn them)

- The DoRA magnitude is `…parametrizations.weight.0.magnitude`: pair by prefix, not by position.
- `Misc/` in SAO contains a `filelock.py` that shadows the real `filelock` package when `Misc/` is on
  `sys.path`. `check_train_manual.py` already handles this.
- Never assume a fix works because it compiles: our last three bugs of this kind were silent (wrong
  weights rendered, NaN treated as healthy, flags accepted but inert).
- `--lr`'s default (5e-6) is useless; the modular runs use 5e-4 to 6e-4. LoRA-TSD's scale is different
  (its lr multiplies a unit spectral-norm ΔW step, clipped by max_delta_norm), so don't copy ours over.

## 6. Git — non-negotiable

- Work on a **new branch `lora-tsd-port`** in both repos. Don't commit to `main` / `latch-sa3-phase1`.
- Commit with `SAO/Misc/agent_commit.sh CONTINUITY -F <msgfile>` (plain `git commit` authors as
  "Kim"). It fails silently: verify with `git log -3 --format='%h %an %s'`. Write messages for the
  archaeologist: what, why, what you verified.
- **Push only the `lora-tsd-port` branch, naming remote and branch explicitly:**
  `git push origin lora-tsd-port` (stable-audio-tools), `git push fork lora-tsd-port` (stable-audio-3).
  **Never `git push` bare, and never touch the `upstream` remote in stable-audio-3** (it points at
  Stability-AI with a push URL).
- Never put prose into a double-quoted shell string (backticks / `$` execute). Use `-F <file>`.
- When done, post a summary to the SAO dialogue (or leave `NOTES.md` if you can't reach it). Say which
  tests pass and what is unverified.
