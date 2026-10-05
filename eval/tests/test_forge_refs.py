from pathlib import Path

import pytest

import forge_testutil  # noqa: F401
from forge.contract import ForgeError
from forge.library import list_files
from forge.refs import RefContext, resolve_audio

SHA = "a" * 64


@pytest.fixture
def ctx(tmp_path):
    out, up, lat = tmp_path / "out", tmp_path / "out" / "_forge" / "uploads", tmp_path / "lat"
    for d in (out / "job1", up, lat):
        d.mkdir(parents=True)
    (out / "job1" / "out_00.wav").write_bytes(b"x")
    (up / f"{SHA}.flac").write_bytes(b"x")
    (lat / "000001.npy").write_bytes(b"x")
    decoded = tmp_path / "dec.wav"
    decoded.write_bytes(b"x")
    return RefContext(out_dir=out, uploads=up, latent_dir=lat, decode_crop=lambda cid: decoded,
                      roots={"crops": lat, "renders": out, "uploads": up})


@forge_testutil.needs_ffprobe
def test_resolve_each_kind(ctx, tmp_path):
    assert resolve_audio({"kind": "upload", "sha256": SHA}, ctx) == ctx.uploads / f"{SHA}.flac"
    assert resolve_audio({"kind": "render", "job_id": "job1", "file": "out_00.wav"}, ctx) == ctx.out_dir / "job1" / "out_00.wav"
    assert resolve_audio({"kind": "crop", "crop_id": "000001"}, ctx) == tmp_path / "dec.wav"
    assert resolve_audio({"kind": "file", "root": "renders", "rel": "job1/out_00.wav"}, ctx) == ctx.out_dir / "job1" / "out_00.wav"
    p = ctx.out_dir / "job1" / "out_00.wav"
    assert resolve_audio({"kind": "path", "path": str(p)}, ctx) == p


@pytest.mark.parametrize("ref,status", [
    (None, 400), ({"kind": "nope"}, 400),
    ({"kind": "upload", "sha256": "xyz"}, 400), ({"kind": "upload", "sha256": "b" * 64}, 404),
    ({"kind": "render", "job_id": "../job1", "file": "out_00.wav"}, 400),
    ({"kind": "render", "job_id": "job1", "file": "missing.wav"}, 404),
    ({"kind": "crop", "crop_id": "../x"}, 400), ({"kind": "crop", "crop_id": "999999"}, 404),
    ({"kind": "file", "root": "etc", "rel": "x.wav"}, 400),
    ({"kind": "file", "root": "renders", "rel": "../../x.wav"}, 400),
    ({"kind": "path", "path": "relative.wav"}, 400), ({"kind": "path", "path": "/nonexistent/a.wav"}, 404),
])
def test_resolve_errors(ctx, ref, status):
    with pytest.raises(ForgeError) as e:
        resolve_audio(ref, ctx)
    assert e.value.status == status


def test_non_audio_extension(ctx):
    bad = ctx.out_dir / "job1" / "notes.txt"
    bad.write_text("x")
    with pytest.raises(ForgeError) as e:
        resolve_audio({"kind": "path", "path": str(bad)}, ctx)
    assert e.value.status == 400


def test_list_files(ctx):
    roots = {"crops": ctx.latent_dir, "renders": ctx.out_dir, "uploads": ctx.uploads}
    r = list_files(roots, "crops", "", 10)
    assert [x["id"] for x in r["roots"]] == ["crops", "renders", "uploads"]
    assert r["files"] == [{"root": "crops", "rel": "000001.npy", "kind": "latent", "size": 1,
                           "mtime": r["files"][0]["mtime"], "ref": {"kind": "crop", "crop_id": "000001"}}]
    rr = list_files(roots, "renders", "", 10)["files"]
    assert [f["rel"] for f in rr] == ["job1/out_00.wav"]            # _forge/ is never listed
    assert rr[0]["ref"] == {"kind": "render", "job_id": "job1", "file": "out_00.wav"}
    uu = list_files(roots, "uploads", "", 10)["files"]
    assert uu[0]["ref"] == {"kind": "upload", "sha256": SHA}
    assert list_files(roots, "crops", "zzz", 10)["files"] == []
    gone = {**roots, "crops": Path("/nonexistent")}
    g = list_files(gone, "crops", "", 10)
    assert g["files"] == [] and g["roots"][0]["available"] is False
    with pytest.raises(ForgeError):
        list_files(roots, "etc", "", 10)
