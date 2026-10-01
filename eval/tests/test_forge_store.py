import hashlib

import numpy as np
import pytest
import soundfile as sf

import forge_testutil  # noqa: F401
from forge.contract import ForgeError
from forge.hashing import file_sha256
from forge.store import JsonStore
from forge.uploads import UploadWriter, probe_audio


def test_store_crud(tmp_path):
    s = JsonStore(tmp_path / "presets" / "render", max_bytes=200)
    assert s.names() == []
    s.put("warm", {"prompt": "x"})
    assert s.names() == ["warm"] and s.get("warm") == {"prompt": "x"}
    assert s.listing()[0]["name"] == "warm" and s.listing()[0]["updated"] > 0
    with pytest.raises(ForgeError) as e:
        s.put("big", {"p": "x" * 500})
    assert e.value.status == 400
    with pytest.raises(ForgeError) as e:
        s.put("list", [1, 2])
    assert e.value.status == 400
    with pytest.raises(ForgeError):
        s.put("../evil", {})
    s.delete("warm")
    with pytest.raises(ForgeError) as e:
        s.get("warm")
    assert e.value.status == 404
    with pytest.raises(ForgeError) as e:
        s.delete("warm")
    assert e.value.status == 404


def test_upload_writer_hash_and_idempotence(tmp_path):
    data = b"RIFF" + bytes(range(256)) * 10
    w = UploadWriter("take.WAV", tmp_path, max_bytes=10_000)
    for i in range(0, len(data), 100):
        w.feed(data[i:i + 100])
    path, sha, n = w.finish()
    assert sha == hashlib.sha256(data).hexdigest() and n == len(data)
    assert path == tmp_path / f"{sha}.wav" and path.read_bytes() == data
    w2 = UploadWriter("again.wav", tmp_path, max_bytes=10_000)
    w2.feed(data)
    assert w2.finish()[0] == path
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{sha}.wav"]      # no .part leftovers


def test_upload_writer_rejects(tmp_path):
    with pytest.raises(ForgeError):
        UploadWriter("notes.txt", tmp_path, max_bytes=10)
    w = UploadWriter("a.wav", tmp_path, max_bytes=10)
    with pytest.raises(ForgeError):
        w.feed(b"x" * 11)
    w.abort()
    w = UploadWriter("a.wav", tmp_path, max_bytes=10)
    with pytest.raises(ForgeError):
        w.finish()                                                            # empty
    assert list(tmp_path.iterdir()) == []


def test_probe_audio(tmp_path):
    p = tmp_path / "t.wav"
    sf.write(p, np.zeros((22050, 2), dtype=np.float32), 44100)
    info = probe_audio(p)
    assert info == {"duration_sec": 0.5, "sample_rate": 44100, "channels": 2}
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio")
    with pytest.raises(ForgeError):
        probe_audio(bad)


def test_file_sha256(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    assert file_sha256(p) == hashlib.sha256(b"abc").hexdigest()
    p.write_bytes(b"abcd")
    assert file_sha256(p) == hashlib.sha256(b"abcd").hexdigest()
