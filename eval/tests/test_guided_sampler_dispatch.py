"""Guidance must not silently change which sampler renders the audio.

sampling.py picks pingpong for rf_denoiser (the post-trained "medium") and euler
otherwise. model.py's guided path used to hardcode euler, so merely passing
latch_configs converted an 8-step pingpong render into an 8-step Euler one --
before any head was consulted. Every guided clip then shared one wrong-sampler
sound and none of them was comparable to its own unguided baseline, which is how
an inert head and a mismatched sampler became indistinguishable by ear
(WORKLOG 2026-09-16).

These tests pin the rule itself, not a render: no model load, no GPU.
"""
import sys

import pytest

sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from stable_audio_3.inference.latch_guided import resolve_guided_sampler


def test_post_trained_model_gets_its_native_pingpong():
    """The regression. rf_denoiser is distilled for pingpong; guidance must not
    silently hand it euler."""
    assert resolve_guided_sampler("rf_denoiser") == "pingpong"


def test_base_model_still_gets_euler():
    assert resolve_guided_sampler("rectified_flow") == "euler"
    assert resolve_guided_sampler("v") == "euler"


def test_guided_choice_matches_the_unguided_choice():
    """The invariant that makes a guided render comparable to its own baseline:
    this rule must agree with sampling.py's `pingpong iff rf_denoiser`."""
    for objective in ("rf_denoiser", "rectified_flow", "v"):
        unguided = "pingpong" if objective == "rf_denoiser" else "euler"
        assert resolve_guided_sampler(objective) == unguided


def test_latch_hparams_override_wins_so_one_ckpt_can_be_ab_tested():
    """Without this, 'before' and 'after' differ by model family as well as by
    sampler, and the A/B measures nothing."""
    assert resolve_guided_sampler(
        "rf_denoiser", {"sampler_type": "euler"}) == "euler"
    assert resolve_guided_sampler(
        "rectified_flow", {"sampler_type": "pingpong"}) == "pingpong"


def test_generate_level_sampler_type_is_honoured():
    """Callers already pass sampler_type= to generate(); they should not need a
    second dialect for the guided path."""
    assert resolve_guided_sampler("rf_denoiser", None, "euler") == "euler"


def test_latch_hparams_beats_generate_level():
    assert resolve_guided_sampler(
        "rf_denoiser", {"sampler_type": "pingpong"}, "euler") == "pingpong"


def test_absent_and_empty_overrides_fall_through_to_native():
    """A None/empty override must not be mistaken for a request."""
    assert resolve_guided_sampler("rf_denoiser", {}, None) == "pingpong"
    assert resolve_guided_sampler("rf_denoiser", {"sampler_type": None}) == "pingpong"
    assert resolve_guided_sampler("rf_denoiser", None, None) == "pingpong"


def test_an_unsupported_sampler_raises_instead_of_silently_downgrading():
    """rk4/dpmpp are real sample_diffusion samplers with no guided implementation.
    They used to be accepted and quietly turned into euler -- the same silence
    this change exists to remove."""
    with pytest.raises(ValueError, match="euler.*pingpong"):
        resolve_guided_sampler("rectified_flow", {"sampler_type": "dpmpp"})
    with pytest.raises(ValueError):
        resolve_guided_sampler("rf_denoiser", None, "rk4")
