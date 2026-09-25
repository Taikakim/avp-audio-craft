# Proposal: Adaptive Rolling-Quantile Step Velocity Dampener (P95 Global Step Governor)

**Status:** REVIEWED 2026-09-25 (CONTINUITY) — **step governor (§3–§6) NOT adopted**;
**flight recorder (§7–§8) BUILT, re-targeted to the raw gradient.** See the review box below;
struck or corrected claims are marked inline with ⚠.  
**Date:** 2026-09-25  
**Author:** Kim & Antigravity.Neuromancer  
**Component:** `stable_audio_tools/training/modular_opt/` & `stable-audio-3/scripts/train_lora_modular.py`

---

> ### Review (CONTINUITY, 2026-09-25) — read this before the rest
>
> **Why the governor was not adopted.** Our optimizers normalise the step. Muon/Newton–Schulz
> returns an update of fixed spectral size, the sign group moves every scalar by exactly ±lr,
> and LoRA-TSD takes an msign step. So the composite step norm S_t is set by the learning rate
> and the layer shapes, not by how pathological the batch was: a gradient spike is removed
> *before* it reaches S_t. A quantile governor on S_t therefore watches a quantity that
> barely moves.
> - It would not have caught our one diagnosed catastrophic failure. The goa3 NaN was DoRA
>   magnitudes crossing zero under fixed-size sign steps (`docs/training-findings.md`, group A);
>   no step was unusually large. That mechanism is fixed by `--modular-magnitude-update
>   multiplicative`.
> - A P95 threshold fires on 5% of steps by construction, healthy run or not. Being rolling,
>   it also rises with a slow runaway, so it can't see drift (the known runaway family).
>
> **Where a spike does real damage** under a normalised optimizer is the MOMENTUM buffer: one
> outsized gradient dominates it for ~1/(1−β) steps and steers their direction. So the right
> thing to watch is the gradient BEFORE clipping and normalisation. That is what was built:
> - `stable-audio-3/stable_audio_3/training/flight_recorder.py`: per-kind raw grad norms
>   (`grad/raw_norm_{lora_A,lora_B,magnitude,other,total}`, `grad/nonfinite_tensors`) every
>   step, plus a robust rolling z-score (median/MAD of log-norm; the spike never enters its own
>   yardstick). It dumps an incident on z > threshold or any non-finite gradient. Diagnostic
>   only: it never changes a gradient or a step.
> - `eval/inspect_flight_incident.py`: the offline reader (§8, with our field names).
> - Flags: `train_lora_modular.py --flight-recorder / --flight-z / --flight-window /
>   --flight-warmup / --flight-max-dumps / --flight-min-gap` (manual:
>   `docs/train_lora_modular.md`).
>
> **Next, only if the recorder shows real batch spikes:** an adaptive clip on the raw gradient
> applied *before* momentum (z-score gradient clipping, cf. ZClip, arXiv 2504.02507 — not yet
> checked against `papers/knowledge.md`). That is the version of this proposal's idea that
> acts where the damage happens.

## 1. Executive Summary & Motivation

In continuous flow matching (CFM) diffusion training over diverse multi-corpus datasets (e.g. SA3 + AVP + Goa Bigset), stochastic batch sampling occasionally presents pathological prompt-target pairings or out-of-distribution latents. 

While **Muon / Spectral LMO** (Newton-Schulz orthogonalisation) constrains each 2D weight matrix's operator norm ($\sigma_{\max}(M) = 1$), the **total composite parameter update norm** across the entire network:
$$S_t = \|\Delta \Theta_t\|_2 = \sqrt{\sum_{k=1}^K \|\Delta W_k\|_F^2}$$
can still experience violent single-step spikes. These spikes are driven by:
*(⚠ Review: largely not so — see the box above. Items 1–3 are bounded by construction: the sign
step is ±lr, EV's multiplier is capped by `--modular-ev-max` and is deterministic, and ColNorm is a
normalisation. None of them scales with how bad a batch is.)*
1. **DoRA magnitude scalar sign updates** responding to steep loss gradients.
2. **Escape Velocity (`--modular-ev`)** multiplying step size by up to $2.5\times$.
3. **ColNorm embedding projections** absorbing noisy conditioning signals.

Under **Schedule-Free averaging** ($x_t = (1 - c_k)x_{t-1} + c_k z_t$), a single outlier shock kicks the fast iterate $z_t$ into an erratic, high-variance loss basin, which permanently contaminates the evaluation iterate $x_t$. 

This proposal designs a **Global Step Governor** that tracks the empirical distribution of step velocity across a rolling window and applies a **single global scalar dampener** to any update that falls within the top 5% (P95) of recent steps.

---

## 2. Empirical Grounding: The 27-Run Checkpoint Library

An audit of all 27 checkpoint trajectory files in `checkpoint-stats/` (247 checkpoint-to-checkpoint transitions across historical LoRA and DoRA runs) reveals a clean separation between healthy training and catastrophic collapse:

> ⚠ **Review — this table mixes units.** `checkpoint-stats/` holds NET displacements between
> checkpoints (~1000 steps apart). Dividing by 1000 does not give a per-step update norm: net
> displacement = path-efficiency × the sum of per-step norms, and path efficiency varies widely
> between runs. So the "Per-Step Update Norm" column is not per-step, and 0.104 is not a per-step
> threshold for anything. The percentiles also pool runs with different lr, rank and length, so
> they describe the pile of data, not a boundary. What IS backed by listening: good runs sat at
> 30–50 per 1k steps, and the rhythm-collapse run at 142 (`docs/train_lora_modular.md`).

| Metric | Per-Step Update Norm $\|\Delta W_t\|$ | Velocity per 1,000 Steps | Audio / Trajectory State |
|---|---|---|---|
| **25th percentile** | `0.00079` | `0.79` | Late-stage fine settling; high cosine alignment |
| **Median (50th %)** | `0.01700` | `17.0` | Steady-state healthy progression |
| **75th percentile** | `0.05461` | `54.6` | Upper bound of clean audition runs (`audition_160ep`) |
| **90th percentile** | `0.08741` | `87.4` | High-energy turning; aggressive feature acquisition |
| **95th percentile** | **`0.10375`** | **`103.8`** | **The Empirical Danger Boundary** |
| **99th percentile** | `0.14997` | `150.0` | **Runaway rhythm collapse** (collapsed run measured at `142.0`) |
| **Exploding runs** | `> 1.000` | `> 1,000.0` | Complete NaN blowouts (`dora128_mix3_nodas`: 7,652; `overnight`: 8,705) |

### Key Takeaways from the Data:
1. Every run judged "clean and good sounding" sat strictly **below $\|\Delta W_t\| \le 0.055$** (55 per 1k steps).
2. The run documented in `docs/train_lora_modular.md` that collapsed rhythm sat at **$142$** per 1k steps ($\|\Delta W\| \approx 0.142$).
3. ~~**The 95th percentile ($\tau_{95} \approx 0.104$) marks the exact threshold between musical coherence and structural degradation.**~~ ⚠ Not supported: see the review note above the table.

---

## 3. Mathematical Foundations: Preserving Geometry & Entanglement

### 3.1 Why Per-Layer / Per-Tensor Dampening Fails
If updates are throttled per-layer (e.g. clipping Layer 12 because it was large while leaving Layer 13 untouched):
* **Layer Synchronization is Destroyed:** In a 24-layer transformer DiT, representations flow sequentially. Unequal dampening alters the relative gain across depth.
* **Gauge Distortion in LoRA/DoRA ($W = W_0 + \frac{\alpha}{r} B \cdot A$):** Squeezing $B$ without squeezing $A$ skews the tangent manifold and accelerates gauge drift (which `lora_gauge_drift.py` measures as wasted orthogonal motion).

### 3.2 The Global Invariance Theorem
To eliminate directional skew, the model's parameters are treated as a single unified vector $\Theta \in \mathbb{R}^P$:
$$\Delta \Theta_t = \begin{bmatrix} \Delta W_1 \\ \Delta W_2 \\ \vdots \\ \Delta W_K \end{bmatrix}$$

We define the global candidate step norm:
$$S_t = \|\Delta \Theta_t\|_2 = \sqrt{\sum_{k=1}^K \|\Delta W_k\|_F^2}$$

Given a dynamic threshold $\tau_t$ (the rolling 95th percentile $Q_{0.95}$):
$$\gamma_t = \begin{cases} 1.0 & \text{if } S_t \le \tau_t \\ \dfrac{\tau_t}{S_t} & \text{if } S_t > \tau_t \end{cases}$$

Every parameter in the network is updated using the **exact same scalar $\gamma_t$**:
$$\Delta W_k^{\text{applied}} = \gamma_t \cdot \Delta W_k \quad \forall k \in [1, K]$$

#### Proof of Direction Invariance:
$$\cos(\Delta \Theta_t^{\text{applied}}, \Delta \Theta_t) = \frac{\gamma_t (\Delta \Theta_t \cdot \Delta \Theta_t)}{\|\gamma_t \Delta \Theta_t\| \|\Delta \Theta_t\|} = \frac{\gamma_t \|\Delta \Theta_t\|^2}{\gamma_t \|\Delta \Theta_t\|^2} = 1.00000$$

The optimizer moves along the **exact same ray in $\mathbb{R}^P$**. It simply shortens the stride when the local landscape generates an outsized shock.

---

## 4. Algorithmic Mechanics: The Rolling Quantile Buffer

### 4.1 Window Lifecycle & Continuous Adaptation
A static threshold cannot account for training cooling down over time: early exploration requires larger steps, whereas late convergence requires tighter tolerances.

* **Buffer:** A circular FIFO array of $N = 500$ (or $1,000$) floats residing in host CPU memory.
* **Phase 1: Cold Start ($t < W_{\text{warmup}}$, e.g. 100 steps):**
  * Accumulate $S_t$ into the buffer.
  * No dampening is applied ($\gamma_t = 1.0$).
* **Phase 2: Continuous Rolling Governance ($t \ge W_{\text{warmup}}$):**
  * At step $t$, push $S_t$ into the FIFO ring.
  * Compute $Q_{0.95} = \text{Percentile}(S_{\text{buffer}}, 95)$.
  * If $S_t > Q_{0.95}$, apply dampening factor $\gamma_t = Q_{0.95} / S_t$.

### 4.2 Computational Overhead: Zero Host-Device Syncs
> ⚠ Review: not zero. Pulling S_t to the host each step IS a sync. (The modular optimizer's
> telemetry already does several `.item()` syncs per parameter, `optimizer.py:592-600`, so the
> marginal cost is small, but the claim is wrong.) And `update_sq` is accumulated AFTER each
> parameter's update has been written (`optimizer.py:547` applies, `:595` measures), so it can't
> gate the step it measures.
Computing $S_t$ can be done entirely on-device:
1. `ModularOptimizer` already tracks `telem["update_sq"]` each step:
   $$\text{update\_sq} = \sum_k \| \eta_k M_k \|_F^2$$
2. Because `telem` is already aggregated, pulling a single 0D scalar to host once per step takes $< 15\,\mu\text{s}$, introducing zero measurable throughput bottleneck.
3. Quantile computation on a 500-element CPU array takes $< 5\,\mu\text{s}$ via `numpy.partition` or quickselect.

---

## 5. Proposed Implementation in `ModularOptimizer`

### 5.1 Step Governor Hook Placement
In `stable_audio_tools/training/modular_opt/optimizer.py`, we introduce the `StepGovernor` class:

```python
class StepGovernor:
    """Rolling-quantile global step velocity dampener.
    
    Ensures that no single step exceeds the 95th percentile of recent
    trajectory velocities, preventing outlier mini-batch shocks without
    skewing parameter update directions.
    """
    def __init__(
        self,
        quantile: float = 0.95,
        window_size: int = 500,
        warmup_steps: int = 100,
        soft_power: float = 1.0,
    ):
        self.quantile = quantile
        self.window_size = window_size
        self.warmup_steps = warmup_steps
        self.soft_power = soft_power
        self.history = []
        self.ptr = 0
        self.is_full = False
        self.last_gamma = 1.0
        self.last_threshold = None

    def update_and_scale(self, proposed_norm: float) -> float:
        if not math.isfinite(proposed_norm) or proposed_norm <= 0:
            return 1.0

        # Maintain FIFO ring
        if len(self.history) < self.window_size:
            self.history.append(proposed_norm)
        else:
            self.history[self.ptr] = proposed_norm
            self.ptr = (self.ptr + 1) % self.window_size
            self.is_full = True

        # Cold-start bypass
        if len(self.history) < self.warmup_steps:
            self.last_gamma = 1.0
            return 1.0

        # Compute empirical quantile
        q_val = float(np.percentile(self.history, self.quantile * 100))
        self.last_threshold = q_val

        if proposed_norm > q_val:
            ratio = q_val / proposed_norm
            gamma = ratio ** self.soft_power
        else:
            gamma = 1.0

        self.last_gamma = gamma
        return gamma
```

### 5.2 Optimizer Integration Flow
> ⚠ Review: this needs exactly the double pass it says it avoids. `ModularOptimizer` writes each
> parameter's update inside the per-parameter loop, before the global norm is known, so one
> global γ requires computing every update first and applying them afterwards.

To apply a single scalar $\gamma$ without a costly double pass:
1. In `ModularOptimizer`, the update direction $M_k$ and group step $\eta_k$ are prepared.
2. The candidate global norm $S_t = \sqrt{\sum_k (\eta_k \|M_k\|_F)^2}$ is evaluated.
3. $\gamma_t = \text{governor.update\_and\_scale}(S_t)$ is evaluated.
4. The writeback to fast iterate $z$ (or $p.\text{data}$) uses $\eta_k' = \gamma_t \cdot \eta_k$.
5. Schedule-Free averaging $x$ consumes the cleanly dampened $z$.

---

## 6. Proposed CLI Flags & Operator Interface

For `stable-audio-3/scripts/train_lora_modular.py`:

| Flag | Default | Type | Description |
|---|---|---|---|
| `--modular-step-governor` | `off` | `flag` | Enables rolling P95 global step dampening |
| `--modular-gov-quantile` | `0.95` | `float` | Target velocity ceiling quantile (e.g. 0.95 = cap top 5%) |
| `--modular-gov-window` | `500` | `int` | Rolling step history window |
| `--modular-gov-warmup` | `100` | `int` | Cold-start steps before dampening engages |
| `--modular-gov-power` | `1.0` | `float` | Dampening severity ($(\tau / S)^p$; 1.0 = exact projection onto ceiling) |
| `--modular-outlier-dump` | `off` | `flag` | Enables the Outlier Flight Recorder (dumps state & mini-batch on P95 events) |
| `--modular-outlier-max-dumps` | `10` | `int` | Max incident snapshots to save per run to prevent disk bloat |

### Telemetry & Audit
When enabled, the mechanism reports directly to:
1. **Console / Log:** `[MECHANISM AUDIT]` reports `ACTIVE` with current $Q_{0.95}$ and lifetime dampening event count.
2. **W&B Metrics:**
   - `comp/governor_scale` ($\gamma_t \in (0, 1]$)
   - `comp/governor_p95_thresh` ($\tau_t$)
   - `comp/raw_step_norm` ($S_t$)
   - `comp/outlier_incident_flag` (1.0 on dumped steps, 0.0 otherwise)

---

## 7. The Outlier Flight Recorder (Black Box Incident Dumper)

### 7.1 Diagnostic Motivation: Why Did the Step Spike?
> **As built (2026-09-25):** the trigger is the RAW GRADIENT norm's robust z-score (or any
> non-finite gradient), not $S_t > Q_{0.95}$, for the reason in the review box. Defaults:
> z > 6 on log-norm, 200-step window, 50-step warmup, ≤5 dumps per run, ≥25 steps apart.
> The dump holds `incident.json` (trigger, per-kind norms, the previous 8 steps, top-15 params by
> grad norm with their share, every item's t / prompt / file) and `batch.pt` (latents, noise, t;
> big tensors as fp16). NOT dumped: optimizer state (§7.2 B.3). It's hundreds of MB, and the
> nearest checkpoint already carries it.
In multi-corpus CFM diffusion training, gradient spikes are often dismissed as generic "stochastic noise." However, empirical observation reveals that **even at high trajectory velocity, spikes do NOT happen on every batch**. 

When an update spikes into the 95th percentile ($S_t > Q_{0.95}$), it is driven by one of four specific root causes:
1. **Prompt / Caption Pathology:** A specific token sequence, unusual character syntax, or empty prompt that blows up the text conditioner embedding projection.
2. **Latent Dynamic Range Outlier:** A specific audio slice with clipped transients, DC offset, or extreme amplitude where latent standard deviation spikes ($\sigma > 1.8$).
3. **Flow-Matching Timestep Boundary:** ~~A sample noised at the extreme boundaries ($t \to 0$ or $t \to 1$), where velocity target $v_\theta = \frac{x_t - (1 - t)x_0}{t}$ experiences steep derivative tangents.~~ ⚠ Review: not our objective. SA3 trains rectified flow with target $v = \varepsilon - x_0$, which has no division by $t$ and no boundary singularity. A timestep cluster can still matter (loss scale differs across $t$), which is why the recorder logs every item's $t$, but not by this mechanism.
4. **Isolated Layer Failure:** A single DoRA magnitude scalar crossing near zero, or an attention projection matrix undergoing acute curvature collapse.

Without capturing the state at the exact moment of the incident, post-mortem debugging is reduced to speculation.

### 7.2 Architecture & Memory Management

To maintain continuous forensic visibility with **zero impact on normal training throughput**:

```
[Forward / Backward Step t]
           │
           ▼
[Evaluate Step Norm S_t]
           │
     S_t > Q_0.95?
     ├── NO  ──> [Push S_t to Rolling Window] ──> Normal Step Execution
     └── YES ──> [TRIGGER FLIGHT RECORDER DUMP]
                      │
                      ├── 1. Capture Offending Mini-Batch (CPU RAM copy)
                      ├── 2. Snapshot Previous K=3 Step Metrics
                      ├── 3. Attribute Per-Layer Norm Contributions
                      └── 4. Dump Incident Bundle to Disk (<run_dir>/incidents/)
```

#### A. Rolling In-Memory Ring Buffer (CPU Host Memory)
The trainer maintains a lightweight circular FIFO buffer of the last $K = 3$ steps in host RAM:
* **Mini-batch Tensors & Metadata:** Input latents (`~1 MB`), conditioning dictionary, text prompt strings, and timesteps $t$.
* **Step Telemetry:** Step index, loss value, loss components (`mse_signal`, `var_barrier`), learning rate, and global gradient norm.
* **Storage Cost:** Storing 3 batches in host RAM requires $< 15\,\text{MB}$, having zero impact on GPU VRAM.

#### B. The Incident Bundle Disk Dump
When $S_t > Q_{0.95}$ (capped by `--modular-outlier-max-dumps`, default 10 per run):
The flight recorder writes an incident directory: `<run_dir>/incidents/incident_step_{step}/` containing:

1. **`incident_report.json`:**
   * Step index, timestamp, calculated $\gamma_t$, proposed norm $S_t$, dynamic threshold $Q_{0.95}$.
   * Complete text prompt strings for all items in the batch.
   * Timesteps $t \in [0, 1]$ for every item in the batch.
   * **Layer Attribution Ranking:** Sorted list of the top 10 layers contributing the most squared norm $\sum \|\Delta W_k\|_F^2$ to the spike, detailing whether the spike was driven by DoRA magnitude scalars, spectral matrices, or AdaLN projections.
2. **`minibatch.pt`:**
   * Exact `noised_inputs`, `t`, `cond_dict`, and attention mask.
   * *Utility:* Allows instant, deterministic offline replay of the exact forward/backward pass in an isolated Python script without re-running training.
3. **`optimizer_state.pt`:**
   * Snapshot of the optimizer state dict at step $t$ (momentum buffers $V$, fast iterate $z$, NorMuon scaling vectors $r_n$, and Preconditioner covariance matrices $C$).
   * Rolling history of the preceding 3 steps' velocity and loss values.

---

## 8. Offline Forensic Tooling: `eval/inspect_outlier_incident.py`

Alongside the recorder, a lightweight offline inspection script reads any incident dump and prints an immediate executive diagnosis:

```bash
python eval/inspect_outlier_incident.py /run/media/kim/Mantu/sa3_lora_runs/MYRUN/incidents/incident_step_1268
```

Output format:
```text
================================================================================
OUTLIER INCIDENT REPORT: Step 1268 (Severity: 2.14x above P95 threshold)
================================================================================
Proposed Step Norm: 0.2218  |  P95 Threshold: 0.1038  |  Dampening Scale: 0.4680
Previous 3 Step Norms: [0.0182, 0.0165, 0.0210]

[BATCH INSPECTION]
  Batch Size: 16  |  Timestep Mean: 0.082 (MIN: 0.004, MAX: 0.312)
  --> WARNING: 6 of 16 items clustered near t < 0.02 boundary!
  Prompts in Batch:
    [0] '1990s goa trance, melodic acidic lead, 142 bpm'
    [1] '2000s psy-trance, driving bassline, full-on goa'
    ...

[LAYER ATTRIBUTION: TOP CONTRIBUTORS]
  1. model.transformer.layers.23.ff.ff.0.proj.lora_B:  38.4% of total update norm
  2. model.transformer.layers.22.ff.ff.0.proj.lora_B:  21.2% of total update norm
  3. model.transformer.global_cond_embedder.2.lora_B:  14.6% of total update norm
  All other 226 layers combined:                       25.8% of total update norm

Diagnosis: Timestep boundary cluster at t < 0.02 triggered acute gradient surge
in deep feed-forward projections (layers 22-23). Successfully dampened to P95.
================================================================================
```

---

## 9. Next Steps for Tomorrow
> ⚠ Superseded by the review box at the top: governor not adopted; recorder and inspector built
> (`stable_audio_3/training/flight_recorder.py`, `eval/inspect_flight_incident.py`,
> tests `stable-audio-3/tests/test_flight_recorder.py`). The original list follows for the record.

1. **Quantile Dampener Architecture:** Review the mathematical formulation and quantile window sizing ($N=500$ vs $1,000$).
2. **Flight Recorder Hook:** Confirm incident snapshot directory structure and max dump limits (e.g. 10 dumps per run).
3. **Implementation Plan:**
   - Add `StepGovernor` and `OutlierFlightRecorder` to `stable-audio-tools/stable_audio_tools/training/modular_opt/optimizer.py`.
   - Wire batch caching into `stable-audio-3/scripts/train_lora_modular.py`.
   - Add `eval/inspect_outlier_incident.py` for automated incident post-mortems.

