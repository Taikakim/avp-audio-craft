import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge.holdpass import (clip_frame_span, depth_for_spans, make_hold_callback,
                            make_hold_renoise_hook)
from forge.splice import splice_by_mask

FLAT = lambda v: {"points": [v] * 4, "curves": [0, 0, 0]}  # noqa: E731


def test_clip_frame_span():
    assert clip_frame_span(0.0, 1.0, 10.0) == (0, 10)
    assert clip_frame_span(0.25, 0.5, 10.0) == (2, 6)          # floor(2.5)=2, ceil(7.5)=8
    assert clip_frame_span(3.0, 0.0, 10.0) == (30, 1)


def test_depth_for_spans_max_and_clip():
    d = depth_for_spans([(2, FLAT(0.3), 4), (4, FLAT(0.6), 10)], 10)
    np.testing.assert_allclose(d, [0, 0, 0.3, 0.3, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6], atol=1e-6)
    assert d.dtype == np.float32


def test_hold_callback_holds_until_release():
    T = 4
    ref = torch.arange(T, dtype=torch.float32).view(1, 1, T)
    eps = torch.ones(1, 1, T)
    depth = np.array([0.0, 0.5, 1.0, 0.2], dtype=np.float32)
    cb = make_hold_callback(ref, eps, depth)
    x = torch.full((1, 1, T), 99.0)
    cb({"x": x, "t": torch.tensor([0.4])})
    # depth < t held to (1-t)*ref + t*eps ; depth >= t left alone
    expect = [0.6 * 0 + 0.4, 99.0, 99.0, 0.6 * 3 + 0.4]
    np.testing.assert_allclose(x.view(-1).numpy(), expect, atol=1e-6)
    x2 = torch.full((1, 1, T), 7.0)
    cb({"x": x2, "t": torch.tensor(0.1)})                         # 0-d t (pingpong-style) also works
    np.testing.assert_allclose(x2.view(-1).numpy(), [0.9 * 0 + 0.1, 7.0, 7.0, 7.0], atol=1e-6)


def test_renoise_hook_applies_hold_after_renoise():
    T = 3
    ref = torch.zeros(1, 1, T)
    eps = torch.full((1, 1, T), 2.0)
    depth = np.array([0.0, 0.9, 0.0], dtype=np.float32)
    hook = make_hold_renoise_hook(ref, eps, depth)
    torch.manual_seed(0)
    out = hook(torch.full((1, 1, T), 5.0), torch.tensor(0.5), torch.zeros(1, 1, T), 0)
    assert out[0, 0, 0].item() == pytest.approx(1.0) and out[0, 0, 2].item() == pytest.approx(1.0)
    assert out[0, 0, 1].item() != pytest.approx(1.0)              # released frame keeps the renoised draw


def test_splice_by_mask_crossfade():
    old = torch.zeros(1, 1, 10)
    new = torch.ones(1, 1, 10)
    mask = np.zeros(10, bool)
    mask[2:8] = True
    out = splice_by_mask(old, new, mask, xfade=2).view(-1).numpy()
    np.testing.assert_allclose(out, [0, 0, 1 / 3, 2 / 3, 1, 1, 2 / 3, 1 / 3, 0, 0], atol=1e-6)
    short = np.zeros(10, bool)
    short[4:6] = True
    out2 = splice_by_mask(old, new, short, xfade=2).view(-1).numpy()
    assert out2[:4].max() == 0 and out2[6:].max() == 0 and 0 < out2[4] <= 1
    assert torch.equal(splice_by_mask(old, new, np.zeros(10, bool)), old)
