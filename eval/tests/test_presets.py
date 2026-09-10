import sys
import time

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import presets

import pytest


PAYLOAD = {"prompt": "goa lead", "duration": 47.0, "steps": 24, "cfg_scale": 7.0,
           "seed": 12345, "batch_size": 2,
           "latch": [{"head": "rms_energy_bass", "kind": "constant", "value": -18.0,
                      "gain": 512.0, "start_pct": 0.0, "end_pct": 0.6}],
           "dora": {"name": "hof", "strength": 1.0}, "gamma": 0.3, "n_iter": 4}


def test_saving_strips_the_seed_because_a_preset_is_a_recipe(tmp_path):
    presets.save("A", PAYLOAD, dir=tmp_path)
    p = presets.load("A", dir=tmp_path)["payload"]
    assert "seed" not in p and "batch_size" not in p


def test_saving_keeps_the_latch_block_intact(tmp_path):
    presets.save("A", PAYLOAD, dir=tmp_path)
    p = presets.load("A", dir=tmp_path)["payload"]
    assert p["latch"][0]["gain"] == 512.0 and p["latch"][0]["value"] == -18.0


def test_saving_does_not_mutate_the_callers_dict(tmp_path):
    before = dict(PAYLOAD)
    presets.save("A", PAYLOAD, dir=tmp_path)
    assert PAYLOAD == before and PAYLOAD["seed"] == 12345


def test_a_preset_round_trips_with_its_notes_and_schema(tmp_path):
    presets.save("My Preset", PAYLOAD, notes="the good one", dir=tmp_path)
    got = presets.load("My Preset", dir=tmp_path)
    assert got["notes"] == "the good one"
    assert got["schema"] == presets.SCHEMA_VERSION
    assert got["name"] == "My Preset"


def test_names_are_slugged_for_the_filename_but_kept_verbatim_inside(tmp_path):
    path = presets.save("Goa / lead #2", PAYLOAD, dir=tmp_path)
    assert path.name == "goa-lead-2.json"
    assert presets.load("Goa / lead #2", dir=tmp_path)["name"] == "Goa / lead #2"


def test_saving_the_same_name_twice_overwrites_rather_than_duplicating(tmp_path):
    presets.save("A", PAYLOAD, dir=tmp_path)
    presets.save("A", {**PAYLOAD, "steps": 40}, dir=tmp_path)
    assert presets.load("A", dir=tmp_path)["payload"]["steps"] == 40
    assert len(presets.list_presets(tmp_path)) == 1


def test_listing_is_newest_first_and_carries_the_prompt(tmp_path):
    presets.save("old", PAYLOAD, dir=tmp_path)
    time.sleep(0.01)
    presets.save("new", {**PAYLOAD, "prompt": "psy bass"}, dir=tmp_path)
    got = presets.list_presets(tmp_path)
    assert [g["name"] for g in got] == ["new", "old"]
    assert got[0]["prompt"] == "psy bass"


def test_an_empty_prompt_is_refused(tmp_path):
    with pytest.raises(ValueError):
        presets.save("bad", {"prompt": "  ", "duration": 10}, dir=tmp_path)


def test_a_missing_preset_raises_a_named_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        presets.load("nope", dir=tmp_path)


def test_a_corrupt_preset_file_is_skipped_by_the_listing_not_fatal(tmp_path):
    presets.save("good", PAYLOAD, dir=tmp_path)
    (tmp_path / "junk.json").write_text("{ not json")
    assert [g["name"] for g in presets.list_presets(tmp_path)] == ["good"]


def test_the_viewer_form_snapshot_round_trips(tmp_path):
    form = {"inf-prompt": "goa lead", "inf-cfg": 12.0,
            "inf-ctl-latch1-gain": 700.0, "inf-ctl-latch-gamma": 0.15}
    presets.save("F", PAYLOAD, form=form, dir=tmp_path)
    assert presets.load("F", dir=tmp_path)["form"] == form


def test_a_preset_without_a_form_snapshot_simply_has_no_form_key(tmp_path):
    presets.save("F", PAYLOAD, dir=tmp_path)
    assert "form" not in presets.load("F", dir=tmp_path)
