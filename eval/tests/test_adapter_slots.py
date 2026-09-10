import sys

import pytest

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import adapter_slots


class FakeLoraModel:
    """Records the calls the slot table makes, so slot logic is testable on CPU."""

    def __init__(self):
        self.loaded = []
        self.removed = []
        self.strengths = {}

    def load_lora(self, paths):
        self.loaded.append(list(paths))

    def set_lora_strength(self, s, lora_index=None):
        self.strengths[lora_index] = s


def _specs(*paths):
    return [{"path": p, "label": p, "family": "adapter", "cost_gb": 0.33}
            for p in paths]


def test_plan_accepts_slots_that_fit_the_vram_floor():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=6.0, free_gb_fn=lambda: 10.0)
    plan = t.plan(_specs("a", "b", "c"))
    assert plan["ok"] is True
    assert [s.index for s in plan["slots"]] == [0, 1, 2]
    assert plan["projected_free_gb"] == pytest.approx(10.0 - 3 * 0.33, abs=0.01)


def test_plan_refuses_rather_than_oom_when_the_floor_would_be_crossed():
    t = adapter_slots.SlotTable(max_slots=8, vram_floor_gb=6.0, free_gb_fn=lambda: 6.2)
    plan = t.plan(_specs("a", "b", "c"))
    assert plan["ok"] is False
    assert "floor" in plan["reason"].lower()


def test_plan_refuses_more_than_max_slots():
    t = adapter_slots.SlotTable(max_slots=2, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    plan = t.plan(_specs("a", "b", "c"))
    assert plan["ok"] is False and "max" in plan["reason"].lower()


def test_max_slots_of_one_reproduces_todays_single_adapter_behaviour():
    t = adapter_slots.SlotTable(max_slots=1, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    assert t.plan(_specs("a"))["ok"] is True
    assert t.plan(_specs("a", "b"))["ok"] is False


def test_apply_clears_every_existing_index_then_loads_the_full_list_once():
    """load_and_apply_loras re-indexes from 0 on each call, so an incremental add
    would collide with index 0. The only safe update is remove-all + one load."""
    m = FakeLoraModel()
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    t.apply(m, _specs("a", "b"))
    t.apply(m, _specs("a", "b", "c"))
    assert m.loaded == [["a", "b"], ["a", "b", "c"]]
    assert m.removed == [0, 1], "both prior indices must be removed before reload"


def test_apply_is_a_noop_when_the_slot_set_is_unchanged():
    m = FakeLoraModel()
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    t.apply(m, _specs("a", "b"))
    plan = t.apply(m, _specs("a", "b"))
    assert plan["rebuild"] is False
    assert m.loaded == [["a", "b"]], "an unchanged set must not reload"


def test_lora_configs_covers_every_resident_index_not_just_the_active_one():
    """dit.py only touches indices present in lora_configs; an omitted index keeps
    its last enable state, so 'A vs B' would silently become 'A+B'."""
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b", "c"))
    cfgs = t.lora_configs(active=1)
    assert sorted(c["lora_index"] for c in cfgs) == [0, 1, 2]
    active = [c for c in cfgs if c["lora_index"] == 1][0]
    assert active["interval"] == (0.0, 1.0)
    for c in cfgs:
        if c["lora_index"] != 1:
            lo, hi = c["interval"]
            assert lo > 1.0, "an inactive slot needs an interval sigma can never satisfy"


def test_lora_configs_honours_a_custom_interval_on_the_active_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b"))
    cfgs = t.lora_configs(active=0, interval=(0.25, 1.0))
    assert [c for c in cfgs if c["lora_index"] == 0][0]["interval"] == (0.25, 1.0)


def test_strengths_zero_every_inactive_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b", "c"))
    assert dict(t.strengths(active=2, strength=1.4)) == {0: 0.0, 1: 0.0, 2: 1.4}


def test_active_none_silences_every_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b"))
    assert dict(t.strengths(active=None, strength=1.0)) == {0: 0.0, 1: 0.0}
    for c in t.lora_configs(active=None):
        assert c["interval"][0] > 1.0


def test_a_fullft_spec_is_rejected_as_a_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    plan = t.plan([{"path": "f", "label": "f", "family": "fullft", "cost_gb": 2.8}])
    assert plan["ok"] is False and "fullft" in plan["reason"].lower()


def test_push_strengths_drives_every_index_through_the_model():
    m = FakeLoraModel()
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0, free_gb_fn=lambda: 99.0)
    t.apply(m, _specs("a", "b", "c"))
    t.push_strengths(m, active=1, strength=0.8)
    assert m.strengths == {0: 0.0, 1: 0.8, 2: 0.0}


def test_the_default_cost_matches_what_was_measured_on_the_card():
    """0.40 GB per r128 adapter, measured 2026-08-26 (two cost 0.79 GB together).
    The plan's 0.33 counted adapter tensors only. Underestimating this turns a
    clean refusal into an OOM, so it is pinned."""
    import model_db
    assert model_db._load_cost_gb("adapter", 128) == pytest.approx(0.40, abs=0.005)
    assert model_db._load_cost_gb("adapter", 64) == pytest.approx(0.20, abs=0.005)


def test_the_floor_refuses_a_third_adapter_at_the_real_baseline():
    # medium-base leaves 7.40 GB free; at 0.40 GB each and a 6.0 GB floor, three
    # fit (7.40 - 1.20 = 6.20) and four do not (5.80).
    t = adapter_slots.SlotTable(max_slots=8, vram_floor_gb=6.0, free_gb_fn=lambda: 7.40)
    three = [{"path": p, "label": p, "family": "adapter", "cost_gb": 0.40}
             for p in "abc"]
    assert t.plan(three)["ok"] is True
    assert t.plan(three + [{"path": "d", "label": "d", "family": "adapter",
                            "cost_gb": 0.40}])["ok"] is False
