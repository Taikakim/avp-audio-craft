# Owner: WINTERMUTE (created 2026-10-13)
"""eval/forge/make_dj_mix_presets.py: clip id -> recipe, and the ptm -> backbone rule."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forge"))
import make_dj_mix_presets as mk  # noqa: E402

CID = "dora16_avp_familiarity_8ep_ptm__ep4__cfg1__w100__rb_rare_8__s278158216__st8"
ROW = {"model": "dora16_avp_familiarity_8ep_ptm", "ckpt": "ep4", "cfg": 1.0, "strength": 1.0,
       "prompt_id": "rb_rare_8", "prompt_text": "mid 90s goa trance", "seed": 278158216, "steps": 8,
       "duration": 47.55, "file": CID + "__d48.m4a"}


def test_parse_id():
    c = mk.parse_id(CID)
    assert c == {"label": "dora16_avp_familiarity_8ep_ptm", "tag": "ep4", "cfg": 1.0, "strength": 1.0,
                 "prompt_id": "rb_rare_8", "seed": 278158216, "steps": 8}
    assert mk.parse_id("x__ep3__cfg7__w100__kl_0__s1000__ema")["weights"] == "ema"


def test_preset_prefers_the_d48_render_and_maps_ptm_to_medium(tmp_path):
    ck = tmp_path / "epoch=4-step=1495.weights.ckpt"
    ck.write_bytes(b"")
    rows = {CID: {**ROW, "duration": 20.0, "file": CID + ".m4a"}, CID + "__d48": ROW}
    idx = {("dora16_avp_familiarity_8ep", "ep4"): str(ck)}
    p, name = mk.preset_for(1, CID, "v7", rows, idx, {})
    assert name == "dj-v7-01-dora16_avp_familiarity_8ep-ep4"
    assert p["model"]["backbone"] == "medium" and p["model"]["ckpt_path"] == str(ck)
    assert p["render"] == {"prompt": "mid 90s goa trance", "seed": 278158216, "cfg_scale": 1.0,
                           "steps": 8, "duration_sec": 47.55}


def test_repr_arm_falls_back_to_the_plain_run_and_base_has_no_ckpt():
    census = {("fp32cmp_x", "ep7"): ("/u/fp32cmp_x/epoch=7.ckpt", "adapter")}
    assert mk.resolve_ckpt("fp32cmp_x_repr", "ep7", {}, census) == ("/u/fp32cmp_x/epoch=7.ckpt", "adapter")
    cid = "base__base__cfg7__w100__kl_0__s1000"
    p, _ = mk.preset_for(2, cid, "v7", {cid: {**ROW, "cfg": 7.0, "steps": 24, "file": cid + ".m4a"}}, {}, {})
    assert p["model"] == {"backbone": "medium-base", "ckpt_path": None, "family": None,
                          "strength": 1.0, "weights": None}
