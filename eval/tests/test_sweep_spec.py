import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import sweep_spec

import pytest


BASE = {"prompt": "goa", "duration": 20.0, "steps": 24, "cfg_scale": 7.0,
        "dora": {"name": "hof", "strength": 1.0},
        "latch": [{"head": "rms_energy_bass", "value": -20.0, "gain": 512.0}]}


def test_one_axis_expands_to_one_cell_per_value():
    cells = sweep_spec.expand(BASE, {"strength": [0.5, 1.0, 1.5]})
    assert len(cells) == 3
    assert [c["payload"]["dora"]["strength"] for c in cells] == [0.5, 1.0, 1.5]


def test_two_axes_expand_to_the_cross_product():
    cells = sweep_spec.expand(BASE, {"strength": [0.5, 1.0], "cfg": [7, 16]})
    assert len(cells) == 4
    assert {(c["coords"]["strength"], c["coords"]["cfg"]) for c in cells} == \
        {(0.5, 7), (0.5, 16), (1.0, 7), (1.0, 16)}


def test_seeds_multiply_every_combination_and_land_in_the_payload():
    cells = sweep_spec.expand(BASE, {"cfg": [7, 16]}, seeds=[11, 22, 33])
    assert len(cells) == 6
    assert sorted({c["payload"]["seed"] for c in cells}) == [11, 22, 33]


def test_no_seeds_means_one_cell_per_combination_with_server_resolved_seed():
    cells = sweep_spec.expand(BASE, {"cfg": [7, 16]})
    assert len(cells) == 2 and all(c["payload"]["seed"] == -1 for c in cells)


def test_expansion_never_mutates_the_base_payload():
    before = sweep_spec._canon(BASE)
    sweep_spec.expand(BASE, {"strength": [9.0]})
    assert sweep_spec._canon(BASE) == before


def test_a_list_indexed_axis_reaches_into_a_latch_slot():
    cells = sweep_spec.expand(BASE, {"latch1_value": [-30.0, -10.0]})
    assert [c["payload"]["latch"][0]["value"] for c in cells] == [-30.0, -10.0]
    assert cells[0]["payload"]["latch"][0]["gain"] == 512.0     # siblings untouched


def test_a_raw_dotted_path_is_accepted_verbatim():
    cells = sweep_spec.expand(BASE, {"mutate.amount": [0.1, 0.4]})
    assert [c["payload"]["mutate"]["amount"] for c in cells] == [0.1, 0.4]


def test_cell_ids_are_deterministic_across_calls():
    a = sweep_spec.expand(BASE, {"cfg": [7, 16]}, seeds=[1])
    b = sweep_spec.expand(BASE, {"cfg": [7, 16]}, seeds=[1])
    assert [c["cell_id"] for c in a] == [c["cell_id"] for c in b]


def test_cell_ids_are_unique_within_a_sweep():
    cells = sweep_spec.expand(BASE, {"cfg": [7, 16], "strength": [0.5, 1.0]}, seeds=[1, 2])
    assert len({c["cell_id"] for c in cells}) == len(cells) == 8


def test_cell_ids_distinguish_values_that_format_identically():
    a = sweep_spec.expand(BASE, {"cfg": [7.0]})[0]["cell_id"]
    b = sweep_spec.expand(BASE, {"cfg": [7.0000001]})[0]["cell_id"]
    assert a != b


def test_cell_ids_survive_reordering_the_axis_dict():
    a = sweep_spec.expand(BASE, {"cfg": [7], "strength": [1.0]})[0]["cell_id"]
    b = sweep_spec.expand(BASE, {"strength": [1.0], "cfg": [7]})[0]["cell_id"]
    assert a == b, "resume must not break because the axes were typed in another order"


def test_an_empty_axis_is_refused_at_expansion_time_too():
    with pytest.raises(ValueError):
        sweep_spec.expand(BASE, {"cfg": []})


def test_validate_rejects_an_empty_axis():
    assert sweep_spec.validate_spec({"preset": "x", "axes": {"cfg": []}})


def test_validate_rejects_a_nonlist_axis():
    assert sweep_spec.validate_spec({"preset": "x", "axes": {"cfg": 7}})


def test_validate_accepts_a_minimal_spec():
    assert sweep_spec.validate_spec({"preset": "x", "axes": {"cfg": [7, 16]}}) == []


def test_validate_requires_a_preset_or_an_inline_payload():
    assert sweep_spec.validate_spec({"axes": {"cfg": [7]}})


def test_the_model_axis_maps_to_ckpt_path():
    cells = sweep_spec.expand(BASE, {"model": ["/m/a.ckpt", "/m/b.ckpt"]})
    assert [c["payload"]["ckpt_path"] for c in cells] == ["/m/a.ckpt", "/m/b.ckpt"]
