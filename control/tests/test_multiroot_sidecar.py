"""Multi-root control sidecars must resolve PER ROOT, not by bare filename stem.

Why this test exists (CONTINUITY 2026-09-09): LatentControlDataset's multi-root path
list was built specifically to sidestep the 000000.* stem COLLISION between corpora
(goa + avp) -- every item carries its own absolute path. The melody/metrical SIDECAR
lookup never got the same treatment: it was basename(latent) + ".melody8.npy" against
ONE flat dir, so goa/000000.npy and avp/000000.npy both read the same stream file.
That trains happily and conditions 100% of the second corpus on the FIRST corpus's
contours -- a wrong-label failure that looks like a weak result, not like a bug.
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sa3_control.dataset import LatentControlDataset  # noqa: E402


def _corpus(tmp, name, stems, contour_value):
    """A minimal latent root + its own melody sidecar dir, with COLLIDING stems."""
    root = tmp / f"latents_{name}"
    side = tmp / f"latents_{name}_morph"
    root.mkdir()
    side.mkdir()
    for s in stems:
        np.save(root / f"{s}.npy", np.zeros((256, 64), dtype=np.float16))
        (root / f"{s}.json").write_text(json.dumps({"source_track": f"{name}-track-{s}"}))
        # every frame carries this corpus's marker value, so a crop conditioned on the
        # WRONG corpus's sidecar is detectable from the returned tensor alone
        np.save(side / f"{s}.melody8.npy",
                np.full((64,), contour_value, dtype=np.int8))
    return str(root), str(side)


def test_each_root_reads_its_own_sidecar(tmp_path):
    goa_root, goa_side = _corpus(tmp_path, "goa", ["000000", "000001"], contour_value=3)
    avp_root, avp_side = _corpus(tmp_path, "avp", ["000000", "000001"], contour_value=9)

    ds = LatentControlDataset([goa_root, avp_root], controls=(), audio_ref=None,
                              melody_dir=[goa_side, avp_side])

    assert len(ds) == 4, "both corpora's crops should survive the melody filter"
    seen = {}
    for i in range(len(ds)):
        item = ds[i]
        corpus = "goa" if goa_root in ds.paths[i] else "avp"
        vals = set(np.unique(item["melody_cls"].numpy()).tolist())
        seen.setdefault(corpus, set()).update(vals)

    assert seen["goa"] == {3}, f"goa crops read a foreign contour: {seen['goa']}"
    assert seen["avp"] == {9}, f"avp crops read a foreign contour: {seen['avp']}"


def test_single_root_behaviour_is_unchanged(tmp_path):
    goa_root, goa_side = _corpus(tmp_path, "goa", ["000000", "000001"], contour_value=3)
    ds = LatentControlDataset(goa_root, controls=(), audio_ref=None, melody_dir=goa_side)
    assert len(ds) == 2
    assert set(np.unique(ds[0]["melody_cls"].numpy()).tolist()) == {3}


def test_mismatched_sidecar_list_is_a_hard_error(tmp_path):
    """A per-root sidecar list that does not line up with the roots is a
    misconfiguration, not something to paper over with a fallback."""
    goa_root, goa_side = _corpus(tmp_path, "goa", ["000000"], contour_value=3)
    avp_root, avp_side = _corpus(tmp_path, "avp", ["000000"], contour_value=9)
    with pytest.raises(ValueError):
        LatentControlDataset([goa_root, avp_root], controls=(), audio_ref=None,
                             melody_dir=[goa_side])
