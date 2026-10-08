"""render_v7_smoketest.main() end to end on SYNTHETIC stems; SA3 and the LatCH solver are faked.

Covers the glue the DSP tests cannot: stem loading, windowing, run_meta.json, the file-name label, and the
three generation outcomes (finite, non-finite, exception) with and without --allow-fallback."""
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_v7_smoketest as smoke  # noqa: E402

SR = 44100
BPM = 140.0
W_BARS = 2
L = int(round(W_BARS * 4 * 60 / BPM * SR))


@pytest.fixture()
def project(tmp_path):
    rng = np.random.default_rng(0)
    clips = [{"id": f"c{k}", "bpm": BPM} for k in range(3)]
    (tmp_path / "order.json").write_text(json.dumps(clips))
    bounds = {c["id"]: {"start": 3.0, "end_pre_zc": 5.0} for c in clips}
    (tmp_path / "bounds.json").write_text(json.dumps(bounds))
    for k in range(3):
        d = tmp_path / "stems" / f"{k:02d}"
        d.mkdir(parents=True)
        for name in smoke.STEM_NAMES:
            sf.write(str(d / f"{name}.wav"), 0.05 * rng.standard_normal((SR * 9, 2)).astype(np.float32), SR, subtype="FLOAT")
    return tmp_path


def run(project, *extra):
    out = project / "out"
    smoke.main(["--order", str(project / "order.json"), "--stems-dir", str(project / "stems"),
                "--bounds", str(project / "bounds.json"), "--out-dir", str(out),
                "--clips", "0:3", "--w-bars", str(W_BARS),
                "--ckpt-a", "a.ckpt", "--ckpt-b", "b.ckpt", "--chroma-head", "head.pt", *extra])
    return out, json.loads((out / "run_meta.json").read_text())


@pytest.fixture()
def fake_sa3(monkeypatch):
    """A fake stable_audio_3 + generative module; `behaviour` picks what dual_latch_guided_generate does."""
    torch = pytest.importorskip("torch")
    state = {"mode": "ok"}

    class FakeModel:
        @staticmethod
        def from_pretrained(*a, **k):
            return object()

    def fake_generate(**kw):
        if state["mode"] == "raise":
            raise RuntimeError("boom")
        n = int(round(kw["duration"] * SR)) - 100            # a little short: must be padded and logged
        x = 0.4 * torch.randn(2, n)
        if state["mode"] == "nan":
            x[0, 10] = float("nan")
        if state["mode"] == "huge":
            x[0, 10] = 1e11
        return x, SR

    m1 = types.ModuleType("stable_audio_3"); m1.StableAudioModel = FakeModel
    m2 = types.ModuleType("mixtape_v7_generative_inference"); m2.dual_latch_guided_generate = fake_generate
    monkeypatch.setitem(sys.modules, "stable_audio_3", m1)
    monkeypatch.setitem(sys.modules, "mixtape_v7_generative_inference", m2)
    monkeypatch.setattr(smoke, "chroma_morph_target", lambda a, b: torch.zeros(1, 384, 10))
    return state


def test_no_generate_renders_the_dsp_layers_and_labels_the_file(project):
    out, meta = run(project, "--no-generate")
    assert [t["other_path"] for t in meta["transitions"]] == ["skipped", "skipped"]
    for t in meta["transitions"]:
        x, sr = sf.read(str(out / t["file"]), dtype="float64")
        assert sr == SR and x.shape == (L, 2) and np.isfinite(x).all()
        assert t["file"].endswith("_skipped.wav")
        assert t["min_bass_power_gain"] == pytest.approx(1.0, abs=1e-6)   # no bass hole
        assert t["bpm_source"] == "order" and meta["kim_feedback"] is None


def test_missing_bpm_is_logged_not_silent(project):
    order = json.loads((project / "order.json").read_text())
    del order[0]["bpm"]
    (project / "order.json").write_text(json.dumps(order))
    _, meta = run(project, "--no-generate")
    assert meta["transitions"][0]["bpm_source"] == "default" and meta["transitions"][1]["bpm_source"] == "order"


def test_generative_path_pads_logs_and_level_matches(project, fake_sa3):
    out, meta = run(project)
    for t in meta["transitions"]:
        assert t["other_path"] == "generative" and t["file"].endswith("_generative.wav")
        assert t["other_len_delta"] == -100 and 0.25 <= t["other_gain"] <= 4.0
        assert sf.read(str(out / t["file"]))[0].shape[0] == L


@pytest.mark.parametrize("mode", ["nan", "huge", "raise"])
def test_failed_generation_stops_the_run_by_default(project, fake_sa3, mode):
    fake_sa3["mode"] = mode
    with pytest.raises((FloatingPointError, RuntimeError)):
        run(project)
    meta = json.loads((project / "out" / "run_meta.json").read_text())
    assert meta["transitions"][0]["other_path"] == "FAILED" and "error" in meta["transitions"][0]
    assert not list((project / "out").glob("*.wav"))          # nothing that could pass for a result


@pytest.mark.parametrize("mode", ["nan", "huge", "raise"])
def test_allow_fallback_continues_but_cannot_masquerade(project, fake_sa3, mode):
    fake_sa3["mode"] = mode
    out, meta = run(project, "--allow-fallback")
    assert [t["other_path"] for t in meta["transitions"]] == ["fallback_crossfade"] * 2
    assert all(p.name.endswith("_fallback_crossfade.wav") for p in out.glob("*.wav"))


def test_paths_are_required_not_hardcoded(monkeypatch):
    for var in smoke.ENV.values():
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit):
        smoke.main(["--no-generate"])                       # order / stems / out missing
    with pytest.raises(SystemExit):
        smoke.main(["--order", "o", "--stems-dir", "s", "--out-dir", "x"])   # generation needs ckpts and head
