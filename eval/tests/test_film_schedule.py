# Owner: WINTERMUTE (created 2026-10-15)
"""eval/film_schedule.py -- FiLM gain by noise level (E8)."""
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "control"))
import film_schedule as fs  # noqa: E402
from sa3_control.adapters import _ACTIVE, ControlContext, use_control_context  # noqa: E402


def test_gain_shape():
    assert fs.film_gain_at(0.9, 1.75) == 1.75                         # default window = everywhere
    assert fs.film_gain_at(0.9, 1.75, 0.5, 1.0) == 1.75               # inside
    assert fs.film_gain_at(0.2, 1.75, 0.5, 1.0) == 0.0                # tail, no fade
    assert abs(fs.film_gain_at(0.4, 2.0, 0.5, 1.0, fade=0.2) - 1.0) < 1e-9   # halfway down the ramp
    assert fs.film_gain_at(0.25, 2.0, 0.5, 1.0, fade=0.2) == 0.0      # past the ramp


def test_unscheduled_requests_are_untouched():
    assert not fs.is_scheduled(None)
    assert not fs.is_scheduled({"ckpt": "x", "value": 4.0, "gain": 1.75})
    assert fs.is_scheduled({"gain": 1.75, "sigma_min": 0.5})


class _Rec(torch.nn.Module):
    """Stands in for the DiT: records the adapter gain it sees on each call."""
    def __init__(self):
        super().__init__()
        self.seen = []

    def forward(self, x, t, **kw):
        self.seen.append(_ACTIVE["gain"])
        return x


def test_hook_sets_the_live_gain_per_step_and_cleans_up():
    m = _Rec()
    sigmas = [1.0, 0.8, 0.6, 0.4, 0.2]
    with use_control_context(ControlContext(torch.zeros(2, 4, 8), gain=1.75)):
        with fs.film_gain_schedule(m, _ACTIVE, 1.75, 0.5, 1.0):
            for s in sigmas:
                m(torch.zeros(1), torch.tensor([s]))
            m(torch.zeros(1), t=torch.tensor([0.9]))                   # kwarg form
    assert m.seen == [1.75, 1.75, 1.75, 0.0, 0.0, 1.75]
    assert _ACTIVE["gain"] == 1.0 and _ACTIVE["tokens"] is None       # context restored
    m.seen.clear()
    m(torch.zeros(1), torch.tensor([0.2]))                             # hook removed
    assert m.seen == [1.0]


def test_fade_shapes():
    # E18: the same fade band, three shapes; all start at the full gain and fall to (near) 0 at the end of the fade
    for shape in ("linear", "cosine", "exp"):
        assert abs(fs.film_gain_at(0.5, 2.0, 0.5, 1.0, fade=0.2, shape=shape) - 2.0) < 1e-9
        assert fs.film_gain_at(0.3001, 2.0, 0.5, 1.0, fade=0.2, shape=shape) < 0.05
    assert abs(fs.film_gain_at(0.4, 2.0, 0.5, 1.0, fade=0.2, shape="cosine") - 1.0) < 1e-9
    assert abs(fs.film_gain_at(0.4, 2.0, 0.5, 1.0, fade=0.2, shape="exp") - 0.2) < 1e-9   # exp(-ln100 / 2) = 0.1


def test_step_envelope_matches_the_latch_window():
    # the FiLM step envelope must be the LatCH window's envelope, step for step (E18 crossfades rely on it)
    sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
    from stable_audio_3.inference.latch_guided import _guide_fades, _window_scale
    n = 50
    g = {"start_pct": 0.2, "end_pct": 1.0, "fade_in_pct": 0.2, "fade_out_pct": 0.2, "fade_shape": "cosine"}
    w = _window_scale(torch.ones(n), int(n * 0.2), n, "flat", *_guide_fades(g, n))
    env = fs.step_envelope(n, 0.2, 1.0, 0.2, 0.2, "cosine")
    assert torch.allclose(w / w.max(), torch.tensor(env), atol=1e-6)


def test_crossfade_sums_to_one():
    n = 50
    for shape in ("linear", "cosine"):
        film = fs.step_envelope(n, 0.0, 0.4, 0.0, 0.2, shape)       # full to 20%, fades out over 20-40%
        latch = fs.step_envelope(n, 0.2, 1.0, 0.2, 0.0, shape)      # fades in over 20-40%, full after
        assert all(abs(a + b - 1.0) < 1e-9 for a, b in zip(film, latch))


def test_step_hook_advances_on_sigma_change_only():
    m = _Rec()
    env = [1.0, 0.5, 0.0]
    with use_control_context(ControlContext(torch.zeros(2, 4, 8), gain=2.0)):
        with fs.film_step_schedule(m, _ACTIVE, 2.0, env):
            for s in (1.0, 1.0, 0.6, 0.6, 0.6, 0.3, 0.1):              # repeated sigma = same step; past the end = last
                m(torch.zeros(1), torch.tensor([s]))
    assert m.seen == [2.0, 2.0, 1.0, 1.0, 1.0, 0.0, 0.0]
    assert fs.is_step_scheduled({"end_pct": 0.4}) and not fs.is_step_scheduled({"gain": 1.0})
