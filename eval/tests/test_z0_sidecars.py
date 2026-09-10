"""z0 next to every render (Kim's standing directive), and the honest exception.

Until 2026-08-26 the render server wrote wav + result.json and nothing else, so a
clip made in the inference UI could never be continued — `/longform
init_latent_path` only worked on output from the batch renderers. The fix is a
non-invasive `latents_sink` in the fork's generate() (same audio out, z0 also
handed back), consumed here.
"""
import sys

import numpy as np
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import explorer_render_server as srv


def test_save_z0_writes_fp16_next_to_the_audio(tmp_path):
    lat = torch.randn(1, 256, 174)
    p = srv.save_z0(tmp_path, "out_00", lat)
    arr = np.load(p)
    assert p.endswith("out_00.z0.npy")
    assert arr.shape == (256, 174)
    # fp16 to match what every batch renderer writes, so the sidecars are
    # interchangeable and continuation.recover() can read either.
    assert arr.dtype == np.float16


def test_save_z0_slices_one_batch_item(tmp_path):
    lat = torch.randn(3, 256, 100)
    for i in range(3):
        arr = np.load(srv.save_z0(tmp_path, f"out_{i:02d}", lat, index=i))
        assert arr.shape == (256, 100)
        assert np.allclose(arr, lat[i].numpy().astype(np.float16), atol=1e-3)


def test_save_z0_never_raises_a_good_render_away(tmp_path):
    # A sidecar that cannot be written must not lose the audio that was rendered.
    assert srv.save_z0(tmp_path / "does" / "not" / "exist", "x", torch.randn(1, 4, 4)) is None
    assert srv.save_z0(tmp_path, "y", None) is None


def test_build_response_surfaces_latents_at_the_top_level(tmp_path):
    resp = srv.build_response("job1", tmp_path, [tmp_path / "out_00.wav"], 7, 0.0, {}, [],
                              {"op": "generate", "latents": ["/a/out_00.z0.npy"]}, {}, False)
    # top level, so a client does not need to know which endpoint produced them
    assert resp["latents"] == ["/a/out_00.z0.npy"]


def test_a_response_with_no_latents_reports_an_empty_list_not_a_missing_key(tmp_path):
    resp = srv.build_response("job2", tmp_path, [], 7, 0.0, {}, [], {"op": "a2a_track"},
                              {}, False)
    assert resp["latents"] == []
