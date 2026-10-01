import io
import json

import numpy as np
import pytest
import soundfile as sf

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture
def client(monkeypatch, tmp_path, tmp_path_factory):
    srv = forge_testutil.get_server(tmp_path_factory)
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    monkeypatch.setattr(srv, "PLAYER_CFG", {"latent_dir": "", "chunk_size": 128, "overlap": 32})
    forge_api.reset_queue()
    return fastapi_testclient.TestClient(srv.app)


def wav_bytes(seconds=0.25):
    buf = io.BytesIO()
    sf.write(buf, np.zeros((int(44100 * seconds), 2), dtype=np.float32), 44100, format="WAV")
    return buf.getvalue()


def test_upload_then_audio_and_files(client):
    data = wav_bytes()
    r = client.put("/forge/upload?filename=take.wav", content=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ref"]["kind"] == "upload" and body["channels"] == 2 and body["duration_sec"] == 0.25
    again = client.put("/forge/upload?filename=other.wav", content=data).json()
    assert again["ref"] == body["ref"]
    a = client.get("/forge/audio", params={"ref": json.dumps(body["ref"])})
    assert a.status_code == 200 and a.headers["content-type"].startswith("audio/wav") and a.content == data
    files = client.get("/forge/files?root=uploads").json()
    assert files["files"][0]["ref"] == body["ref"]
    assert [r["id"] for r in files["roots"]] == ["crops", "renders", "uploads"]


def test_upload_rejects(client):
    assert client.put("/forge/upload?filename=x.txt", content=b"abc").status_code == 400
    r = client.put("/forge/upload?filename=x.wav", content=b"not audio at all")
    assert r.status_code == 400 and "readable" in r.json()["error"]


def test_audio_bad_ref(client):
    assert client.get("/forge/audio", params={"ref": "{not json"}).status_code == 400
    assert client.get("/forge/audio", params={"ref": json.dumps({"kind": "upload", "sha256": "c" * 64})}).status_code == 404


def test_sessions(client):
    assert client.get("/forge/sessions").json() == {"ok": True, "sessions": []}
    assert client.put("/forge/sessions/set1", json={"version": 1}).status_code == 400
    assert client.put("/forge/sessions/set1", json={"version": 2, "clips": [{}, {}]}).json() == {"ok": True}
    s = client.get("/forge/sessions").json()["sessions"][0]
    assert s["name"] == "set1" and s["n_clips"] == 2
    assert client.get("/forge/sessions/set1").json() == {"version": 2, "clips": [{}, {}]}
    assert client.get("/forge/sessions/nope").status_code == 404
    assert client.put("/forge/sessions/bad name", json={"version": 2}).status_code in (400, 404)


def test_presets(client):
    assert client.get("/forge/presets/render").json() == {"ok": True, "names": []}
    assert client.put("/forge/presets/render/warm", json={"prompt": "pad"}).json() == {"ok": True}
    assert client.get("/forge/presets/render").json()["names"] == ["warm"]
    assert client.get("/forge/presets/render/warm").json() == {"prompt": "pad"}
    assert client.get("/forge/presets/sampling").status_code == 400
    assert client.delete("/forge/presets/render/warm").json() == {"ok": True}
    assert client.delete("/forge/presets/render/warm").status_code == 404
