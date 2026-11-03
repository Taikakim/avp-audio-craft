---
name: Spectral Forge stabilization tracker location
description: Path to the persistent backlog doc tracking 18+ open issues and sub-project decomposition
type: project
originSessionId: cd4df882-0456-4abe-ad52-476a875f03c6
---
The single source of truth for the Spectral Forge stabilization effort is at:

**`docs/superpowers/2026-05-06-stabilization-backlog.md`** (in the project repo).

It contains:
- 18+ numbered open issues with status, source, and current understanding
- User-stated directives (universal slider traversal, master soft clipper, MIX default 100% wet, Floor=-120 default, etc.)
- Sub-project decomposition (A through F) with critical-path ordering
- Currently in design: Sub-project A (Approach 1 — single-spec stabilization sweep covering routing, bypass, soft-clipper move, smearing-over-time)
- Diagnostic facts captured along the way

**How to use:** before answering any question about Spectral Forge open issues or design intent, read this doc. Update its "Update log" section when major facts or decisions land. Do not let the in-conversation backlog list drift from this doc.

**Why:** the user explicitly asked for a persistent tracker that survives context compaction, cache deletes, and conversation forks. The doc serves that purpose; this memory entry is the breadcrumb to find it.

**Current state (as of 2026-05-08 overnight session):** Sub-projects A, B+C, D, AND E are COMPLETE. The 2026-05-08 sweep ran D-1 (TILT_MAX → 4, Freeze portamento 0..750ms with 1ms floor, off_thresh recalibration), D-2 (curve area headroom above 0 dB with full clamp removal so curves flow into the strip), E-1 (Freeze RESISTANCE log-scaled excess capped at 0.1/hop), and E-2 (PAST SMEAR active in all 5 modes with mode-specific semantics). Plus help-system overhauls: context-sensitive help-box, pending/presented promotion model, per-curve/per-mode help text catalog for every shipped module, dynamic matrix flow text with yellow Feedback prefix. Plus systemic root-cause fixes for: the "100% offset" pattern (`default_nodes_for_module_curve` Dynamics-only RATIO routing), mode popups not opening (`ui.id()` → stable `egui::Id::new`), tilt display/DSP mismatch (TILT_MAX scaling), Contrast UI panel, Gain Pull/Match display index, Harmony THRESHOLD axis, Rhythm panel resize, persistent ~25% spectrum line. ~30 commits between `4aa0600` → `376b5f2`. Closed during this sweep: issues #6, #9, #10, #11, #15, #16. Spec doc updated with §3.5 (headroom), revised §8 (help-box), and new §9 (lessons learned). Tracker doc updated.

**Next sub-projects pending (per backlog table):**
- (F) PEAK HOLD DSP mismatch (deferred from prior plan) — only sub-project remaining.

**Known limitations carried over:**
- Virtual rows (T/S Split) routing remains non-functional — `matrix_cell` bounds-check rejects r >= 9. Marked with TODO in `fx_matrix_grid.rs`. Fixing requires extending NUM_MATRIX_ROWS and adding FloatParams for virtual rows.
- Threshold idx 9 calibration test in `tests/calibration.rs::threshold_idx9_dsp_matches_display_log_formula` is a pre-existing failure on `--features=probe`. Same root cause as the deferred entries in `tests/curve_calibration_matrix.rs` (idx 0/9 offset_fn exponents calibrated for old db_min=-60). Don't try to fix in passing — needs its own plan.
- PEAK HOLD on PhaseSmear/1 + Gain/1 (idx 14) — endpoints match axis_aware_lerp but mid-range slider positions show ±5 ms variance due to `peak_hold_curve_to_ms` (log-piecewise) not composing smoothly with `off_portamento` (geometric). Marked deferred in `tests/curve_calibration_matrix.rs`. Fix would need a custom `off_peak_hold` that's the inverse of `peak_hold_curve_to_ms ∘ axis_aware_lerp`.
