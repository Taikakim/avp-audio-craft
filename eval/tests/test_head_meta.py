import json
import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import head_meta


def _md(**kw):
    base = {"feature_name": "rms_energy_bass", "out_channels": 1,
            "loss_type": "smooth_l1", "standardized": True,
            "std_mean": -21.93, "std_std": 14.53, "epoch": 18, "avg_loss": 0.04}
    base.update(kw)
    return base


def d(**kw):
    return head_meta.describe("rms_energy_bass", "medium", "/tmp/x.pt", 512.0,
                              metadata=_md(**kw), overrides={})


def test_slider_bounds_are_two_sigma_around_the_dataset_mean():
    h = d()
    assert h["slider_min"] == -50.99
    assert h["slider_max"] == 7.13
    assert h["value_default"] == -21.93


def test_degenerate_sigma_falls_back_to_the_servers_old_default():
    h = d(std_std=0.0)
    assert (h["slider_min"], h["slider_max"], h["value_default"]) == (-80.0, 20.0, -30.0)


def test_a_384_channel_cosine_head_disables_scalar_target_and_loss_select():
    h = head_meta.describe("same_chroma", "medium", "/tmp/c.pt", 512.0,
                           metadata=_md(feature_name="same_chroma", out_channels=384,
                                        loss_type="cosine", standardized=False,
                                        std_mean=0.0, std_std=1.0, epoch=20),
                           overrides={})
    assert h["supports_scalar_target"] is False
    assert h["supports_loss_select"] is False
    assert h["supports_kinds"] == []


def test_an_undertrained_head_is_flagged_with_a_reason_naming_both_facts():
    h = d(feature_name="spectral_kurtosis", epoch=3, std_mean=15.72, std_std=521.6)
    assert h["health"] == "undertrained"
    assert "3" in h["health_reason"] and "521.6" in h["health_reason"]


def test_a_healthy_scalar_head_is_ok_with_an_empty_reason():
    h = d()
    assert h["health"] == "ok" and h["health_reason"] == ""


def test_chroma_readout_is_reported_as_not_recorded_when_nothing_knows_it():
    h = head_meta.describe("hpcp", "medium", "/tmp/h.pt", 512.0,
                           metadata=_md(feature_name="hpcp", out_channels=12), overrides={})
    assert h["readout"] == "unknown"
    assert h["readout_source"] == "not-recorded"


def test_an_override_supplies_the_readout_and_says_so():
    ov = {"hpcp": {"readout": "essentia_hpcp_12"}}
    h = head_meta.describe("hpcp", "medium", "/tmp/h.pt", 512.0,
                           metadata=_md(feature_name="hpcp", out_channels=12), overrides=ov)
    assert h["readout"] == "essentia_hpcp_12"
    assert h["readout_source"] == "overrides"


def test_a_scalar_head_reports_readout_not_applicable():
    assert d()["readout"] == "n/a"


def test_the_gain_note_is_in_the_normalised_scale():
    note = d()["gain_scale_note"]
    assert "512" in note and "slot-1 gain" in note


def test_rms_heads_are_labelled_dB():
    assert d()["units"] == "dB"


def test_every_legacy_info_key_survives():
    h = d()
    for k in ("name", "family", "path", "default_gain", "out_channels",
              "loss_type", "target_kind_default", "slider_min", "slider_max",
              "value_default"):
        assert k in h, k


def test_load_overrides_returns_empty_dict_when_the_file_is_absent(tmp_path):
    assert head_meta.load_overrides(tmp_path / "nope.json") == {}


def test_load_overrides_reads_the_file(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps({"hpcp": {"readout": "x"}}))
    assert head_meta.load_overrides(p)["hpcp"]["readout"] == "x"


def test_a_future_checkpoint_that_records_its_readout_is_believed():
    h = head_meta.describe("hpcp2", "medium", "/tmp/h2.pt", 512.0,
                           metadata={"out_channels": 12, "loss_type": "smooth_l1",
                                     "std_mean": 0.24, "std_std": 0.27, "epoch": 20,
                                     "chroma_key": "full_mix"},
                           overrides={})
    assert h["readout"] == "full_mix"
    assert h["readout_source"] == "checkpoint"
