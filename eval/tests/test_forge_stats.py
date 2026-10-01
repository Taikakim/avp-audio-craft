import base64
import json

import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge import stats
from forge.contract import ForgeError


def test_xcorr_payload_diag_and_correlated_dims():
    rng = np.random.default_rng(0)
    z = rng.standard_normal((256, 300))
    z[1] = z[0] * 2.0
    n, x = stats.xcorr_payload([z[:, :150], z[:, 150:]], max_frames=20000)
    assert n == 300 and x["shape"] == [256, 256]
    q = np.frombuffer(base64.b64decode(x["data_b64"]), dtype=np.uint8).reshape(256, 256)
    assert q[0, 0] == 255 and q[0, 1] == 255 and abs(int(q[2, 3]) - 128) < 40


def test_xcorr_subsamples():
    n, _ = stats.xcorr_payload([np.random.default_rng(1).standard_normal((256, 5000))], max_frames=100)
    assert n == 5000


def test_resample_points():
    assert stats.resample_points([1.0, 2.0], 10) == [1.0, 2.0]
    r = stats.resample_points(list(range(101)), 11)
    assert len(r) == 11 and r[0] == 0.0 and r[-1] == 100.0 and r[5] == pytest.approx(50.0)


def test_audio_feature_shapes():
    sr = 44100
    y = np.zeros((2, sr * 2), dtype=np.float32)
    y[:, sr:] = 0.5
    for f in stats.LIBROSA_FEATURES:
        v = stats.audio_feature(y, sr, f, 22)
        assert v.shape == (22,) and np.all(np.isfinite(v))
    rms = stats.audio_feature(y, sr, "rms", 22)
    assert rms[-3] > rms[2]
    with pytest.raises(ForgeError):
        stats.audio_feature(y, sr, "nope", 22)


def test_dataset_index(tmp_path):
    for i, (bpm, lufs) in enumerate([(120.0, -14.0), (140.0, -9.5), (None, -20.0)]):
        (tmp_path / f"{i:06d}.npy").write_bytes(b"x")
        (tmp_path / f"{i:06d}.json").write_text(json.dumps({
            "bpm_madmom": bpm, "lufs": lufs, "relative_position_start": 0.1 * i,
            "track_metadata_artist": "A", "track_metadata_title": f"T{i}", "padding_mask": [1, 1]}))
    (tmp_path / "000000.TIMESERIES.json").write_text("{}")
    idx = stats.DatasetIndex(tmp_path)
    assert {"bpm", "lufs", "rel_pos"} <= set(idx.fields())
    assert "padding_mask" not in idx.fields()
    pts = idx.points("bpm", "lufs")
    assert [(p["crop_id"], p["x"], p["y"]) for p in pts] == [("000000", 120.0, -14.0), ("000001", 140.0, -9.5)]
    assert pts[0]["label"] == "A — T0"
    with pytest.raises(ForgeError):
        idx.points("nope", "lufs")


def test_stats_route_with_path_latents(monkeypatch, tmp_path, tmp_path_factory):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    import soundfile as sf
    srv = forge_testutil.get_server(tmp_path_factory)
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    forge_api.reset_queue()
    rng = np.random.default_rng(0)
    for name in ("a", "b"):
        np.save(tmp_path / f"{name}.z0.npy", rng.standard_normal((256, 40)).astype(np.float16))
        sf.write(tmp_path / f"{name}.wav", np.zeros((4096 * 40, 2), dtype=np.float32), 44100)
    c = fastapi_testclient.TestClient(srv.app)
    r = c.post("/forge/stats", json={"latents": [{"kind": "path", "path": str(tmp_path / "a.z0.npy")},
                                                 {"kind": "path", "path": str(tmp_path / "b.z0.npy")}],
                                     "features": ["rms"], "max_points": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_frames"] == 80 and body["xcorr"]["shape"] == [256, 256]
    assert [s["index"] for s in body["timeseries"]] == [0, 1]
    assert len(body["timeseries"][0]["values"]) == 10
    assert c.post("/forge/stats", json={"latents": []}).status_code == 400
