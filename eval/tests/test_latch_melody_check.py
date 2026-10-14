# Owner: GHOST-NOTE (created 2026-10-14)
"""Controls for latch_melody_check: run under the MIR venv (basic_pitch, mir_eval):
    /home/kim/Projects/mir/mir/bin/python -m pytest eval/tests/test_latch_melody_check.py"""
import os
import sys
import tempfile

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("basic_pitch")
pytest.importorskip("mir_eval")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import latch_melody_check as m  # noqa: E402

SR = 22050


def melody(notes, dur=6.0):
    t = np.arange(int(dur * SR)) / SR
    seg = len(t) // len(notes)
    x = np.zeros(len(t), dtype=np.float32)
    for n, p in enumerate(notes):
        tt = t[n * seg:(n + 1) * seg]
        x[n * seg:(n + 1) * seg] = 0.4 * np.sin(2 * np.pi * 440 * 2 ** ((p - 69) / 12) * tt) * np.minimum(1, np.minimum(tt - tt[0], tt[-1] - tt) * 40)
    return x


def w(td, name, x):
    p = os.path.join(td, name + ".wav")
    sf.write(p, x, SR)
    return p


def test_same_notes_eqd_match_and_shifted_or_unrelated_do_not():
    from scipy.signal import butter, sosfilt
    A, B = [60, 64, 67, 72, 64, 60], [62, 65, 69, 74, 65, 62]
    with tempfile.TemporaryDirectory() as td:
        x = melody(A)
        eq = (sosfilt(butter(2, 2500, "lowpass", fs=SR, output="sos"), x) * 2).astype(np.float32)   # darker + louder, same notes (Kim's case)
        up1 = melody([p + 1 for p in A])                                                               # every note a semitone up
        rows = m.run([{"id": "eq", "base": w(td, "a", x), "steered": w(td, "a_eq", eq)},
                      {"id": "up1", "base": w(td, "b", melody(B)), "steered": w(td, "b_up", melody([p + 1 for p in B]))},
                      {"id": "same", "base": w(td, "c", melody([65, 69, 72, 77, 69, 65])), "steered": w(td, "c2", melody([65, 69, 72, 77, 69, 65]))}])
        by = {r["id"]: r for r in rows}
        assert by["eq"]["matched"]["note_f1"] > 0.9
        assert by["same"]["matched"]["note_f1"] > 0.99
        assert by["up1"]["matched"]["note_f1"] < 0.2 and by["up1"]["matched"]["pc_hist_cos"] < 0.5
        assert by["eq"]["unrelated"]["note_f1"] < by["eq"]["matched"]["note_f1"] - 0.5
