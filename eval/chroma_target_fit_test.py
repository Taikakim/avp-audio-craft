"""chroma_target_fit_test.py -- CPU checks for the 2026-10-30 chroma eval fixes (KUANG).

  - latent_frames / fit_to_latent (chroma_steer_render): a target fitted to the latent window
    survives model.py's resample unchanged, while an unfitted progression is stretched ~1.3x.
  - record_is_current (chroma_avp_matrix_render): stale heads and stretched progressions are
    re-rendered, unaffected static cells are reused.
  - load_full_ft / checked_decode (render_choice_clips_chroma).

Run:  SA3_SRC=<stable-audio-3 checkout> SAME_CHROMA_SRC=<mir-same-chroma>/src python -m pytest eval/chroma_target_fit_test.py
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parent
for p in (os.environ.get("SA3_SRC", str(HERE.parent / "stable-audio-3")),
          os.environ.get("SAME_CHROMA_SRC", "/home/kim/Projects/mir-same-chroma/src"),
          str(HERE.parent / "control"), str(HERE)):
    sys.path.insert(0, p)

import chroma_steer_render as CSR  # noqa: E402


def _fake_model(stride0=2, chunk=4):
    """Just enough of StableAudioModel for the real _adapt_sample_size."""
    from stable_audio_3.model import StableAudioModel
    m = SimpleNamespace(
        model=SimpleNamespace(sample_rate=44100, pretransform=SimpleNamespace(downsampling_ratio=4096)),
        model_config={"model": {"pretransform": {"config": {"encoder": {"config": {
            "chunk_size": chunk, "strides": [stride0]}}}}}})
    m._adapt_sample_size = StableAudioModel._adapt_sample_size.__get__(m)
    return m


def test_latent_frames_include_the_padding():
    m = _fake_model()
    assert CSR.latent_frames(m, 20.0) == 280      # 26.0 s -> 279.9 -> 280 (even)
    assert CSR.latent_frames(m, 20.05) == 282     # 26.05 s -> 280.5 -> 281 -> 282
    assert CSR.latent_frames(m, 20.05) > int(round(20.05 * CSR.FPS))


def _resample_like_model_py(raw, n_latent):
    t = torch.as_tensor(raw, dtype=torch.float32).unsqueeze(0)
    return torch.nn.functional.interpolate(t, size=n_latent, mode="linear", align_corners=False)[0].numpy()


def test_fitted_progression_keeps_its_timing():
    n, n_latent = 216, 282
    step = np.zeros((1, n), np.float32)
    step[:, 108:] = 1.0                            # one chord change at 10 s
    old = _resample_like_model_py(step, n_latent)[0]
    new = _resample_like_model_py(CSR.fit_to_latent(step, n_latent), n_latent)[0]
    assert np.array_equal(new[:n], step[0])        # identity over the audible frames
    assert np.all(new[n:] == 1.0)                  # last frame held over the padding
    change_old = int(np.argmax(old >= 0.5))
    assert change_old > 108 * 1.25                 # the old path moved the change ~30 % later
    with pytest.raises(ValueError):
        CSR.fit_to_latent(np.zeros((1, 300)), n_latent)


def test_avp_matrix_reuses_only_current_records(monkeypatch):
    import chroma_avp_matrix_render as M
    legacy = M.LEGACY_HEADS
    assert M.record_is_current({"head": "goa_e13", "target": "C"})                 # static, same head
    assert M.record_is_current({"head": "base", "target": ""})
    assert not M.record_is_current({"head": "goa_e13", "target": "keylift"})       # stretched progression
    assert not M.record_is_current({"head": "avp_aug", "target": "C"})             # readout-target head
    assert M.record_is_current({"head": "avp_aug", "target": "keylift",
                                "head_path": str(M.HEADS["avp_aug"]), "target_fit": "latent"})
    monkeypatch.setitem(M.HEADS, "goa_e13", Path("/elsewhere/ep14.pt"))
    assert not M.record_is_current({"head": "goa_e13", "target": "C", "head_path": legacy["goa_e13"]})


def test_full_ft_load_refuses_a_partial_checkpoint(tmp_path):
    import render_choice_clips_chroma as R
    dit = torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.Linear(2, 2))
    full = {f"model.{k}": v + 1 for k, v in dit.state_dict().items()}
    torch.save({"state_dict": full}, tmp_path / "full.ckpt")
    assert R.load_full_ft(dit, tmp_path / "full.ckpt") == 4
    partial = {k: v for k, v in full.items() if not k.startswith("model.1.")}
    torch.save({"state_dict": partial}, tmp_path / "partial.ckpt")
    with pytest.raises(RuntimeError, match="partial load"):
        R.load_full_ft(dit, tmp_path / "partial.ckpt")


def test_checked_decode_retries_until_two_agree():
    import render_choice_clips_chroma as R
    good = torch.zeros(1, 2, 10)
    outs = iter([torch.full((1, 2, 10), 0.9), good, good.clone()])
    w, extra = R.checked_decode(lambda z: next(outs), None)
    assert torch.equal(w, good) and extra == 2
    with pytest.raises(RuntimeError):
        R.checked_decode(lambda z: torch.randn(1, 2, 10), None)
