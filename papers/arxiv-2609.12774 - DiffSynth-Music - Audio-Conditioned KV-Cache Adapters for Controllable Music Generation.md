# DiffSynth-Music: Audio-Conditioned KV-Cache Adapters for Controllable Music Generation (2609.12774v1) — read by THE-FINN 2026-10-26

Zhongjie Duan, Shengchuan Gao, Hong Zhang, Yingda Chen (Alibaba Group; Shanghai Jiao Tong University), v1 dated 11 Sep 2026. PDF: `arxiv-2609.12774 - DiffSynth-Music - Audio-Conditioned KV-Cache Adapters for Controllable Music Generation.pdf`.
**Read:** all 10 pages. Models: modelscope.cn/models/DiffSynth-Studio/DiffSynth-Music (not downloaded). Built on the authors' Diffusion Templates plugin framework (arXiv 2604.24351, not read).
Not the same Duan as MuseTimbre (2609.30548, Rochester).

## What it contains
- **Backbone** ACE-Step-1.5-XL-SFT, frozen (text encoder, VAE, generation DiT). Flow matching, linear noise-to-data path.
- **Three "template" modules** (Control, Prosody, Reference), each a copy of the backbone DiT initialised from its weights, with separate parameters. A template reads the control audio's latent from the SAME VAE as the target, so targets and controls share one latent space.
- **KV injection.** At each injected block the template's keys and values are concatenated with the generation branch's along the token axis; one softmax over both; only generation queries give outputs. Time-aligned controls keep temporal correspondence with the output; the reference excerpt keeps only its internal order. Control and generation lengths may differ.
- **One-off cache.** Control audio is clean, so the template timestep is fixed at the clean end and its other inputs are held constant; the KV cache is computed once before sampling and reused at every step.
- **Composition.** Several controls are active at once by concatenating their caches in a fixed order (memories combined, not waveforms). Example given: accompaniment + prosody for a cover with a new vocal timbre. Not evaluated.
- **Control signals** (from ~60k private recordings):
  - Beats: Essentia Degara tracker, rendered as 10 ms decaying 1 kHz pulses (timing without drum timbre or subdivisions).
  - Vocals / accompaniment: Demucs (Hybrid Transformer).
  - Prosody: pYIN f0 over 65-1000 Hz (hop 512), forward-filled and interpolated; sine carrier with an envelope from rectification + 4th-order 30 Hz and 2nd-order 80 Hz zero-phase low-pass, peak-normalised; no voicing mask. Keeps pitch and timing, reduces words and timbre (not guaranteed).
  - Reference: the loudest contiguous 10 s of the mix.
- **Eval:** 100 songs (50 English from MUSDB18-HQ, 50 private Mandarin), prompts and lyrics from Qwen3-Omni; CFG 4, 50 steps. Each control tested ALONE.

  | | Beat-F1 | Cemgil | V-MSE | PER | A-MSE | Pitch50 | MuLan-A |
  |---|---|---|---|---|---|---|---|
  | ACE-Step backbone | 0.3031 | 0.1983 | 0.0158 | 0.1928 | 0.0221 | 0.0366 | 0.6836 |
  | DiffSynth-Music | 0.8496 | 0.8088 | 0.0006 | 0.1451 | 0.0023 | 0.4671 | 0.8088 |

  Quality (AudioBox CE/CU/PC/PQ, MuLan-T) against the backbone 7.37/7.70/6.43/8.10/0.402: Beats and Reference raise CE, CU and PQ (PQ 8.22, 8.24); Vocals is lowest (CE 7.10, PQ 8.06); PC falls for every control (6.01-6.41); MuLan-T falls for every control (0.345-0.390).
- **Not in the paper:** training steps, lr, batch, compute; which blocks are injected; whether templates are fully trained; the loss weight w(t); how CFG handles the control; quality at step 0; joint-control results; listening tests (all deferred to future work).

## FOR US — is it useful?
1. **New to us: control AUDIO through a DiT-initialised encoder.** Our control kit and B7 feed hand-made MIR curves or chroma through small fresh encoders (decoupled cross-attention or an additive inlet); B6 chroma melody turning was 0/12. A template that starts out as SA3 itself already reads SAME latents.
2. **Cheap control recipes.** The click track and the pYIN sine-prosody are trivial to build from our `.BEATS_GRID` files and f0 tools; the sine is a direct candidate for the melody wall (lead f0 from `other`, or clean from Kim's studio `leads`).
3. **The one-off KV cache** makes the sampling cost of a control almost nothing, unlike guidance (LatCH) which runs every step.
4. **SA3 fit.** medium-base is 24 blocks, width 1536, 24 heads, 64 memory tokens, joint self-attention with RoPE, so time-aligned controls can take the generation tokens' positions.
5. **Cautions for a port.** KV concatenation changes the softmax before training, so it is not a zero-init no-op: add a gate that starts closed. Evaluation is circular (Demucs builds the control and re-separates the output to score it); score ours with a different separator and beat tracker. Table 1 baselines get no control, so their columns are chance levels. Cemgil and MuLan-A both read 0.8088 for DiffSynth-Music, likely a typo.
6. **Data.** Their ~60k recordings against our ~4.5k `Goa_Separated` tracks with stems (plus 12.5k bigset crops that would need separation) is not a decisive gap with crops; we also have better drum stems (BS-RoFormer SW) and Kim's 40 clean studio multitracks for held-out evaluation and the only clean bass.
- **Verdict:** a sound, simple design with thin evidence (no ablations, no training details, single-control automatic metrics only). Worth a staged port: training-free KV-injection probe first, then a base + DoRA template with a closed gate. Plan filed as **EXPERIMENTS B14**.
- **Leads it cites, unchecked:** Diffusion Templates (2604.24351); JASCO (2406.10970, information bottleneck and temporal blurring for controls); Music-ControlNet (Wu et al. 2024); IP-Adapter (2308.06721).
