"""Mood FiLM mode (sa3_control/mood.py + LatentControlDataset(mood_spec=...)): the [values, present]
vector, tag-subset sampling, inference requests, the dataset's mood curve and field filter, and the
checkpoint -> conditioner round trip. Needs stable-audio-3's scripts/latch/mood_targets.py (SA3_ROOT)."""

from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from sa3_control import mood

try:
    MT = mood.mood_targets()
except ImportError as e:                       # SA3 checkout absent (set SA3_ROOT)
    pytest.skip(f"stable-audio-3 mood_targets not importable: {e}", allow_module_level=True)

T = 64
N_TAGS = 8
NAMES = ["dark", "energetic"]


def _spec(smooth_s=0.0):
    return {"field": "effnet_moodtheme_ts", "transform": "logit_z", "n_channels_in": N_TAGS,
            "indices": [3, 5], "names": list(NAMES), "mean": [0.0, 0.0], "std": [1.0, 1.0],
            "smooth_s": smooth_s}


def test_tag_mask_is_never_empty_and_covers_every_subset_size():
    g = torch.Generator().manual_seed(0)
    m = mood.sample_tag_mask(4000, 5, generator=g)
    sizes = m.sum(1)
    assert m.shape == (4000, 5) and set(m.unique().tolist()) <= {0.0, 1.0}
    assert sizes.min() >= 1 and sizes.max() <= 5
    counts = torch.bincount(sizes.long(), minlength=6)[1:]
    assert (counts > 600).all()                                  # ~800 each for uniform 1..5
    assert (m.mean(0) - 0.6).abs().max() < 0.05                  # each tag kept ~E[size]/K = 3/5


def test_vector_absent_differs_from_corpus_mean():
    spec = _spec()
    v_dark = mood.request_vector(spec, {"dark": 2.0})
    assert v_dark.tolist() == [2.0, 0.0, 1.0, 0.0]               # energetic absent
    v_mean = mood.request_vector(spec, {"dark": 2.0, "energetic": 0.0})
    assert v_mean.tolist() == [2.0, 0.0, 1.0, 1.0]               # energetic held at the corpus mean
    assert mood.request_vector(spec, {"dark": 9.0}, clip=3.0)[0] == 3.0
    with pytest.raises(ValueError, match="not in this spec"):
        mood.request_vector(spec, {"happy": 1.0})
    with pytest.raises(ValueError, match="empty"):
        mood.request_vector(spec, {})
    assert mood.parse_request("dark=2, energetic=-1") == {"dark": 2.0, "energetic": -1.0}
    with pytest.raises(ValueError):
        mood.parse_request("dark")


def test_window_values_and_build_vector():
    curves = torch.zeros(2, 2, T)
    curves[0, 0] = 1.0
    curves[1, 1] = 10.0
    vals = mood.window_values(curves, clip=3.0)
    assert torch.allclose(vals, torch.tensor([[1.0, 0.0], [0.0, 3.0]]))
    vec = mood.build_vector(vals, torch.tensor([[1.0, 0.0], [1.0, 1.0]]))
    assert torch.allclose(vec, torch.tensor([[1.0, 0.0, 1.0, 0.0], [0.0, 3.0, 1.0, 1.0]]))


def _corpus(root, n=4, skip=()):
    root.mkdir()
    for i in range(n):
        stem = f"{i:06d}"
        np.save(root / f"{stem}.npy", np.zeros((256, T), np.float32))
        (root / f"{stem}.json").write_text(json.dumps({"path": f"track{i // 2}.flac", "prompt": "goa"}))
        comp = {"onset_envelope_ts": np.zeros(T, np.float32)}
        if stem not in skip:
            p = np.full((T, N_TAGS), 0.01, np.float32)
            p[:, 3] = 0.5                                        # logit 0
            p[T // 2:, 5] = 0.9                                  # logit ln 9 in the second half
            comp["effnet_moodtheme_ts"] = p
        np.savez(root / f"{stem}.TIMESERIES.npz", **comp)


def test_dataset_mood_curve_window_and_field_filter(tmp_path, capsys):
    from sa3_control.dataset import LatentControlDataset
    _corpus(tmp_path / "c", skip=("000002",))
    ds = LatentControlDataset(str(tmp_path / "c"), controls=(), audio_ref=None, mood_spec=_spec())
    assert len(ds) == 3 and "mood: 3/4 crops have effnet_moodtheme_ts" in capsys.readouterr().out
    item = ds[0]
    cur = item["controls"]["mood"]
    assert cur.shape == (2, T)
    assert torch.allclose(cur[0], torch.zeros(T), atol=1e-5)
    assert torch.allclose(cur[1, T // 2:], torch.full((T // 2,), float(np.log(9.0))), atol=1e-4)
    # the trainer's window mean over the first half sees only the low part of "energetic"
    half = mood.window_values(cur[None, :, :T // 2], clip=3.0)[0]
    assert half[1] < -3.0 + 1e-6                                 # logit(0.01) ~ -4.6, clipped to -3

    from sa3_control.train import collate
    b = collate([ds[0], ds[1]])
    assert b["controls"]["mood"].shape == (2, 2, T)


def test_checkpoint_round_trip_builds_the_same_encoder():
    from sa3_control.conditioner import FingerprintEncoder
    from sa3_control.generate import build_conditioner
    spec = _spec()
    enc = FingerprintEncoder(in_dim=mood.in_dim(spec), control_dim=64, n_tokens=4)
    torch.nn.init.normal_(enc.film[-1].weight, std=0.01)        # leave the zero-init identity
    ck = {"control_mode": "mood", "fp_in_dim": enc.in_dim, "mood_spec": spec,
          "args": {"control_dim": 64, "n_tokens": 4}}
    enc2 = build_conditioner(ck, "cpu", torch.float32)
    enc2.load_state_dict(enc.state_dict())
    vec = mood.request_vector(ck["mood_spec"], {"dark": 2.0})[None]
    assert torch.allclose(enc(vec), enc2(vec))
    assert not torch.allclose(enc(vec), enc(mood.request_vector(spec, {"dark": -2.0})[None]))
