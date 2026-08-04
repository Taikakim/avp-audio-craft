"""TDD for the tier-1 windowed-a2a breathing loop orchestration (#35).

The driver walks the source in overlapping windows; each window is rendered a2a at the
controller's current init_noise_level, the OUTPUT window is measured (recurrence,
novelty) by the injected meter, and the controller sets the next window's nl. The
renderer and meter are injected (dependency injection) so the loop logic is testable
with no GPU and independent of W's recurrence_meter3 signature. The driver returns the
joined audio plus the per-window (nl, recurrence, novelty) trajectories — the "does it
breathe" eval artifact.
"""
import numpy as np
from breathing_controller import BreathingController
from breathing_a2a import breathing_loop, plan_windows


def test_plan_windows_covers_track_with_overlap():
    # 100s track, 30s windows, 10s overlap -> stride 20s -> starts 0,20,40,60,80(->100)
    wins = plan_windows(total_sec=100.0, window_sec=30.0, overlap_sec=10.0)
    assert wins[0] == (0.0, 30.0)
    assert wins[1][0] == 20.0
    assert wins[-1][1] == 100.0          # last window ends exactly at the track end
    # windows are contiguous-with-overlap and never exceed the track
    assert all(lo < hi <= 100.0 for lo, hi in wins)


def test_loop_renders_each_window_at_controller_nl():
    calls = []
    def render(win_audio, nl):
        calls.append(nl)
        return win_audio                      # identity "render"
    def measure(ctx, new_len):
        return (0.1, 0.9)                     # never loops -> nl stays at requested
    ctl = BreathingController(requested_nl=0.6, novelty_floor=0.3, novelty_up=0.5)
    src = np.ones((2, 44100 * 100), dtype=np.float32)
    _full, traj = breathing_loop(src, sr=44100, window_sec=30.0, overlap_sec=10.0,
                                 render=render, measure=measure, controller=ctl)
    assert calls, "renderer was never called"
    assert all(abs(nl - 0.6) < 1e-9 for nl in calls)          # no loop -> steady nl
    assert len(traj["nl"]) == len(traj["recurrence"]) == len(traj["novelty"]) == len(calls)


def test_nl_breathes_down_then_up():
    # scripted meter: windows 1-2 loop hard, then novelty recovers
    seq = iter([(0.9, 0.05), (0.9, 0.05), (0.2, 0.8), (0.2, 0.8), (0.2, 0.8)])
    seen = []
    def render(win_audio, nl):
        seen.append(nl); return win_audio
    def measure(ctx, new_len):
        return next(seq)
    ctl = BreathingController(requested_nl=0.7, novelty_floor=0.3, novelty_up=0.5,
                              nl_step=0.1, nl_min=0.3)
    src = np.ones((2, 44100 * 100), dtype=np.float32)
    _full, traj = breathing_loop(src, sr=44100, window_sec=25.0, overlap_sec=5.0,
                                 render=render, measure=measure, controller=ctl)
    nl = traj["nl"]
    # window0 at requested, then steps DOWN across the looping windows, then back UP
    assert nl[0] == 0.7
    assert nl[1] < nl[0]                       # engaged, stepped down after first loop
    assert min(nl) < 0.7                       # it did breathe down
    assert nl[-1] > min(nl)                    # and recovered back up


def test_join_preserves_channels_and_length():
    def render(win_audio, nl):
        return win_audio
    def measure(ctx, new_len):
        return (0.1, 0.9)
    ctl = BreathingController(requested_nl=0.5, novelty_floor=0.3, novelty_up=0.4)
    src = np.ones((2, 44100 * 60), dtype=np.float32)
    full, _traj = breathing_loop(src, sr=44100, window_sec=20.0, overlap_sec=5.0,
                                 render=render, measure=measure, controller=ctl)
    assert full.shape[0] == 2                  # stereo preserved
    assert abs(full.shape[1] - src.shape[1]) <= 44100 * 0.5   # ~same length (± a hop)


def test_measure_sees_growing_trailing_context():
    # the measure must receive accumulated trailing context (not the isolated window),
    # so it can see a phrase repeating ACROSS windows. new_len stays ~one window; the
    # context length grows until it saturates at lookback+window.
    ctx_lens, new_lens = [], []
    def render(win_audio, nl):
        return win_audio
    def measure(ctx, new_len):
        ctx_lens.append(ctx.shape[1]); new_lens.append(new_len)
        return (0.1, 0.9)
    ctl = BreathingController(requested_nl=0.6, novelty_floor=0.3, novelty_up=0.5)
    src = np.ones((2, 44100 * 120), dtype=np.float32)
    breathing_loop(src, sr=44100, window_sec=25.0, overlap_sec=5.0,
                   render=render, measure=measure, controller=ctl, lookback_sec=40.0)
    assert ctx_lens[0] < ctx_lens[2]                       # context accumulates
    assert ctx_lens[-1] <= 44100 * (40.0 + 25.0) + 1       # capped at lookback+window
    assert ctx_lens[-1] > ctx_lens[0]                      # later windows see more context


def test_flag_breaks_marks_quiet_and_sparse_windows():
    from breathing_a2a import _flag_breaks
    # window 2 is both quiet (low rms) AND sparse (low onset) -> a break; the other
    # low-on-one-axis windows are misaligned so the AND only catches window 2.
    onset = [5.0, 4.0, 0.2, 4.5, 6.0]
    rms   = [0.30, 0.31, 0.01, 0.28, 0.29]
    assert _flag_breaks(onset, rms, pct=25.0) == [False, False, True, False, False]
    # sparse-but-loud (idx0) or quiet-but-busy (idx1) must NOT flag - a break needs BOTH
    assert _flag_breaks([0.1, 5, 5, 5], [0.5, 0.1, 0.5, 0.5], pct=25.0) == [False, False, False, False]


def test_breathing_loop_v2_ducks_hard_on_source_break():
    from breathing_a2a import breathing_loop_v2
    from breathing_controller import BreathingControllerV2
    seen = []
    def render(win, nl):
        seen.append(nl); return win
    def measure(ctx, new_len):
        return (0.1, 0.9)                       # healthy output everywhere
    ctl = BreathingControllerV2(requested_nl=0.62, novelty_floor=0.30, novelty_up=0.55,
                                nl_min=0.30, break_floor=0.30, reramp_start=0.41)
    src = np.ones((2, 44100 * 125), dtype=np.float32)
    from breathing_a2a import plan_windows
    nwin = len(plan_windows(125.0, 25.0, 5.0))
    breaks = [False]*nwin
    breaks[2] = True                            # a source break at window 2
    _full, traj = breathing_loop_v2(src, 44100, 25.0, 5.0, render, measure, ctl,
                                    source_breaks=breaks)
    assert traj["nl"][0] == 0.62                # healthy ceiling
    assert traj["nl"][2] == 0.30                # ducked hard on the break
    assert abs(traj["nl"][3] - 0.41) < 1e-9     # re-ramp start after the break
    assert traj["nl"][4] > traj["nl"][3]        # then climbs
    assert traj["source_break"][2] is True


def test_derive_source_flags():
    from breathing_a2a import derive_source_flags
    # w0 = break (quiet+sparse), w2 = fill (onset+HF burst, loud), others mid
    feats = {"onset": [0.1, 3.0, 9.0, 3.0, 3.0],
             "rms":   [0.02, 0.3, 0.5, 0.3, 0.3],
             "hf":    [0.05, 0.3, 0.9, 0.3, 0.3]}
    f = derive_source_flags(feats, break_pct=25.0, fill_pct=80.0)
    assert f["break"][0] is True and f["break"][2] is False
    assert f["fill"][2] is True and f["fill"][0] is False       # burst
    assert f["low_density"][0] is True                           # below mean onset


def test_breathing_loop_v3_flushes_on_fill():
    from breathing_a2a import breathing_loop_v3, plan_windows
    from breathing_controller import BreathingControllerV3
    def render(win, nl):
        return win
    def measure(ctx, new_len):
        return (0.1, 0.9)                                        # healthy output
    ctl = BreathingControllerV3(ceiling=0.70, relax_ceiling=0.30, nl_min=0.30,
                                novelty_floor=0.30, flush_floor=0.05)
    src = np.ones((2, 44100 * 125), dtype=np.float32)
    nwin = len(plan_windows(125.0, 25.0, 5.0))
    flags = {"break": [False]*nwin, "fill": [False]*nwin, "low_density": [False]*nwin}
    flags["fill"][2] = True
    _full, tr = breathing_loop_v3(src, 44100, 25.0, 5.0, render, measure, ctl,
                                  source_flags=flags, hf_static_thr=-1.0)  # never HF-static
    assert tr["nl"][0] == 0.70                                   # high ceiling
    assert tr["nl"][2] == 0.05                                   # deep flush on the fill
    assert tr["nl"][3] > tr["nl"][2]                             # re-ramps after
    assert len(tr["hf_var"]) == nwin and "hf_static" in tr
