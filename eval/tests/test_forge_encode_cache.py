"""Review 2026-10-01: encode_cached returned fp32 on a miss but the fp16 it saved on a hit, so a fixed
seed rendered differently on the first run; and the cache write was not atomic."""
import threading
from types import SimpleNamespace

import numpy as np
import pytest

import forge_testutil  # noqa: F401

torch = pytest.importorskip("torch")
from forge.services import Services, HOP  # noqa: E402


def test_miss_and_hit_return_the_same_latent(tmp_path):
    calls = []

    class FakePretransform(torch.nn.Module):
        """Stands in for MODEL.model.pretransform -- the path encode_cached really uses (StableAudioModel
        has no .encode(); found on the first real-server run, 2026-10-06)."""
        def __init__(self):
            super().__init__()
            self.w = torch.nn.Parameter(torch.zeros(1))

        def encode(self, audio):          # audio [1, 2, N]
            calls.append(1)
            g = torch.Generator().manual_seed(0)
            return torch.randn(1, 256, int(np.ceil(audio.shape[-1] / HOP)), generator=g) * 3.14159

    model = SimpleNamespace(model=SimpleNamespace(pretransform=FakePretransform()))
    srv = SimpleNamespace(MODEL=model, SR=44100, GPU_LOCK=threading.Lock())
    paths = SimpleNamespace(cache_dir=lambda kind: (tmp_path / kind).mkdir(exist_ok=True) or tmp_path / kind)
    svc = Services(srv, lambda: paths)
    audio = np.random.default_rng(1).standard_normal((2, HOP * 5)).astype(np.float32)
    miss = svc.encode_cached(audio)
    hit = svc.encode_cached(audio)
    assert len(calls) == 1
    assert torch.equal(miss, hit) and miss.dtype == torch.float32
    assert not list((tmp_path / "encode").glob("*.part*"))
