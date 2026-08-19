# Forward-Evolution Error Analysis and Adaptive Design for Matrix-Valued Diffusion Models (2608.15103v1) — deep-read

Pang, Shen, Zhang (Tsinghua YMSC / NUS), math.ST, 15 Aug 2026. PDF in papers/ root. **Read by C
2026-08-19 (§1, §5, §6, §7 in full; §2–4 = the KL/complexity proofs, skimmed).** Arrived via the external
Claude analysis Kim relayed; every load-bearing claim of that summary was checked against the PDF and holds.

## What it is
Theory for **variance-preserving OU diffusion with matrix-valued schedules** `dX = −½β(u)X du + β(u)^{1/2}dW`,
β SPD. Transfers reverse-time discretization error to the forward corruption law and analyses two frozen
schemes: **score-freezing** → step complexity `d/ε²` (ambient dimension); **posterior-mean-freezing** (exact
Gaussian drift, frozen `m_u = E[X0|X_u]`) → `k log k/ε²` with k the metric-entropy dimension. Both match,
not beat, known worst-case orders; the contribution is the unified forward proof + the design rules it yields.

## The prescriptive parts (verified)
- **Cor 5.2 (Gaussian fixed-spectrum alignment):** `g_sc = ‖V^{-1/2} β V^{-1/2}‖_F²`; a minimizer shares
  eigenvectors with the marginal covariance V and **pairs the larger noising rate with the larger variance**
  → low-variance directions are noised MORE SLOWLY.
- **Prop 5.3 (intrinsic subspace alignment):** if data lie in a k-dim subspace U, assign the k largest
  cumulative rates to U (bound-level, not exact optimality; commuting schedules only).
- **§5.2 / Prop 5.5 (adaptive grid for a FIXED schedule):** equidistribute √(local growth): `F(t)=∫₀ᵗ√g`,
  `t_i = F⁻¹(i/N·F(t_N))`; leading cost `L²/(2N) + o(1/N)` and no O(1/N)-mesh grid beats `L²/2` in the
  liminf. Estimable from forward-noised pilot samples (eq. 5.23: difference a pilot-cell energy K̂, add the
  schedule term, floor by ρ). **"For a pretrained model whose schedule cannot be changed, only the
  grid-design step applies."** (p.33)
- **§6 experiment (100-d product Gaussian mixture, analytic scores, N=64):** uniform 68.20 → hybrid 61.64 →
  adaptive **57.36** on exact discretization error (−15.9 % / −6.9 %); ordering holds N=16…96 (47.84 / 41.52 /
  38.66 at 96). Schedule direction: forward rotation 57.36 < within-fixed 58.65 < marginal-fixed 60.08 <
  reverse rotation 60.66 → "rotation alone is insufficient; its ordering must track the scale-dependent
  forward geometry."
- **Caveats, the authors' own:** VP-OU only (stochastic interpolants "not pursued", p.7); synthetic
  "proof of concept", no learned predictor, no pilot-estimation error tested; no code; asymptotic in N.

## FOR US
- **Three routes, one answer.** Cor 5.2 + Prop 5.3 resolved for our latent (melody = inside the data manifold,
  low-variance within it) → the discretization-optimal schedule noises the melody subspace more slowly ⇔ melody
  is cleaner at every t ⇔ melody LEADS in the reverse process. That is SFD's Δt (2512.04926, empirical), the
  learned-schedule paper's family (2602.19512), and our own R²(t) measurement (melody abandoned at high
  noise) — from theory, from images, from our model. **Inference, not theorem:** the theory minimises
  discretization error, not melody learnability; the coincidence is C's/the external reader's reading.
- **Rotation matters, and our geometry rotates:** rhythm dominates at high noise, harmony/melody at low
  (our layer×feature R² maps). SA3's latent is a candidate for a ROTATING matrix schedule, not just a fixed
  anisotropic one — a stronger and later claim.
- **The one thing usable now — the adaptive grid — is for `-base`, many-step sampling only.** Our
  production is APT-distilled few-step (asymptotics void). RF analogue: equidistribute √(local error growth)
  ≈ the curvature of the learned velocity field along the path, estimable from a pilot batch — the
  known "curvature-adaptive step" family (cf. Align Your Steps, Sabour et al. 2024, which optimises grids
  via KL bounds; not re-read here). Expected gain: single-digit-to-mid-teens % discretization error at
  16–64 steps = fewer steps for equal quality, NOT better melody. Cheap (hours, base ckpt, sampler seam
  `build_schedule` accepts custom grids); low priority.
- **Complexity note that favours what we already have:** posterior-mean freezing (`k log k/ε²`) is the
  scheme rectified flow hands us for free (`ẑ0 = z_t − t·v̂`); its precondition k ≪ 256 is the same
  eigen-measurement (786× anisotropy) that grounds the melody work.
- **What stays ours / what it can't do:** no RF theorem, no real data, no learned predictor. Pair with
  2602.19512 (criteria from this one, implementation from that one) only when a real melody-schedule
  finetune is committed; then `P_melody` is used twice — where noise goes (schedule) and where gradient
  pressure goes (#59 loss).
