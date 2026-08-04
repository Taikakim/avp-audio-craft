# What Kim wanted to know

*A running archive of substantive Q&A — worked explanations that would otherwise be lost when a
session's context is compacted. Not a user FAQ: these are Kim's real questions and the full answers,
kept so the reasoning persists. Append, don't prune. (Renamed from FAQ.md, 2026-08-05.)*

---

Why does the output start to sound like ringing spectral bands when we're applying too much steering?

Short version: ringing-then-noise is the signature of amplitude-driven off-manifold extrapolation, and the optimizer is a real but
      second-order modulator of where that threshold sits and how the artifact looks — not the root cause.
      
      Why ringing bands appear first (before noise)
      
      The adapter is additive in the attention output: base + gain·adapter(ctrl). It was trained so that at gain ≈ 1 the edit direction
      lands the latent in-distribution. Turning gain up is extrapolating a roughly-linear learned direction beyond the scale it was fit at
      — you're not asking for "more of a valid thing," you're walking the latent off the SAME manifold along a fixed-ish vector.
      
      Three things make the first failure structured (banded) rather than random:
      
      1. The error accumulates coherently. In rectified flow the adapter biases the velocity field the same way at every ODE step, so the
      displacement integrates in one consistent direction. Coherent bias → structured off-manifold latent, not stochastic scatter.
      Structured cause → structured artifact.
      2. The SAME decoder over-drives specific spectral modes. A large, roughly-coherent latent perturbation pushed through the decoder's
      upsampling stack excites a few dominant resonances / the transposed-conv periodicities (the classic comb/checkerboard tendency of
      upsampling decoders when driven hard). A periodic structure in time = line/banded spectrum → audible "ringing." The decoder still
      imposes some learned structure here, so you get tonal bands, not hash.
      3. For onset-density specifically, "denser" saturates into a carrier. Asking for ever-higher event rate eventually can't resolve
      into discrete transients; the injected periodic energy collapses into a sustained periodic modulation — which is a line spectrum. So
      over-driven density control naturally tends toward banding before chaos.
      
      Push gain further and the latent goes so far off-manifold the decoder loses coherence entirely → the structured resonance breaks
      down into broadband noise. Structured-artifact-then-noise is the textbook progression of over-amplifying a single direction.
      
      Does the optimizer matter? Yes — but to the threshold and texture, not the existence
      
      It genuinely affects this, because it shapes the geometry of the learned edit direction, and we measured that directly: FusionOpt
      and AdamW converged to different solutions (the conditioner cosine ~0.45 between them, and fusion learned flatter per-layer norms).

      - NorMuon/Muon (in the fusion stack) normalize update geometry per-neuron + spectrally, biasing toward more isotropic, balanced
      weight matrices. That tends to spread the control contribution across more modes → energy isn't concentrated in one resonance →
      plausibly a higher/cleaner gain ceiling before ringing, and when it does break, a more diffuse texture.
      - AdamW lets a few directions dominate (per-parameter adaptive scaling), giving a spikier, lower-effective-rank edit direction →
      amplifying it concentrates energy into fewer spectral modes → sharper banding, onset at lower gain.

      So which optimizer you pick can move where the clean range ends and change whether over-steer reads as tonal banding vs broadband
      grunge — which is consistent with your two long runs tracing very different gnorm trajectories and likely having different clean
      operating envelopes.
    
      But the fundamental cause is the additive over-amplification + the decoder's off-manifold response, not the optimizer. Any optimizer 
      that learns one useful control axis will ring when you drive that axis past its trained scale. The optimizer (and LR/warmup) tunes
      the headroom and the failure's character; the gain amplitude and SAME's decoding behavior set the mechanism.

What exactly happens in the MuseControlLite-style models:

The trajectory data is in, and it directly answers your questions — better than I expected. Here's what the three LR runs reveal:
  
  ┌───────────────┬───────────────────────┬─────────────┬────────────┬──────────────────┬──────────────┬────────────────┐
  │      run      │ net disp. ‖W_last−W₀‖ │ path length │ efficiency │ velocity ep2→end │ global norm  │   cos→final    │
  ├───────────────┼───────────────────────┼─────────────┼────────────┼──────────────────┼──────────────┼────────────────┤
  │ lr2e5 (40 ep) │ 25.5                  │ 36.6        │ 0.70       │ 3.05 → 0.63      │ 157.6 (flat) │ →1.000 by ep31 │
  ├───────────────┼───────────────────────┼─────────────┼────────────┼──────────────────┼──────────────┼────────────────┤
  │ lr8e5 (10 ep) │ 25.1                  │ 33.0        │ 0.76       │ 5.84 → 2.70      │ 157.5 (flat) │ →1.000 by ep6  │
  ├───────────────┼───────────────────────┼─────────────┼────────────┼──────────────────┼──────────────┼────────────────┤
  │ lr1e4 (~1 ep) │ 8.9                   │ 10.8        │ 0.83       │ (short run)      │ 157.6 (flat) │ →1.000         │
  └───────────────┴───────────────────────┴─────────────┴────────────┴──────────────────┴──────────────┴────────────────┘
  
  Three facts jump out:
  1. lr2e5 and lr8e5 reach the same net displacement (~25) in the same direction (cos→final →1.0) — lr8e5 just gets there in ¼ the steps.
  The destination is LR-invariant; LR only sets the speed. This is the "Flux lesson" confirmed in weight space.
  2. It's directed drift, not wandering and not stuck. Efficiency 0.70–0.76 + cos→final climbing straight to 1.0 = the head moves
  consistently toward one attractor. Velocity decays smoothly but never hits zero (lr2e5 still 0.63/epoch at ep40) — not converged, not
  oscillating.
  3. Constant global norm (~157.6) the whole way — the weights rotate/redistribute on a fixed-norm shell, they don't grow.
   
  Now reconcile with the eval: control authority peaks ~ep24 then declines, while the weights march steadily toward the (loss-defined) final
  point. So the control sweet spot is a bump partway along an otherwise-monotonic descent — the model keeps moving past it toward an
  attractor that the RF loss likes but that has worse control. The training objective is misaligned with the goal.
   
  Your three questions, answered by the data
   
  "Could we still train at a lower LR?" — No, it won't help. The destination is LR-invariant (lr8e5 and lr2e5 land in the same place); a
  lower LR just traverses the same path more slowly and still overshoots the ep24 control peak, only later. You'd burn steps for nothing.
  The issue is where you stop, not how fast you move. 
   
  "Higher LR + damping?" — Yes, this is the right instinct, and the data backs it. Higher LR is strictly more efficient (same destination, ¼
  the steps). The "damping" that matters is EMA / weight-averaging, because the centroid checkpoint is ep20 (lr2e5) / ep5 (lr8e5) — i.e.
  the natural soup-center sits right next to the ep24 control peak. So averaging should land near the sweet spot automatically. (That's
  exactly what the queued soups will test.)
   
  "Overtraining stuck in a minimum?" — Not a minimum, and not "stuck": velocity never reaches zero, so it's still moving. It's directed 
  overshoot of a mid-trajectory optimum under a misaligned/uninformative loss — the RF loss can't see control authority, so the optimizer
  drifts past it. Classic "overfitting/stuck-minimum" framing doesn't fit; "objective misalignment → drift past the incidental sweet spot"
  does.
   
  The recipe this implies 
    
  - Don't lower the LR. Go higher (faster, same place) + one of: (a) eval-based early stop at the control peak (you can't read it from loss
  — must generate+measure every N epochs), or (b) EMA/weight-averaging as cheap insurance that needs no eval. The soups are the post-hoc
  proof of (b); if a centroid-ish soup beats single-ckpt ep24 on Audiobox, bake EMA into future training.
  - Bonus from the per-layer data: the FiLM scalar→token map (conditioner.film.2) is the single most-moving component across all LRs — it
  never stops adapting. (Noting, not interpreting — that's the point of the library.)
   
  Everything's running: 8 soups queued (auto-eval after Phase 1, ~now on step86400/16), trajectory library + standing guideline in
  SAO/checkpoint-stats/ + MASTER.md. Once the soups finish I can run a proper adversarial/literature-grounded analysis of the
  EMA-vs-early-stop recipe with the averaging evidence in hand — but the weight-space data already says lower-LR is the wrong direction.
   
   
how should I read the traj/velocity, traj/path_len, traj/path_efficiency and traj/net_disp grahps?   
      
      Good question — these four are all derived from one idea, so once you have the mental model they're easy to read.

  The mental model

  Picture all the trainable weights as a single point moving through a huge space (119.6 M dimensions here). Training is a journey from the
  start point W0 to wherever it ends. Every checkpoint (5,400 steps) I measure the journey. The walking analogy makes all four obvious:

  ┌─────────────────┬─────────────────────────────────────────────────────────┬─────────────────────┐ 
  │     metric      │                     walking analogy                     │       formula       │
  ├─────────────────┼─────────────────────────────────────────────────────────┼─────────────────────┤
  │ net_disp        │ how far you are from home, as the crow flies            │ ‖W_now − W0‖        │
  ├─────────────────┼─────────────────────────────────────────────────────────┼─────────────────────┤
  │ path_len        │ your odometer — total distance actually walked          │ Σ velocity          │
  ├─────────────────┼─────────────────────────────────────────────────────────┼─────────────────────┤
  │ velocity        │ how far you walked in the last leg (your current speed) │ ‖W_now − W_prev‖    │
  ├─────────────────┼─────────────────────────────────────────────────────────┼─────────────────────┤
  │ path_efficiency │ did you walk straight or wander? (1 = straight line)    │ net_disp / path_len │
  └─────────────────┴─────────────────────────────────────────────────────────┴─────────────────────┘
  
  How to read each curve's shape
  
  - velocity — the "speed." Decaying = settling (big moves early, smaller as it homes in — what you want). Flat/high = never settling
  (drifting at full speed). Spikes = instability.
  - net_disp — distance from the init model. Rises then plateaus = converged (found a region, staying there). Rises forever (linear) = 
  hasn't found a home.
  - path_len — always climbs (you can't un-walk). The useful bit is its slope = velocity: steep = moving fast, flattening = slowing.
  - path_efficiency — directedness, 0→1. High & stable (~0.7–1) = going somewhere. Declining toward 0 = increasingly wandering. Note: some
  decline is normal (any curved path drops below 1; a pure random walk → ~1/√N), so read the level and whether the decline stalls, not the
  raw drop.
  
  Read them together — that's where the diagnosis is
  
  - Clean convergence (ideal): velocity → 0, net_disp plateaus, efficiency high & flat. "Walked straight to a spot and stopped."
  - Settling-but-wandering ← our run: velocity decaying, net_disp plateauing, efficiency declining-but-slowing. "Meandered a bit but slowing
  down and homing in." Converging, just not in a straight line.
  - Drift / never-settle ← Fusion + the collapse signature: velocity flat-high, net_disp linear (no plateau), efficiency sliding steadily.
  "Walking full speed forever down a curving path — never arrives." This is what we tied to control-authority collapse.
  - Instability: velocity spikes, net_disp lurches.
  
  Two reading caveats
  
  - The first point is inflated. The adapters start at zero, so the first leg (velocity 26.9 = net_disp) is the big from-zero jump. The
  "real" settled speed is the later values (14 → 11 → 10).
  - Absolute numbers are only relative. velocity ~10, net_disp ~34 mean nothing alone — compare them to each other and across runs, not to a
  fixed scale.
  
  So for the live run
  
  velocity decaying (14→11→10) + net_disp decelerating (→34) = it's settling — the thing Fusion never did. The efficiency sliding to 0.54
  says the path curves, but the shrinking velocity means that slide will slow rather than run to zero. What to watch as it finishes: does
  velocity keep heading toward 0 (full settle) or flatten at a floor (residual drift)? Does net_disp flatten? Does efficiency stabilize or
  keep dropping? Those answers at ep40 are the real verdict. 
  
What are the whist, ghist, wnorm and gnorm_layer graphs, and how to read them? 

      These four are a clean 2×2: weights vs gradients, each as a norm (one number — the size) or a histogram (the full distribution — the 
  shape). Logged per layer (77 trainable tensors here).

  ┌───────────┬─────────────────────────────┬─────────────────────────────────────────────────┐
  │           │ norm = how big (line graph) │ histogram = how distributed (heatmap over time) │
  ├───────────┼─────────────────────────────┼─────────────────────────────────────────────────┤
  │ weights   │ wnorm/<layer>               │ whist/<layer>                                   │
  ├───────────┼─────────────────────────────┼─────────────────────────────────────────────────┤
  │ gradients │ gnorm_layer/<layer>         │ ghist/<layer>                                   │
  └───────────┴─────────────────────────────┴─────────────────────────────────────────────────┘

  The norm answers "how large," the histogram answers "in what shape" — two layers with the same wnorm can have totally different
  distributions (one tidy bell, one a few huge outliers), and only the histogram shows it.

  The two norms (line graphs)

  wnorm/<layer> — size of each layer's weights.
  - Rising = the layer is learning (moving away from init). Our zero-init to_out adapters grow from ~0 as they learn to inject control.
  - Flat = not changing (converged, or effectively frozen). 
  - Sudden jump = instability. It's the per-layer version of global/wnorm.

  gnorm_layer/<layer> — size of the gradient hitting each layer. This is the "where is the learning signal" map.
  - Healthy, non-zero = actively being pushed.
  - Near-zero = no signal — a dead/frozen layer not contributing (for an adapter, it means that layer isn't doing control work).
  - Decaying over training = that layer is converging.
  - Step-to-step bounce is normal (per-batch noise); a spike is a warning (exploding gradient).
  - The most useful combo is gnorm_layer / wnorm (I also log it as g_over_w) = relative push — a big layer with a big gradient may be moving
  less than a small layer with a small one.

  The two histograms (heatmaps over time)

  wandb renders these as a heatmap: x = step, y = value bins, brightness = how many weights/grads sit in that bin. Read the evolution of the
  shape.

  whist/<layer> — distribution of weight values.
  - Usually a blob centered near 0 with tails.
  - Spreading/widening over time = healthy learning (diversifying from the tight init). Zero-init to_out starts as a spike at 0 and fans
  out.
  - Watch for pathologies the norm hides: piling up at the extremes (saturation), splitting bimodal, or collapsing to a single value (dead
  units).

  ghist/<layer> — distribution of gradient values.
  - Should be a roughly symmetric blob around 0 (gradients push both ways); its width = signal strength.
  - Collapsing to ~0 = vanishing gradient (layer going dead). Huge outliers = exploding (instability). A persistent nonzero mean = the layer
  being systematically driven one direction.
  - Narrowing as training proceeds = converging.

  Reading them together — the diagnoses

  - Dead/idle layer: gnorm_layer ≈ 0 + whist static. (Our 24.film.0, 24.tokens look like this.)
  - Actively learning: gnorm_layer healthy + wnorm rising + whist spreading. (Our late-layer to_out 18–22, the second FiLM.)
  - Instability: gnorm_layer spikes + ghist outliers + wnorm jumps.
  - Converged/settling: gnorm_layer decaying + wnorm plateauing + whist/ghist stop changing.

  What ours shows

  The pattern matches the trajectory story: the late-layer to_out adapters + the second FiLM have rising wnorm, live gnorm_layer, and
  spreading whist (the control machinery), while the input FiLM and token embeddings sit with near-zero gradients and static histograms (not
  pulling their weight). If you want a quick health scan, the single best panel is gnorm_layer/* grouped — one glance tells you which
  layers are alive, which are dead, and whether anything is spiking.

What does the "size" of layer weights mean? What does it mean when a layer's gnorm is rising? Also, what are the .to_out_weight, to_k_weight and to_v_weight grahps?

      ● Three good questions, and they connect. Let me take them in order.

  1. What the "size" (norm) of a weight tensor means

  The norm is sqrt(sum of all the weight values²) — one number for the overall magnitude of every number in that matrix. Think of each
  weight matrix as an amplifier/knob on the signal passing through it:
  - Bigger norm = a stronger transformation — the layer scales/influences its input more.
  - Norm ≈ 0 = the knob is off — it multiplies its input toward zero, so the layer has essentially no effect.

  This is why it matters for our adapters specifically: to_out is zero-initialized, so its norm starts at ~0 — the adapter literally does
  nothing at step 0 (output = base + 0·adapter). When you see its wnorm grow from zero, that's the adapter turning on — going from
  "contributes nothing" to "actively injecting control." So for our layers, weight-size ≈ how switched-on that piece is.

  (Caveat: the norm only tells you the strength of the transformation, not its direction — which inputs map to which outputs. But the trend
  up/down is the useful signal.)

  2. What a rising gnorm means (e.g. gnorm_layer/19.to_k.weight)
                                                        
  gnorm is the norm of the gradient w.r.t. that layer — i.e. how hard the optimizer is currently pushing to change it. Big gradient = "the
  loss really wants this layer different."
  
  The key intuition: you normally expect gnorm to decay as a run converges (the landscape flattens → smaller pushes → the layer settles). So
  a rising gnorm is notable, and usually means one of:
  - (most likely here) the layer is becoming more engaged — as the adapters switch on (their to_out norms grow), the control pathway becomes
  active, so more gradient now flows through its key/value projections. The learning is shifting toward that layer.
  - a coupling effect — as the weights grow, the layer's outputs get larger, which can enlarge the gradients too.
  - (only if it keeps climbing and spikes) early instability.
  
  So gnorm_layer/19.to_k.weight rising reads as: layer-19's control adapter is getting more learning signal over time — its key projection
  is being actively refined as the control mechanism comes alive. That's consistent with what we already saw (the late layers 18–22 are the
  active control machinery). It's healthy unless it turns into spikes.

  3. What to_k, to_v, to_out are

  These are the three pieces of the decoupled cross-attention adapter we add to each DiT layer. Attention works in Q / K / V terms:
  - Query (Q): "what am I looking for?" — comes from the DiT's own hidden state.
  - Key (K): "what's on offer to attend to?"
  - Value (V): "the actual content I'll pull in."
  - Attention matches Q against K (how much to attend where), pulls a weighted sum of V, then projects the result out.

  In our adapter the control conditioning (the onset-density tokens) is fed in as its own K and V (that's the "decoupled" part — separate
  from the base model's attention):
  - to_k.weight — projects the control signal → Keys: learns which aspects of the control to make addressable.
  - to_v.weight — projects the control signal → Values: learns what content to actually inject from it.
  - to_out.weight — projects the attention result back into the DiT's residual stream. Zero-initialized, so it's the adapter's gate/volume 
  knob: 0 = adapter silent, growing = adapter writing into the model.

  Final per layer: hidden = base_attention + gain · to_out( attention( Q_base, to_k(control), to_v(control) ) ).

  So as a set: to_k/to_v learn what to read from the control signal; to_out controls how much gets written back. Reading them: to_out
  growing tells you the adapter is active (and where — late layers, in our run); to_k/to_v moving (and their rising gnorm) tells you the
  adapter is refining what in the control signal it keys on and injects. 19.to_k rising is exactly that layer learning to sharpen what
  control features it attends to.



