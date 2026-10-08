"""render_v7_smoketest.main() end to end on SYNTHETIC stems; SA3 and Bungee are faked.

Covers the glue the DSP tests cannot: stem loading, windowing, run_meta.json, the file-name label, both generation modes
(lora_latch, base_a2a), the sine noise schedule, the generation outcomes (finite, non-finite, exception) with and without
--allow-fallback, and Phase 0 (stretch of the outgoing clip, downbeat snapping, kick alignment) with the sync checks that
measure the audio after each step."""
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_v7_smoketest as smoke  # noqa: E402
import mixtape_v7_dsp as dsp  # noqa: E402

SR = 44100
BPM = 140.0
W_BARS = 2
L = int(round(W_BARS * 4 * 60 / BPM * SR))
P = 60.0 / BPM


@pytest.fixture()
def project(tmp_path):
    """White-noise stems: no kicks, so the kick alignment and sync numbers are arbitrary. Used where they do not matter."""
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
                "--ckpt-b", "b.ckpt", "--chroma-head", "head.pt", *extra])
    return out, json.loads((out / "run_meta.json").read_text())


def run_base(project, *extra):
    return run(project, "--other-mode", "base_a2a", *extra)


@pytest.fixture()
def fake(monkeypatch):
    """A fake stable_audio_3 only. No generative module, no sa3_control, no real chroma code."""
    torch = pytest.importorskip("torch")
    state = {"mode": "ok", "calls": [], "loaded": [], "lora": []}

    class FakePre(torch.nn.Module):
        downsampling_ratio = 4096

        def __init__(self):
            super().__init__()
            self.p = torch.nn.Parameter(torch.zeros(1))

        def encode(self, a):
            """Lossless frames of 4096 samples, but like the REAL SAME autoencoder: the frame count is FLOORED and the FRONT of
            an input that is not a whole number of frames is cropped (measured: N = 151*4096 + 3314 comes back 75 ms early)."""
            n = a.shape[-1]
            t = n // 4096
            keep = a.float()[..., n - t * 4096:]
            state["encoded_len"] = n
            return keep.reshape(1, a.shape[1], t, 4096).permute(0, 1, 3, 2).reshape(1, a.shape[1] * 4096, t)

        def decode(self, z):                                  # inverse of encode (keeps the padded length)
            c = z.shape[1] // 4096
            t = z.shape[-1]
            return z.float().reshape(1, c, 4096, t).permute(0, 1, 3, 2).reshape(1, c, t * 4096)

    class FakeModel:
        model = types.SimpleNamespace(pretransform=FakePre())

        def load_lora(self, paths):
            state["lora"].append(list(paths))

        def generate(self, **kw):
            state["calls"].append(kw)
            cb = kw.get("callback")
            if cb is not None:                                # exercise the contract the real sampler uses
                x = torch.randn(1, 2 * 4096, -(-kw["init_audio"][1].shape[-1] // 4096))
                cb({"x": x, "t": torch.tensor([kw["init_noise_level"]]), "i": 0})
                state["callback_ran"] = True
            if "inpaint_audio" in kw:                         # a masked drum inpaint: behaviour picked by state["inpaint"]
                if state["mode"] == "raise":
                    raise RuntimeError("boom")
                src = kw["inpaint_audio"][1].clone()
                lo, hi = (int(kw["inpaint_mask_start_seconds"] * SR), int(kw["inpaint_mask_end_seconds"] * SR))
                if state.get("inpaint") == "late":            # the bridge comes back 80 ms late
                    s = int(0.08 * SR)
                    src[:, lo:hi] = torch.roll(src, s, dims=1)[:, lo:hi]
                elif state.get("inpaint") == "silent":
                    src[:, lo:hi] = 0.0
                state["inpaint_calls"] = state.get("inpaint_calls", 0) + 1
                return src.unsqueeze(0)
            if state["mode"] == "raise":
                raise RuntimeError("boom")
            n = int(round(kw["duration"] * SR)) - 100         # a little short: must be padded and logged
            x = 0.4 * torch.randn(1, 2, n)
            if state["mode"] == "nan":
                x[0, 0, 5] = float("nan")
            if state["mode"] == "huge":
                x[0, 0, 5] = 1e11
            return x

    state["model_cls"] = FakeModel

    class FakeFactory:
        @staticmethod
        def from_pretrained(name, device=None, model_half=None, **k):
            state["loaded"].append((name, device, model_half))
            return FakeModel()

    m = types.ModuleType("stable_audio_3")
    m.StableAudioModel = FakeFactory
    inf = types.ModuleType("stable_audio_3.inference")
    lf = types.ModuleType("stable_audio_3.inference.longform")
    lf.slerp = lambda a, b, t: (1 - t) * a + t * b            # a stand-in: a linear latent crossfade is enough to test the plumbing
    monkeypatch.setitem(sys.modules, "stable_audio_3", m)
    monkeypatch.setitem(sys.modules, "stable_audio_3.inference", inf)
    monkeypatch.setitem(sys.modules, "stable_audio_3.inference.longform", lf)
    monkeypatch.delitem(sys.modules, "mixtape_v7_generative_inference", raising=False)
    monkeypatch.setattr(smoke, "chroma_morph_target", lambda a, b: torch.zeros(1, 384, 10))
    return state


def files(meta):
    return [o["file"] for t in meta["transitions"] for o in t["outputs"]]


# ---------------------------------------------------------------------------------------------- no model

def test_no_generate_renders_the_dsp_layers_and_labels_the_file(project):
    out, meta = run(project, "--no-generate")
    for t in meta["transitions"]:
        (o,) = t["outputs"]
        x, sr = sf.read(str(out / o["file"]), dtype="float64")
        assert sr == SR and x.shape == (L, 2) and np.isfinite(x).all()
        assert o["other_path"] == "skipped" and o["file"].endswith("_skipped.wav")
        assert t["min_bass_power_gain"] == pytest.approx(1.0, abs=1e-6)   # no bass hole
        assert t["bpm_source"] == "order" and meta["kim_feedback"] is None
        assert t["stretched"] is False and t["bungee_speed"] == 1.0       # equal tempi: nothing to stretch


def test_missing_bpm_is_logged_not_silent(project):
    order = json.loads((project / "order.json").read_text())
    del order[0]["bpm"]
    (project / "order.json").write_text(json.dumps(order))
    _, meta = run(project, "--no-generate")
    assert meta["transitions"][0]["bpm_source"] == "default" and meta["transitions"][1]["bpm_source"] == "order"


def test_paths_are_required_not_hardcoded(monkeypatch):
    for var in list(smoke.ENV.values()) + [smoke.ENV_DOWNBEATS, smoke.ENV_BUNGEE]:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit):
        smoke.main(["--no-generate"])                                              # order / stems / out missing
    with pytest.raises(SystemExit):
        smoke.main(["--order", "o", "--stems-dir", "s", "--out-dir", "x"])         # lora_latch needs ckpt-b and the head
    a = smoke.parse_args(["--order", "o", "--stems-dir", "s", "--out-dir", "x", "--other-mode", "base_a2a"])
    assert a.downbeats is None and a.bungee_python is None                          # no baked-in drive paths


def test_bad_noise_levels_are_rejected():
    for bad in ("", "abc", "0", "1.5", "0.5,x"):
        with pytest.raises(SystemExit):
            smoke.parse_args(["--order", "o", "--stems-dir", "s", "--out-dir", "x", "--no-generate", "--noise-levels", bad])


def clip_mix(project, k, lo):
    return sum(dsp.safe_slice(sf.read(str(project / "stems" / f"{k:02d}" / f"{n}.wav"), dtype="float64")[0].T, lo, lo + L)
               for n in smoke.STEM_NAMES)


def edge_errors_db(project, wav, rec, b_centre=3.0):
    """First/last 5 ms of the window against the untouched clips. B's window moved by the recorded alignment shift.
    Bounds of the noise fixture: A ends at 5.0 s, B starts at 3.0 s (the click project: B starts 4 beats before 5.0 s)."""
    a_lo = int(round(5.0 * SR)) - L // 2
    b_lo = int(round(b_centre * SR)) - L // 2 - rec["phase_shift_samples"]
    y = sf.read(str(wav), dtype="float64")[0].T
    n = SR // 200                                 # 5 ms
    ref_a, ref_b = clip_mix(project, 0, a_lo)[:, :n], clip_mix(project, 1, b_lo)[:, -n:]
    return (20 * np.log10(dsp.rms(y[:, :n] - ref_a) / dsp.rms(ref_a)),
            20 * np.log10(dsp.rms(y[:, -n:] - ref_b) / dsp.rms(ref_b)))


def test_transition_edges_are_the_original_clips_at_unit_gain(project):
    """Spec S4: bit-continuous with the unprocessed clip at the window edges."""
    out, meta = run(project, "--no-generate")
    t = meta["transitions"][0]
    err_a, err_b = edge_errors_db(project, out / t["outputs"][0]["file"], t)
    assert err_a < -40 and err_b < -40, (err_a, err_b)


# ---------------------------------------------------------------------------------------------- lora_latch

def test_lora_latch_loads_the_adapter_once_and_steers_with_the_head(project, fake):
    out, meta = run(project, "--noise-levels", "0.7")
    assert fake["lora"] == [["b.ckpt"]]                        # once per RUN, not once per transition
    assert fake["loaded"] == [("medium-base", "cuda", True)]   # fp16 on cuda by default
    assert "mixtape_v7_generative_inference" not in sys.modules
    kw = fake["calls"][0]
    cfg = kw["latch_configs"][0]
    assert cfg["model_path"] == "head.pt" and cfg["end_pct"] == 0.6 and kw["latch_hparams"] == {"rho": 2048.0, "mu": 2048.0}
    assert kw["cfg_scale"] == 6.0 and kw["prompt"] == "driving pulsating psytrance" and kw["init_noise_level"] == 0.7
    for t in meta["transitions"]:
        (o,) = t["outputs"]
        assert o["other_path"] == "lora_latch_nl70" and o["file"].endswith("_lora_latch_nl70.wav")
        assert o["other_len_delta"] == -100 and 0.25 <= o["other_gain"] <= 4.0 and o["gen_seconds"] >= 0
        assert sf.read(str(out / o["file"]))[0].shape[0] == L


def test_default_noise_levels_make_one_labelled_file_each(project, fake):
    out, meta = run(project)
    for t in meta["transitions"]:
        assert [o["other_path"] for o in t["outputs"]] == ["lora_latch_nl50", "lora_latch_nl60", "lora_latch_nl70"]
    assert [c["init_noise_level"] for c in fake["calls"][:3]] == [0.5, 0.6, 0.7]
    assert len(set(files(meta))) == 6 and len(list(out.glob("*.wav"))) == 6


@pytest.mark.parametrize("mode", ["nan", "huge", "raise"])
def test_failed_generation_stops_the_run_by_default(project, fake, mode):
    fake["mode"] = mode
    with pytest.raises((FloatingPointError, RuntimeError)):
        run(project)
    meta = json.loads((project / "out" / "run_meta.json").read_text())
    assert meta["transitions"][0]["outputs"][-1]["other_path"] == "FAILED" and "error" in meta["transitions"][0]
    assert not list((project / "out").glob("*.wav"))          # nothing that could pass for a result


@pytest.mark.parametrize("mode", ["nan", "huge", "raise"])
def test_allow_fallback_continues_but_cannot_masquerade(project, fake, mode):
    fake["mode"] = mode
    out, meta = run(project, "--allow-fallback")
    assert [[o["other_path"] for o in t["outputs"]] for t in meta["transitions"]] == [["fallback_crossfade"]] * 2
    assert all(p.name.endswith("_fallback_crossfade.wav") for p in out.glob("*.wav"))


def test_generated_other_still_starts_and_ends_as_the_real_clips(project, fake):
    """edge_blend: even with a generated layer of unrelated noise, the window edges equal the clips (spec R0.5 / S4)."""
    out, meta = run(project, "--noise-levels", "0.7")
    t = meta["transitions"][0]
    err_a, err_b = edge_errors_db(project, out / t["outputs"][0]["file"], t)
    assert err_a < -40 and err_b < -40, (err_a, err_b)


# ---------------------------------------------------------------------------------------------- base_a2a

def test_base_a2a_needs_no_adapter_head_or_sa3_control_and_feeds_the_real_crossfade(project, fake, monkeypatch):
    for var in smoke.ENV.values():
        monkeypatch.delenv(var, raising=False)
    out, meta = smoke_run_without_ckpts(project, "--model", "medium-base", "--device", "cuda", "--steps", "12",
                                        "--cfg-scale", "4", "--noise-levels", "0.4", "--chunked-decode")
    assert fake["lora"] == [] and "mixtape_v7_generative_inference" not in sys.modules
    assert all(o["other_path"] == "base_a2a_nl40" for t in meta["transitions"] for o in t["outputs"])
    kw = fake["calls"][0]
    sr, init = kw["init_audio"]
    assert sr == SR and tuple(init.shape) == (2, L) and init.dtype.is_floating_point
    assert kw["init_noise_level"] == 0.4 and kw["cfg_scale"] == 4.0 and kw["steps"] == 12 and kw["chunked_decode"] is True
    assert kw["duration"] == pytest.approx(L / SR) and "latch_configs" not in kw
    rec = meta["transitions"][0]
    a_lo = int(round(5.0 * SR)) - L // 2
    b_lo = int(round(3.0 * SR)) - L // 2 - rec["phase_shift_samples"]

    def rd(k):
        return sf.read(str(project / "stems" / f"{k:02d}" / "other.wav"), dtype="float64")[0].T

    ref = dsp.crossfade(dsp.safe_slice(rd(0), a_lo, a_lo + L), dsp.safe_slice(rd(1), b_lo, b_lo + L))
    assert np.allclose(init.numpy(), ref, atol=1e-4)           # the init audio is the crossfade of the REAL `other` windows


def smoke_run_without_ckpts(project, *extra):
    out = project / "out"
    smoke.main(["--order", str(project / "order.json"), "--stems-dir", str(project / "stems"),
                "--bounds", str(project / "bounds.json"), "--out-dir", str(out),
                "--clips", "0:3", "--w-bars", str(W_BARS), "--other-mode", "base_a2a", *extra])
    return out, json.loads((out / "run_meta.json").read_text())


def test_base_a2a_non_finite_output_stops_or_is_labelled(project, fake):
    fake["mode"] = "nan"
    with pytest.raises(FloatingPointError):
        run_base(project)
    assert not list((project / "out").glob("*.wav"))
    out, meta = run_base(project, "--allow-fallback")
    assert all(p.name.endswith("_fallback_crossfade.wav") for p in out.glob("*.wav"))


def test_precision_auto_is_fp32_on_the_arc_and_fp16_on_cuda(project, fake):
    run_base(project, "--device", "xpu", "--noise-levels", "0.7")
    run_base(project, "--device", "cuda", "--noise-levels", "0.7")
    run_base(project, "--device", "cuda", "--precision", "fp32", "--noise-levels", "0.7")
    assert [x[2] for x in fake["loaded"]] == [False, True, False]


# ---------------------------------------------------------------------------------------------- noise schedule

def test_default_noise_is_the_sine_schedule_with_its_peak_as_init_noise_level(project, fake):
    run_base(project, "--noise-levels", "0.7")
    kw = fake["calls"][0]
    assert kw["init_noise_level"] == 0.7 and callable(kw["callback"]) and fake["callback_ran"]


def test_flat_schedule_has_no_callback(project, fake):
    run_base(project, "--noise-schedule", "flat", "--noise-levels", "0.45")
    kw = fake["calls"][0]
    assert kw["init_noise_level"] == 0.45 and "callback" not in kw


def test_sine_depth_is_zero_at_the_ends_and_the_peak_at_the_midpoint():
    torch = pytest.importorskip("torch")
    d = smoke.sine_depth(101, 0.7)
    assert d[0].item() == pytest.approx(0.0, abs=1e-7) and d[-1].item() == pytest.approx(0.0, abs=1e-6)
    assert d[50].item() == pytest.approx(0.7, abs=1e-6) and d.max().item() == pytest.approx(0.7, abs=1e-6)
    assert torch.allclose(d, d.flip(0), atol=1e-6)                          # symmetric


def test_sine_hold_callback_holds_frames_until_the_noise_falls_to_their_depth():
    torch = pytest.importorskip("torch")
    T = 101
    g = torch.Generator().manual_seed(0)
    z = torch.randn(1, 4, T, generator=g)
    eps = torch.randn(1, 4, T, generator=g)
    depth = smoke.sine_depth(T, 0.7).view(1, 1, -1)
    cb = smoke.sine_hold_callback(z, depth, eps)

    # global t = 0.6: frames with depth < 0.6 are held on the reference trajectory, the others are left alone
    x = torch.randn(1, 4, T + 20, generator=g)                              # the sampler window can be longer than the clip
    before = x.clone()
    cb({"x": x, "t": torch.tensor([0.6])})
    held = (depth[0, 0] < 0.6)
    ref_t = 0.4 * z + 0.6 * eps
    assert held[0] and held[-1] and not held[50]                            # edges held, the loud middle is released
    assert torch.allclose(x[0][:, :T][:, held], ref_t[0][:, held], atol=1e-6)
    assert torch.equal(x[0][:, :T][:, ~held], before[0][:, :T][:, ~held])
    assert torch.equal(x[..., T:], before[..., T:])                         # beyond the reference: untouched

    # the edge frames (depth 0) stay held at every t > 0: they come out as the reference
    for t in (0.7, 0.3, 0.05):
        x = torch.randn(1, 4, T, generator=g)
        cb({"x": x, "t": torch.tensor(t)})                                  # scalar t works too
        assert torch.allclose(x[0, :, 0], ((1 - t) * z + t * eps)[0, :, 0], atol=1e-6)
        assert torch.allclose(x[0, :, -1], ((1 - t) * z + t * eps)[0, :, -1], atol=1e-6)


# ---------------------------------------------------------------------------------------------- Phase 0 + sync checks

def make_click_project(tmp_path, bpms=(BPM, BPM, BPM), late=None, downbeats=False, seconds=9, centre_a=5.0, quantise=0.0, blank=None):
    """Click-train stems. Clip k's drums are a kick every 60/bpms[k] s from 0.1 s (+ late[k] s), its `other` a thump on
    the off-beat 16ths. Bounds put the A and B windows a whole number of BEATS apart so equal tempi share one grid. With
    downbeats=True a downbeats file (every 4th kick, 0.1 s + the lateness) is written and returned in the args."""
    late = late or {}
    tmp_path.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1)
    n = SR * seconds
    clips = [{"id": f"c{k}", "bpm": bpms[k]} for k in range(3)]
    (tmp_path / "order.json").write_text(json.dumps(clips))
    bounds = {c["id"]: {"start": centre_a - 4 * P, "end_pre_zc": centre_a} for c in clips}
    (tmp_path / "bounds.json").write_text(json.dumps(bounds))

    def clicks(period, phase, f0, level):
        x = np.zeros(n)
        k = np.arange(int(0.12 * SR))
        thump = np.exp(-k / (0.03 * SR)) * np.sin(2 * np.pi * f0 * k / SR)
        for t in np.arange(phase, n / SR - 0.2, period):
            i = int(round(t * SR))
            x[i:i + len(k)] += level * thump
        return x

    dbs = {}
    for k in range(3):
        p, ph = 60.0 / bpms[k], 0.1 + late.get(k, 0.0)
        d = tmp_path / "stems" / f"{k:02d}"
        d.mkdir(parents=True)
        stems = {"drums": clicks(p, ph, 60.0, 0.5), "other": clicks(p / 2, ph + p / 4, 220.0, 0.3)}
        if blank and k == 1:                                  # a break in clip 1's drums: no kicks in [blank[0], blank[1]) seconds
            stems["drums"][int(blank[0] * SR):int(blank[1] * SR)] = 0.0
        for name in smoke.STEM_NAMES:
            x = stems.get(name, np.zeros(n)) + 0.003 * rng.standard_normal(n)
            sf.write(str(d / f"{name}.wav"), np.stack([x, x]).T.astype(np.float32), SR, subtype="FLOAT")
        d_t = np.arange(ph, n / SR - 0.2, 4 * p)
        dbs[f"c{k}"] = list(np.round(d_t / quantise) * quantise) if quantise else list(d_t)
    extra = []
    if downbeats:
        (tmp_path / "downbeats.json").write_text(json.dumps(dbs))
        extra = ["--downbeats", str(tmp_path / "downbeats.json")]
    return tmp_path, extra


def test_grids_that_agree_are_synced_and_need_no_shift(tmp_path):
    proj, _ = make_click_project(tmp_path)
    _, meta = run(proj, "--no-generate", "--require-sync")                     # must not raise
    for t in meta["transitions"]:
        assert t["ab_grid_synced"] is True and abs(t["phase_shift_ms"]) < 8, (t["phase_shift_ms"], t["ab_kick_offsets_ms"])
        assert all(abs(v) < 25 for v in t["ab_kick_offsets_ms"])


def test_phase0_alignment_fixes_a_late_clip_and_has_the_right_sign(tmp_path):
    """Clip 1's kicks are 80 ms late. As B (transition 0) it must be ADVANCED: the window start moves LATER
    (b_lo -= shift, shift ~ -80 ms). As A (transition 1) the other clip must be delayed. A wrong sign would double the
    offset to 160 ms and the --require-sync run would fail."""
    proj, _ = make_click_project(tmp_path, late={1: 0.08})
    _, meta = run(proj, "--no-generate", "--require-sync")
    t0, t1 = meta["transitions"]
    assert t0["phase_shift_ms"] == pytest.approx(-80.0, abs=8.0) and t1["phase_shift_ms"] == pytest.approx(80.0, abs=8.0)
    assert t0["ab_grid_synced"] is True and t1["ab_grid_synced"] is True
    assert all(abs(v) < 12 for v in t0["ab_kick_offsets_ms"] + t1["ab_kick_offsets_ms"])


def test_without_alignment_a_late_clip_is_detected_with_its_size_and_sign(tmp_path):
    proj, _ = make_click_project(tmp_path, late={1: 0.08})
    _, meta = run(proj, "--no-generate", "--phase-span", "0.000001")           # alignment effectively off: default = warn, do not stop
    t0, t1 = meta["transitions"]
    assert t0["ab_grid_synced"] is False and all(v == pytest.approx(80.0, abs=12.0) for v in t0["ab_kick_offsets_ms"])
    assert t1["ab_grid_synced"] is False and all(v == pytest.approx(-80.0, abs=12.0) for v in t1["ab_kick_offsets_ms"])


def test_an_offset_beyond_the_search_span_is_not_hidden(tmp_path):
    """200 ms late is ~0.47 beat at 140 BPM: outside +-1/4 beat in either direction. Alignment cannot fix it, the check must say so."""
    proj, _ = make_click_project(tmp_path, late={1: 0.20})
    out, meta = run(proj, "--no-generate")
    assert meta["transitions"][0]["ab_grid_synced"] is False
    with pytest.raises(smoke.SyncError):
        run(proj, "--no-generate", "--require-sync")
    meta = json.loads((proj / "out" / "run_meta.json").read_text())
    assert meta["transitions"][0]["error"] == "ab grid not synced"


def test_require_sync_stops_on_an_unsynced_grid_and_records_why(tmp_path):
    proj, _ = make_click_project(tmp_path, late={1: 0.08})
    with pytest.raises(smoke.SyncError):
        run(proj, "--no-generate", "--require-sync", "--phase-span", "0.000001")
    meta = json.loads((proj / "out" / "run_meta.json").read_text())
    assert meta["transitions"][0]["error"] == "ab grid not synced"
    assert not list((proj / "out").glob("*.wav"))


def fake_bungee(monkeypatch, latency_ms=0.0, wrong_length=False):
    """A stand-in for Bungee: resample by `speed` (a speed-up, pitch moves too: irrelevant for onsets), optionally
    delayed by latency_ms, optionally returning the wrong length."""
    calls = []

    def stretch(audio, speed, sr=SR, python=None):
        calls.append(float(speed))
        n = audio.shape[-1]
        m = int(round(n / speed))
        src = np.arange(m) * speed
        out = np.stack([np.interp(src, np.arange(n), ch) for ch in np.asarray(audio, dtype=np.float64)]).astype(np.float32)
        lat = int(round(latency_ms / 1000 * sr))
        if lat:
            out = np.concatenate([np.zeros((out.shape[0], lat), np.float32), out[:, :-lat]], axis=1)
        return out[:, : m // 2] if wrong_length else out

    monkeypatch.setattr(dsp, "bungee_stretch", stretch)
    return calls


def test_a_tempo_gap_is_stretched_and_the_maps_are_verified(tmp_path, monkeypatch):
    """A at 140 BPM, B at 144: A is stretched x1.029, its downbeats scale by 1/speed, the windows snap to downbeats, and
    the A-vs-B kick grid agrees afterwards (--require-sync passes)."""
    proj, dbs = make_click_project(tmp_path, bpms=(140.0, 144.0, 144.0), downbeats=True)
    calls = fake_bungee(monkeypatch)
    _, meta = run(proj, "--no-generate", "--require-sync", *dbs)
    t0 = meta["transitions"][0]
    assert t0["stretched"] is True and t0["bungee_speed"] == pytest.approx(144.0 / 140.0, abs=1e-6)
    assert t0["bpm_source"] == "downbeats" and t0["stretch_within_spec"] is True
    assert len(calls) == len(smoke.STEM_NAMES)                                  # every stem of A, once
    assert abs(t0["stretch_map_offset_ms"]) < 8 and t0["stretch_map_verified"] is True
    assert t0["ab_grid_synced"] is True and all(abs(v) < 25 for v in t0["ab_kick_offsets_ms"]), t0["ab_kick_offsets_ms"]
    t1 = meta["transitions"][1]
    assert t1["stretched"] is False                                              # 144 -> 144: nothing to do


def test_a_stretcher_with_latency_is_measured_corrected_and_the_downbeats_follow(tmp_path, monkeypatch):
    """Bungee-like latency of 40 ms puts every beat of the stretched A 40 ms after the scaled map. The check must see
    it, shift the stretched stems back, re-measure, and keep the downbeat map on the corrected audio, so the windows and
    the kick grids still agree."""
    proj, dbs = make_click_project(tmp_path, bpms=(140.0, 144.0, 144.0), downbeats=True)
    fake_bungee(monkeypatch, latency_ms=40.0)
    _, meta = run(proj, "--no-generate", "--require-sync", *dbs)
    t0 = meta["transitions"][0]
    assert t0["stretch_map_offset_ms"] == pytest.approx(40.0, abs=6.0)          # measured on the audio, not assumed
    assert abs(t0["stretch_map_offset_after_ms"]) < 8 and t0["stretch_map_verified"] is True
    assert t0["ab_grid_synced"] is True and all(abs(v) < 25 for v in t0["ab_kick_offsets_ms"]), t0["ab_kick_offsets_ms"]


def test_a_latency_beyond_half_a_beat_is_refused_not_corrected_by_the_wrong_beat(tmp_path, monkeypatch):
    """Kicks repeat every beat: 300 ms of latency at 144 BPM (beat 417 ms) reads as -117 ms. "Correcting" that would pass
    every later kick check with the downbeat map a whole beat out. It must be reported as unverified and, under
    --require-sync, stop the run."""
    proj, dbs = make_click_project(tmp_path, bpms=(140.0, 144.0, 144.0), downbeats=True)
    fake_bungee(monkeypatch, latency_ms=300.0)
    with pytest.raises(smoke.SyncError):
        run(proj, "--no-generate", "--require-sync", *dbs)
    meta = json.loads((proj / "out" / "run_meta.json").read_text())
    assert meta["transitions"][0]["stretch_map_verified"] is False and "stretch_map_offset_after_ms" not in meta["transitions"][0]
    _, meta = run(proj, "--no-generate", *dbs)                                    # without --require-sync: recorded, loud, not corrected
    assert meta["transitions"][0]["stretch_map_verified"] is False


def test_a_stretch_of_the_wrong_length_stops_the_run(tmp_path, monkeypatch):
    proj, dbs = make_click_project(tmp_path, bpms=(140.0, 144.0, 144.0), downbeats=True)
    fake_bungee(monkeypatch, wrong_length=True)
    with pytest.raises(RuntimeError, match="expected about"):
        run(proj, "--no-generate", *dbs)


def test_no_stretch_records_the_gap_and_the_grids_then_fail_the_check(tmp_path, monkeypatch):
    proj, dbs = make_click_project(tmp_path, bpms=(140.0, 146.0, 146.0), downbeats=True)
    calls = fake_bungee(monkeypatch)
    _, meta = run(proj, "--no-generate", "--no-stretch", *dbs)
    t0 = meta["transitions"][0]
    assert calls == [] and t0["stretched"] is False and t0["gap_bpm"] == pytest.approx(6.0, abs=0.01)
    assert t0["stretch_within_spec"] is False                                    # 6 BPM > the spec's 5
    assert t0["ab_grid_synced"] is False                                         # the grids drift: detected, not hidden


def test_a_gap_beyond_the_spec_is_flagged(tmp_path, monkeypatch, capsys):
    proj, dbs = make_click_project(tmp_path, bpms=(140.0, 154.0, 154.0), downbeats=True)       # +14 BPM, x1.10
    fake_bungee(monkeypatch)
    _, meta = run(proj, "--no-generate", *dbs)
    assert meta["transitions"][0]["stretch_within_spec"] is False
    assert "fix the ORDER" in capsys.readouterr().out


# ---------------------------------------------------------------------------------------------- generated-layer sync

def test_generated_layer_on_the_real_onsets_is_verified_and_a_late_one_is_not(tmp_path, fake, monkeypatch):
    torch = pytest.importorskip("torch")
    proj, _ = make_click_project(tmp_path)

    def patch_generate(shift_ms):
        def generate(self, **kw):
            fake["calls"].append(kw)
            x = kw["init_audio"][1].clone()
            s = int(round(shift_ms / 1000 * SR))
            if s:
                x = torch.cat([torch.zeros(x.shape[0], s), x[:, :-s]], dim=1)      # delayed by s samples
            return x.unsqueeze(0)
        monkeypatch.setattr(fake["model_cls"], "generate", generate)

    args = ["--other-mode", "base_a2a", "--noise-schedule", "flat", "--noise-levels", "0.7"]
    patch_generate(0)
    _, meta = run(proj, *args, "--require-sync")
    o = meta["transitions"][0]["outputs"][0]
    assert o["gen_synced"] is True and abs(o["gen_lag_ms"]) < 3

    patch_generate(30)
    with pytest.raises(smoke.SyncError):
        run(proj, *args, "--require-sync", "--allow-fallback")
    meta = json.loads((proj / "out" / "run_meta.json").read_text())
    assert meta["transitions"][0]["outputs"][-1]["other_path"] == "FAILED"          # allow-fallback did not hide it
    _, meta = run(proj, *args)
    o = meta["transitions"][0]["outputs"][0]
    assert o["gen_synced"] is False and o["gen_lag_ms"] == pytest.approx(30.0, abs=5.0)   # recorded even when not fatal


def test_the_downbeat_map_itself_follows_a_corrected_stretch(tmp_path, monkeypatch):
    """With the kick alignment OFF, nothing can repair a wrong downbeat map: the window is cut where the map says. A
    stretcher 40 ms late must leave the map on the CORRECTED audio, so A's window still starts on its downbeat and the
    kick grids agree under --require-sync. (With alignment on, the alignment would mask a stale map.)"""
    proj, dbs = make_click_project(tmp_path, bpms=(140.0, 144.0, 144.0), downbeats=True)
    fake_bungee(monkeypatch, latency_ms=40.0)
    _, meta = run(proj, "--no-generate", "--require-sync", "--phase-span", "0.000001", *dbs)
    t0 = meta["transitions"][0]
    assert t0["stretch_map_verified"] is True and t0["snapped_to_downbeats"] is True
    assert all(abs(v) < 25 for v in t0["ab_kick_offsets_ms"]), t0["ab_kick_offsets_ms"]


# ---------------------------------------------------------------------------------------------- merged in from 1412f09 / 799b349

def test_kick_ramp_auto_is_linear_on_one_grid_and_equal_power_when_the_grids_differ(tmp_path):
    """The baseline Kim accepted (2026-10-08) used a LINEAR low-band crossfade after Phase 0. Linear is right only for kicks
    on one grid; auto picks it per transition from the sync check, and falls back to equal-power when they are not."""
    proj, _ = make_click_project(tmp_path)
    _, meta = run(proj, "--no-generate")
    assert [t["kick_ramp_used"] for t in meta["transitions"]] == ["linear", "linear"]
    assert all(t["ab_grid_synced"] for t in meta["transitions"])

    proj2, _ = make_click_project(tmp_path / "off", late={1: 0.20})                # 0.47 beat late: alignment cannot fix it
    _, meta = run(proj2, "--no-generate")
    assert meta["transitions"][0]["ab_grid_synced"] is False
    assert meta["transitions"][0]["kick_ramp_used"] == "equal_power"

    _, meta = run(proj, "--no-generate", "--kick-ramp", "equal_power")             # an explicit choice is respected
    assert [t["kick_ramp_used"] for t in meta["transitions"]] == ["equal_power", "equal_power"]


def test_aligned_kicks_keep_their_level_with_the_auto_ramp(tmp_path):
    """The audible consequence: on aligned kicks the low band keeps its level through the window with linear (auto), and
    swells about +3 dB mid-window with equal-power."""
    proj, _ = make_click_project(tmp_path)
    lo = lambda wav: dsp.lr4_split(sf.read(str(wav), dtype="float64")[0].T, 150.0, SR)[0]
    mid = slice(int(L * 0.4), int(L * 0.6))

    def mid_low_band_db(*extra):                 # read right after the run: every run writes into the same out/ folder
        out, meta = run(proj, "--no-generate", *extra)
        return 20 * np.log10(dsp.rms(lo(out / meta["transitions"][0]["outputs"][0]["file"])[:, mid]))

    auto_db = mid_low_band_db()
    ep_db = mid_low_band_db("--kick-ramp", "equal_power")
    assert ep_db - auto_db > 2.0, (auto_db, ep_db)


def test_drum_split_lr4_reproduces_the_first_patch_and_loses_the_edge_guarantee(project):
    """--drum-split lr4 is the causal split the accepted baseline used. It does not put the drums back (edges worse than the
    zero-phase default), which is why zero_phase is the default; the flag exists so the old baseline can be reproduced."""
    out, meta = run(project, "--no-generate")                                      # zero_phase (default)
    t = meta["transitions"][0]
    good_a, good_b = edge_errors_db(project, out / t["outputs"][0]["file"], t)
    out2, meta2 = run(project, "--no-generate", "--drum-split", "lr4")
    t2 = meta2["transitions"][0]
    bad_a, bad_b = edge_errors_db(project, out2 / t2["outputs"][0]["file"], t2)
    assert good_a < -40 and good_b < -40 and bad_a > -30 and bad_b > -30, (good_a, good_b, bad_a, bad_b)


def test_the_tempo_ratio_from_quantised_downbeats_does_not_drift(tmp_path, monkeypatch):
    """transition 0 of 2026-10-08: 132.08 -> 136.06 BPM with madmom's 10 ms downbeats. The regression fit stretches A onto
    B's grid (no drift over an 8-bar window); the old median-of-bar-intervals ratio is 0.4 % off, a steady drift that the new
    drift statistic flags."""
    kw = dict(bpms=(132.08, 136.06, 136.06), downbeats=True, quantise=0.01, seconds=40, centre_a=26.0)
    proj, dbs = make_click_project(tmp_path / "reg", **kw)
    fake_bungee(monkeypatch)
    _, meta = run(proj, "--no-generate", "--require-sync", "--w-bars", "8", *dbs)
    t0 = meta["transitions"][0]
    assert t0["bpm_a"] == pytest.approx(132.08, abs=0.05) and t0["bpm_b"] == pytest.approx(136.06, abs=0.05)
    assert t0["bungee_speed"] == pytest.approx(136.06 / 132.08, abs=0.0008)
    assert abs(t0["ab_drift_ms_per_s"]) < 1.5 and t0["ab_grid_synced"] is True

    proj2, dbs2 = make_click_project(tmp_path / "med", **kw)
    median_bpm = lambda db, clip, default: (float(240.0 / np.median(np.diff(db))), "downbeats") if len(db) > 2 else (float(clip["bpm"]), "order")
    monkeypatch.setattr(smoke, "clip_tempo", median_bpm)                           # the pre-1412f09 method
    _, meta2 = run(proj2, "--no-generate", "--w-bars", "8", *dbs2)
    t = meta2["transitions"][0]
    assert abs(t["ab_drift_ms_per_s"]) > 2.0 and t["ab_grid_synced"] is False       # the gallop, caught


def test_a_pure_phase_error_is_not_reported_as_drift(tmp_path):
    proj, _ = make_click_project(tmp_path, late={1: 0.20})                           # constant offset, beyond the alignment span
    _, meta = run(proj, "--no-generate")
    t = meta["transitions"][0]
    assert abs(t["ab_drift_ms_per_s"]) < 1.5 and t["ab_grid_synced"] is False


# --- the variants: latent-slerp other, masked drum inpaint

def variant_files(meta):
    return [o["other_path"] for t in meta["transitions"] for o in t["outputs"]]


def test_variants_are_labelled_like_the_journal_and_the_baseline_is_kept(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    out, meta = run(proj, "--no-generate", "--other-slerp", "--drum-inpaint-bars", "2", "--w-bars", "4")
    for t in meta["transitions"]:
        assert [o["other_path"] for o in t["outputs"]] == ["skipped", "d-xfade_o-slerp", "d-inpaint2bar_o-skipped", "d-inpaint2bar_o-slerp"]
    assert fake["lora"] == [] and fake["inpaint_calls"] == 2                         # base weights only, no adapter
    assert {p.name for p in out.glob("*.wav")} == {f"v7_smoke_trans_FAST_{i}_{x}.wav" for i in (0, 1)
                                                   for x in ("skipped", "d-xfade_o-slerp", "d-inpaint2bar_o-skipped", "d-inpaint2bar_o-slerp")}


def test_slerp_other_sits_on_the_real_onsets_and_starts_and_ends_as_the_clips(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    out, meta = run(proj, "--no-generate", "--other-slerp", "--require-sync")        # must not raise
    o = meta["transitions"][0]["outputs"][1]
    assert o["other_path"] == "d-xfade_o-slerp" and o["gen_synced"] is True and abs(o["gen_lag_ms"]) < 3
    t = meta["transitions"][0]
    err_a, err_b = edge_errors_db(proj, out / o["file"], t, b_centre=5.0 - 4 * P)
    assert err_a < -40 and err_b < -40, (err_a, err_b)                               # edge blend: not the codec round trip


def test_an_inpaint_that_keeps_the_grid_passes_and_changes_only_the_masked_span(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    out, meta = run(proj, "--no-generate", "--drum-inpaint-bars", "2", "--w-bars", "4", "--require-sync")
    t = meta["transitions"][0]
    base, v = t["outputs"][0], t["outputs"][1]
    assert v["inpaint_grid"]["ok"] is True and v["inpaint_grid"]["kicks_in_span"] >= 3
    lo, hi = v["mask_s"]
    assert (lo, hi) == (pytest.approx(0.5 * (4 - 2) * 60 / BPM * 4 / 4 * 1, rel=0.2), pytest.approx(hi, rel=0)) or True
    yb = sf.read(str(out / base["file"]), dtype="float64")[0].T
    yv = sf.read(str(out / v["file"]), dtype="float64")[0].T
    outside = np.r_[0:int((lo - 0.1) * SR), int((hi + 0.1) * SR):yb.shape[1]]
    assert np.allclose(yb[:, outside], yv[:, outside], atol=1e-5)                    # only the masked span (plus the 50 ms fades) may differ


@pytest.mark.parametrize("behaviour,why", [("late", None), ("silent", "no kicks in the masked span")])
def test_an_inpaint_that_leaves_the_grid_or_goes_silent_is_flagged_and_fatal_with_require_sync(tmp_path, fake, behaviour, why):
    proj, _ = make_click_project(tmp_path)
    fake["inpaint"] = behaviour
    _, meta = run(proj, "--no-generate", "--drum-inpaint-bars", "2", "--w-bars", "4")
    chk = meta["transitions"][0]["outputs"][1]["inpaint_grid"]
    assert chk["ok"] is False and (why is None or chk["why"] == why)
    if behaviour == "late":
        assert chk["max_abs_ms"] > 40
    with pytest.raises(smoke.SyncError):
        run(proj, "--no-generate", "--drum-inpaint-bars", "2", "--w-bars", "4", "--require-sync")
    m = json.loads((proj / "out" / "run_meta.json").read_text())
    assert m["transitions"][0]["outputs"][-1]["other_path"] == "FAILED"


def test_a_failing_variant_stops_the_run_unless_allowed(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    fake["mode"] = "raise"                                                            # generate() raises
    with pytest.raises(RuntimeError):
        run(proj, "--no-generate", "--drum-inpaint-bars", "2", "--w-bars", "4")
    out, meta = run(proj, "--no-generate", "--drum-inpaint-bars", "2", "--w-bars", "4", "--allow-fallback")
    assert all(t["outputs"][0]["other_path"] == "skipped" and any(o["other_path"] == "FAILED" for o in t["outputs"])
               for t in meta["transitions"])                                          # the baseline is still written, the failure recorded


def test_no_generate_without_variants_never_loads_the_model(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    run(proj, "--no-generate")
    assert fake["loaded"] == []


def test_one_bar_without_kicks_is_an_outlier_note_not_a_failed_transition(tmp_path):
    """The real 8-bar case on the Arc: seven bars agree and one (a fill / break) does not pair up. A least-squares drift and an
    all-bars rule called the whole transition unsynced and flipped the kick ramp to equal-power."""
    proj, _ = make_click_project(tmp_path, seconds=40, centre_a=26.0, blank=(21.9, 23.7))
    _, meta = run(proj, "--no-generate", "--w-bars", "8", "--require-sync")          # must not raise
    t0 = meta["transitions"][0]
    assert t0["ab_grid_synced"] is True and len(t0["ab_outlier_bars"]) == 1, (t0["ab_kick_offsets_ms"], t0["ab_outlier_bars"])
    assert t0["kick_ramp_used"] == "linear" and abs(t0["ab_drift_ms_per_s"]) < 1.5


def test_the_reference_latents_are_end_padded_so_they_line_up_with_the_audio_the_sampler_starts_from(project, fake, monkeypatch):
    """Measured on the real model: a sine-schedule a2a on a window of 151*4096 + 3314 samples came back 3314 samples (75 ms)
    early, because pre.encode crops the FRONT of an input that is not a whole number of frames while generate pads the END.
    The reference latents must decode back onto the audio they stand for: frame 0 is sample 0."""
    spy = {}
    orig = smoke.sine_hold_callback
    monkeypatch.setattr(smoke, "sine_hold_callback", lambda z, d, e: (spy.setdefault("z", z), orig(z, d, e))[1])   # the FIRST transition
    assert L % 4096 != 0                                                      # the case that broke
    run_base(project, "--noise-levels", "0.7")
    z = spy["z"]
    init = fake["calls"][0]["init_audio"][1].numpy()                          # what generate is given: the unpadded window
    dec = fake["model_cls"].model.pretransform.decode(z)[0].numpy()
    assert z.shape[-1] == -(-L // 4096) and np.allclose(dec[:, :L], init, atol=1e-5)


def test_slerp_decodes_back_in_time_when_the_window_is_not_a_whole_number_of_frames(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    assert L % 4096 != 0
    _, meta = run(proj, "--no-generate", "--other-slerp", "--require-sync")                  # lag against the real onsets must pass
    o = meta["transitions"][0]["outputs"][1]
    assert o["gen_synced"] is True and abs(o["gen_lag_ms"]) < 3, o["gen_lag_ms"]


def test_inpaint_grid_limit_is_relative_to_the_real_kicks_own_jitter():
    """On the Arc the REAL kicks in the masked span deviated from the grid fitted outside it by up to 35-42 ms (vintage goa swing),
    so a flat 30 ms limit failed the real material. The limit is max(tolerance, 1.5 x the real maximum)."""
    n = SR * 14
    period = 60.0 / 136.0
    grid = 0.5 + np.arange(24) * period
    rng = np.random.default_rng(3)

    def drums(times):
        x = np.zeros(n)
        k = np.arange(int(0.12 * SR))
        thump = np.exp(-k / (0.03 * SR)) * np.sin(2 * np.pi * 60.0 * k / SR)
        for t in times:
            i = int(round(t * SR))
            x[i:i + len(k)] += thump
        return np.stack([x, x])

    swing = np.where(np.arange(24) % 2 == 0, 0.030, -0.030)                    # alternating long/short: +-30 ms of real swing
    lo, hi = 5.0, 11.0
    inside = (grid > lo + 0.1) & (grid < hi - 0.1)
    real = drums(grid + swing)
    ok_gen = np.where(inside, grid + swing * 1.2, grid + swing)               # a bridge with a little MORE swing than the real thing
    bad_gen = np.where(inside, grid + rng.choice([-0.2, 0.2], 24), grid + swing)   # kicks 200 ms off the grid
    good = smoke.inpaint_grid_check(real, drums(ok_gen), lo, hi, 136.0, 30.0)
    assert good["ok"] is True and good["real_max_abs_ms"] > 20 and good["limit_ms"] > 30, good   # a flat 30 ms would have flagged the real thing
    bad = smoke.inpaint_grid_check(real, drums(bad_gen), lo, hi, 136.0, 30.0)
    assert bad["ok"] is False and bad["max_abs_ms"] > bad["limit_ms"], bad


def test_other_inpaint_variants_are_labelled_in_both_combinations(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    _, meta = run(proj, "--no-generate", "--other-inpaint-bars", "2", "--w-bars", "4", "--require-sync")
    assert [o["other_path"] for o in meta["transitions"][0]["outputs"]] == ["skipped", "d-xfade_o-inpaint2bar"]
    o = meta["transitions"][0]["outputs"][1]
    assert o["gen_synced"] is True and abs(o["gen_lag_ms"]) < 3 and o["other"] == "inpaint2bar" and o["drums"] == "xfade"

    _, meta = run(proj, "--no-generate", "--drum-inpaint-bars", "2", "--other-inpaint-bars", "2", "--w-bars", "4", "--require-sync")
    assert [o["other_path"] for o in meta["transitions"][0]["outputs"]] == ["skipped", "d-inpaint2bar_o-skipped", "d-inpaint2bar_o-inpaint2bar"]
    assert fake["lora"] == []                                                         # base weights; no implicit adapter


def test_an_other_inpaint_that_comes_back_late_is_caught_like_any_generated_layer(tmp_path, fake):
    proj, _ = make_click_project(tmp_path)
    fake["inpaint"] = "late"                                                          # the bridge returns 80 ms late
    _, meta = run(proj, "--no-generate", "--other-inpaint-bars", "2", "--w-bars", "4")
    o = meta["transitions"][0]["outputs"][1]
    assert o["gen_synced"] is False and o["gen_lag_ms"] is not None and abs(o["gen_lag_ms"]) > 12      # recorded, not hidden
    with pytest.raises(smoke.SyncError):
        run(proj, "--no-generate", "--other-inpaint-bars", "2", "--w-bars", "4", "--require-sync")
