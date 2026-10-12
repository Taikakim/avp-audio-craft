# MuseTimbre: Zero-Shot Timbre Transfer by Controlling a Frozen Music Generator (2609.30548v1)

Cheng (Georgia Tech) and Duan (Rochester AIR Lab). arXiv v1 24 Sep 2026, 4 pages. Code (MIT) and weights
(MIT, 1.7 GB, trainable modules only): `barry-mir/muse-timbre`, local clone `/home/kim/Projects/muse-timbre`.
Built on **Stable Audio 3 Medium (base)**, i.e. our backbone. PDF beside this note. **Read by THE-FINN
2026-10-13**: paper text for claims and numbers, README and `musetimbre/model.py` + `infer.py` for the code.
Not run.

## What it does
Re-voices a source recording (or a MIDI score) in the timbre of a reference clip, with the SA3 backbone, its
autoencoder and its text conditioner all frozen. About 420 M trainable parameters in two plug-in modules:
- **Pitch:** Basic Pitch transcription (or MIDI) -> 176-channel binary roll (88 note + 88 onset, ~10.77
  frames/s) -> 5-layer 1-D CNN -> zero-init decoupled cross-attention in every DiT block, **rotary embeddings
  on Q, K and V**, query positions rescaled onto the roll's timeline (`q_pos = i * T/N`).
- **Timbre:** LAION-CLAP music audio tower (HTSAT-base) on the raw reference -> one 512-d vector -> MLP ->
  per-block zero-init **post-block AdaLN** scale/shift. The CLAP encoder is **fine-tuned end to end** at
  lr 1e-5 (adapters 1e-4).
- **Training:** 250k steps, batch 16, AdamW, 1000 warmup + cosine. Reference = a disjoint crop of the same
  recording (`diffclip` option: a different window), so it shares the instrument but not the notes. Data =
  50/50 mix of real stems (MoisesDB, URMP) and **rendered MIDI** through many SoundFonts with GM-program
  substitution (exact roll, wide timbre range), each corpus weighted equally.
- **Guidance:** mutually exclusive dropout draws (both 10 %, timbre only 20 %, pitch only 20 %); pitch
  dropout is either the whole roll or a **random temporal span**. Inference
  `v = v_u + lp(v_p - v_u) + lt(v_t - v_u)`, lp = lt = 2, 25 Euler steps (~1 s per 5 s clip, RTX 5090).
  A text prompt is a third separately guided branch.
- **Code details worth knowing:** the new K/V projection is **warm-started from the block's frozen text
  cross-attention `to_kv`**; conditions are passed through instance attributes so one set of patched blocks
  serves all guidance branches; activation checkpointing is switched off because the backbone is frozen.

## What it shows (304 pairs, four held-out datasets, different instrument and dataset per pair)
- Timbre match (PaSST family-level top-1) **57.6 %** at melody frame-F1 **0.316**. Audio-reference baselines
  CTD 48.7 %, SS-VQ-VAE 45.4 %. TokenSynth-A (CLAP audio) has higher F1, 0.380, but 34.6 % timbre match.
  Ceilings: reference clips 88.5 % PaSST, transcribing the true source 0.540 F1. So pitch preservation is
  NOT the best of the field.
- Module ablation (double dissociation): no timbre module -> 16.1 % timbre match (chance 11.8 %); no pitch
  module -> 74.7 % timbre match, F1 0.041.
- Fine-tuned CLAP as a pitch-robust timbre encoder: top-1 retrieval at pool size 256 rises from 0.53 (frozen
  CLAP) to **0.88**, far above AST, MERT, Music2Latent. Synthetic renders only; the authors leave real-audio
  timbre-similarity evaluation to future work.
- Listening test (20 musically trained listeners, 10 clips, MUSHRA-style): timbre 2.6 vs TokenSynth-A 2.4
  (small margin), CTD 1.4, SS-VQ-VAE 1.1; fidelity 2.5 vs 2.6; TokenSynth-A leads on pitch (3.4).

## Not ablated in the paper
RoPE on Q/K/V, the K/V warm start, the temporal-span pitch dropout, and AdaLN-versus-cross-attention for timbre
are design choices with no isolating experiment. Any gain from adopting them is untested, here or by us.

## For us (project POV)
We already have the same family: `control/sa3_control` decoupled cross-attention adapters (MuseControlLite
style, the paper's ref [1] and baseline), an audio-reference riffer on a different crop of the same track,
independent per-source dropout with multi-source guidance (`train.py --melody-dropout`,
`--metrical-dropout`), trainable-only checkpoints, and `--no-checkpoint`. Candidate adoptions, cheapest
first, all UNTESTED:
1. **RoPE on the control cross-attention** with query positions rescaled to the control timeline, as an A/B
   against our additive `add_fractional_positions` (`adapters.py:79`) on a time-aligned adapter (melody,
   contour, onset).
2. **K/V warm start** from the frozen text cross-attention weights (one line; may soften the
   "reference-specific only at lr 1e-4, then elbow" behaviour).
3. **Random temporal-span dropout** of the control signal, so a control is followed where present and free
   elsewhere (contour / melody training).
4. **Pitch-robust fine-tuned CLAP reference encoder** with disjoint-note pairs as an alternative reference
   branch; relevant while the morph/adherence instruments fail their gates (`eval/morph_*`). Also a possible
   timbre-similarity metric next to MERIT and the Thoret 2021 metric (`Thoret 2021` note), once checked on
   real audio.
5. **Rendered-MIDI data recipe** (many sounds per MIDI, exact roll): our Surge pipeline
   (`synth_inversion`) and the DAWproject tick-exact ground truth (`DAWPROJECT.md`) could build paired data
   for the pianoroll arm that D14 had to drop (needs the conditioning inlet, `docs/INFERENCE-SURFACE.md`).
Licence: SA3 backbone under the Stability Community License (commercial use restricted), which we already
work under; code and weights MIT.
