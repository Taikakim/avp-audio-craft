# Owner: GHOST-NOTE (created 2026-10-28)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import mixtape_v7_dsp as dsp

SR = 44100


def test_handover_waits_for_the_last_clash():
    bar = 1000; L = 10 * bar; downs = np.arange(0, L, bar)
    assert dsp.clash_free_handover([0, 0, 40, 40, 0, 0, 0, 0, 0, 0], downs, bar, L) == 6 * bar   # not before 60 % of the window
    assert dsp.clash_free_handover([0, 0, 0, 0, 0, 0, 0, 30, 30, 0], downs, bar, L) == 9 * bar   # first downbeat after the last bad run
    assert dsp.clash_free_handover([0, 0, 0, 0, 0, 0, 0, 0, 50, 50], downs, bar, L) is None      # clash to the end: left to the edge
    assert dsp.clash_free_handover([None, 1, 2, 3, 4, 5, 6, 7, 1, 1], downs, bar, L) == 6 * bar  # None = a break, not a clash
    assert dsp.clash_free_handover([0, 0, 0, 0, 0, 0, 0, 0, 0, 80], downs, bar, L) == 6 * bar    # one odd final bar is a fill, ignored


def test_filter_swap_goes_from_a_to_b_without_two_basslines():
    bar = int(SR * 1.7); L = 8 * bar; t = np.arange(L) / SR
    a = np.sin(2 * np.pi * 55 * t)[None, :].astype(np.float32); b = np.sin(2 * np.pi * 90 * t)[None, :].astype(np.float32)
    downs = np.arange(0, L, bar)
    m, h = dsp.bandswap_master(a, b, downs, bar, SR, handover=5 * bar, swap_sec=2 * bar / 4 / SR)
    assert np.isfinite(m).all() and h == 5 * bar
    m0, _ = dsp.bandswap_master(a, b, downs, bar, SR, handover=5 * bar)          # the legacy level blend, same hand-over bar
    # endpoints agree with the legacy master: before the hand-over it is A's bass, after the swap it is B's, in the same amounts
    assert np.allclose(m[0, 3 * bar:4 * bar], m0[0, 3 * bar:4 * bar], atol=1e-3)
    assert np.allclose(m[0, 6 * bar:7 * bar], m0[0, 6 * bar:7 * bar], atol=0.05)
    mid = slice(5 * bar, 5 * bar + int(2 * bar / 4))                            # during the swap the two masters differ (the filter swap)
    assert not np.allclose(m[0, mid], m0[0, mid], atol=1e-3)
