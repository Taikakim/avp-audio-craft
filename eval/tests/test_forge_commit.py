import copy

import pytest

import forge_testutil  # noqa: F401
from forge import commit as C
from forge.contract import ForgeError

HEADS = {"rms_energy_bass": {"default_gain": 512.0}, "chroma_other": {"default_gain": 2048.0}}
ENV = {"points": [0.3, 0.3, 0.3, 0.3], "curves": [0, 0, 0]}


def payload():
    return {
        "project_bpm": 140.0, "duration_sec": 40.0, "defaults": {"prompt": "goa"},
        "lanes": [{"index": i, "muted": False, "solo": False, "gain": 1.0, "chain": None} for i in range(4)],
        "clips": [
            {"id": "a", "lane": 0, "start_sec": 0, "offset_sec": 0, "dur_sec": 20, "loop": False,
             "audio": {"kind": "upload", "sha256": "a" * 64}, "native_bpm": 140.0, "detune_cents": 0, "a2a": None},
            {"id": "b", "lane": 0, "start_sec": 16, "offset_sec": 0, "dur_sec": 20, "loop": False,
             "audio": {"kind": "upload", "sha256": "b" * 64}, "native_bpm": 138.0, "detune_cents": 12,
             "a2a": {"render": {"prompt": "acid", "steps": 8}, "envelope": ENV}},
            {"id": "c", "lane": 2, "start_sec": 0, "offset_sec": 0, "dur_sec": 30, "loop": True,
             "audio": {"kind": "crop", "crop_id": "000001"}, "native_bpm": None, "detune_cents": 0,
             "a2a": {"render": {"prompt": "acid", "steps": 8}, "envelope": ENV}},
        ],
        "overlaps": [{"key": "a-b", "lane": 0, "start_sec": 16, "end_sec": 20, "a_id": "a", "b_id": "b",
                      "curve": ENV, "chroma_xfade": True, "render": {"prompt": "blend", "steps": 12}}],
        "mix": {"order": "tree", "nodes": {k: {"interp": "slerp", "t": 0.5} for k in ("M1", "M2", "MX")},
                "quad_weights": [1, 1, 1, 1]},
        "master": {"latch_on": True, "head": "rms_energy_bass", "gain": 64, "norm_on": True},
        "decode_lanes": False,
    }


def test_stage_labels():
    assert C.STAGES == ["DECODE latent → audio", "BUNGEE stretch / pitch", "ENCODE audio → latent", "LANE CHAINS",
                        "A2A RE-NOISE", "INPAINT OVERLAPS", "MIX", "MASTER CHAIN", "DECODE latent → audio"]


def test_validate_normalises():
    v = C.validate_commit(payload(), HEADS)
    assert [l["index"] for l in v["lanes"]] == [0, 1, 2, 3]
    assert v["lanes"][0]["chain"]["latch_on"] is False
    assert v["clips"][1]["a2a"]["render"]["steps"] == 8 and v["defaults"]["prompt"] == "goa"
    assert v["overlaps"][0]["render"]["steps"] == 12


@pytest.mark.parametrize("mutate,needle", [
    (lambda p: p.update(duration_sec=200), "capped at 184 s"),
    (lambda p: p["lanes"].pop(), "indexes 0, 1, 2, 3"),
    (lambda p: p.update(clips=[]), "no clips"),
    (lambda p: p["clips"][1].update(id="a"), "unique"),
    (lambda p: p["clips"][0].update(native_bpm=60.0), "stretch ratio"),
    (lambda p: p["overlaps"][0].update(b_id="c"), "both be on lane 0"),
    (lambda p: p["overlaps"][0].update(start_sec=21), "start_sec < end_sec"),
    (lambda p: p["mix"].update(order="spiral"), "mix order"),
    (lambda p: p["master"].update(head="nope"), "unknown master head"),
    (lambda p: p["lanes"][1].update(chain={"latch_on": True, "slots": [
        {"head": "nope", "kind": "constant", "value": 0, "weight": 1, "start_pct": 0, "end_pct": 0.6},
        {"head": "none", "kind": "constant", "value": 0, "weight": 1, "start_pct": 0, "end_pct": 0.6}]}),
     "unknown LatCH head"),
])
def test_validate_rejects(mutate, needle):
    p = payload()
    mutate(p)
    with pytest.raises(ForgeError) as e:
        C.validate_commit(p, HEADS)
    assert e.value.status == 400 and needle in e.value.message


def test_plan_groups_and_steps():
    plan = C.plan_passes(C.validate_commit(payload(), HEADS))
    assert [(g["lane"], g["key"], g["clip_ids"]) for g in plan["a2a"]] == [(0, "lane0:a2a:0", ["b"]),
                                                                           (2, "lane2:a2a:0", ["c"])]
    assert [(g["key"], g["overlap_keys"], g["chroma"]) for g in plan["inpaint"]] == [("lane0:ov:a-b", ["a-b"], True)]
    assert plan["steps_total"] == 8 + 8 + 12


def test_plan_merges_identical_renders_and_skips_inaudible():
    p = payload()
    p["clips"][0]["a2a"] = copy.deepcopy(p["clips"][1]["a2a"])
    p["overlaps"][0]["chroma_xfade"] = False
    p["lanes"][2]["muted"] = True
    plan = C.plan_passes(C.validate_commit(p, HEADS))
    assert [(g["key"], g["clip_ids"]) for g in plan["a2a"]] == [("lane0:a2a:0", ["a", "b"])]
    assert [(g["key"], g["chroma"]) for g in plan["inpaint"]] == [("lane0:inpaint:0", False)]
    p["lanes"][0]["solo"] = True
    p["lanes"][2]["muted"] = False
    assert [g["lane"] for g in C.plan_passes(C.validate_commit(p, HEADS))["a2a"]] == [0]
