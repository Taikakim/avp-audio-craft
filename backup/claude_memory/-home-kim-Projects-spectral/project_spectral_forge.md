---
name: Spectral Forge — project state
description: Spectral compressor CLAP plugin project goals, design decisions, and current status
type: project
originSessionId: 5d082542-d7a8-48f9-b040-f070d5860fe2
---
**What it is:** A spectral toolkit meant for expandability over a modular architecture. CLAP plugin for Linux/Bitwig. Soothe-style spectral compressor with per-bin compression across 1025 STFT bins, 7 parameter curves, plus freeze and phase smear effects. Commit `2ba0293` is the most recent working state.

**Key decisions (original):**
- CLAP only, Linux only, Bitwig primary target
- Rust + nih-plug + realfft + triple_buffer
- 7 independent EQ-style curve sets (6 nodes each), CurveNode {x,y∈[-1,+1],q∈[0,1]}
- Patent-safe: no oeksound-patented Hilbert/convolution approach
- Audio thread: zero allocation, zero locking
- All visual constants in editor/theme.rs only

**Current implementation state (as of 2026-04-22):**
- `feature/sidechain-refactor` merged to `master` — master now has both automation-presets and sidechain-refactor work
- Sidechain: single aux stereo SC port, `sc_envelope_rx` triple-buffer, single `sidechain_active: Arc<AtomicBool>`
- GainMode::Match: ERB-smoothed timbre-match via SC/main log-magnitude ratio
- `display_curve_idx(module_type, curve_idx, gain_mode: GainMode)` signature (3-arg)
- Params impl is hand-written (no `#[derive(Params)]`); `#[persist]` / `#[id]` attrs must NOT appear on struct fields
- All future work targets `master` branch (no active worktree)

**Previous state (2026-04-19):**
- 7 dynamics curves + 1 phase curve (index 7) + 4 freeze curves (indices 8–11)
- SpectralContrast engine as alternative to compressor
- EffectMode enum (exclusive modes) — being replaced by Plan A serial chain
- Reference fork at `/home/kim/Projects/spectral2/` has M/S processing (5 curves)

## Architecture roadmap (plans written in docs/superpowers/plans/)

**Plan A** (`2026-04-19-serial-fx-chain.md`): 
Serial FX chain — dynamics→freeze→phase sequential stages. Replaces exclusive EffectMode with freeze_enabled/phase_enabled BoolParams + DynamicsMode enum. Effects tab gets independent ON/OFF toggles.

**Plan B** (`2026-04-19-variable-fft.md`):
Variable FFT resolution. `MAX_FFT_SIZE = 16384`, `MAX_NUM_BINS = 8193`. All Pipeline buffers pre-allocated at MAX_NUM_BINS. Runtime fft_size in Pipeline, user-selectable (512/1024/2048/4096/8192/16384).

**Plan C** (`2026-04-19-modular-matrix.md`):
8×8 routing matrix architecture. Modules on diagonal; off-diagonal cells = send amplitudes (including feedback from later→earlier modules). Up to 8 module slots. Each module has: type, user-editable name, help text, channel routing target (All/Mid/Side). Graph header shows "Editing: [Name] - [channel]".

**Plan D**: M/S Module (5 curves: Balance, Expansion, Decorrelation, Transient, Pan). Reference: `/home/kim/Projects/spectral2/src/dsp/pipeline.rs` lines 446–501.

**Plan E**: HPSS Transient/Sustained splitter module.

## Key architectural decisions

- All buffers pre-allocated at MAX_NUM_BINS (MAX_FFT_SIZE/2+1 = 8193) — no audio-thread alloc
- 8×8 feedback routing matrix: matrix[j][i] = amplitude of module j output sent to module i input; j < i = feedback with one-hop delay
- Module channel_target (All/Mid/Side) gates processing per-channel inside StftHelper closure
- No per-node routing targets (indefinitely deferred)
- No FM replicator (deferred)
- Kim plays on big soundsystems (Turbosound, Funktion-One) — mono bass compatibility critical: Side channel sub-bass must be forceable to zero

## Reference project for M/S

`/home/kim/Projects/spectral2/` — reference M/S implementation:
- `src/bridge.rs`: ms_curve_tx/rx (5 channels)
- `src/params.rs`: NUM_MS_CURVES=5, ms_curve_nodes, ms_active_curve
- `src/dsp/pipeline.rs` lines 446–501: M/S balance in STFT closure
