# eval/test_soup_ladder.py — run: SAO/.venv/bin/python -m pytest eval/test_soup_ladder.py -q
import math

import pytest
import torch

from eval.soup_ladder import profile_weights, soup_state_dicts


def test_profiles_sum_to_one_and_have_expected_shape():
    for prof in ("uniform", "asc", "expasc", "bell_late", "bell_end"):
        w = profile_weights(8, prof)
        assert abs(sum(w) - 1.0) < 1e-12, prof
        assert len(w) == 8
    assert profile_weights(8, "asc")[-1] > profile_weights(8, "asc")[0]
    e = profile_weights(8, "expasc")
    assert abs(e[-1] / e[0] - math.exp(4.0)) < 1e-9          # ~55x last-to-first
    b = profile_weights(9, "bell_late", peak_frac=0.75)       # peak at index 6 of 0..8
    assert b.index(max(b)) == 6
    assert profile_weights(5, "bell_end").index(max(profile_weights(5, "bell_end"))) == 4


def test_soup_of_identical_dicts_is_identity():
    sd = {"x.lora_A": torch.randn(4, 3), "x.magnitude": torch.rand(4)}
    out = soup_state_dicts([sd, sd, sd], [0.2, 0.3, 0.5])
    for k in sd:
        assert torch.allclose(out[k], sd[k])


def test_soup_two_dicts_half_half_is_mean_and_keeps_dtype():
    a = {"w": torch.zeros(3, dtype=torch.bfloat16)}
    b = {"w": torch.ones(3, dtype=torch.bfloat16)}
    out = soup_state_dicts([a, b], [0.5, 0.5])
    assert out["w"].dtype == torch.bfloat16
    assert torch.allclose(out["w"].float(), torch.full((3,), 0.5))


def test_soup_refuses_bad_weights_and_mismatched_keys():
    a = {"w": torch.zeros(2)}
    with pytest.raises(ValueError):
        soup_state_dicts([a, a], [0.5, 0.6])
    with pytest.raises(ValueError):
        soup_state_dicts([a, {"v": torch.zeros(2)}], [0.5, 0.5])
