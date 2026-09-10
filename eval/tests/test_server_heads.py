import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")


def test_chroma_head_path_is_resolved_against_the_live_mount_not_a_literal():
    import explorer_render_server as srv
    p = srv._chroma_head_path()
    assert p is None or "Mantu1" not in p or srv._mantu_root().endswith("Mantu1")


def test_head_entry_carries_the_new_metadata_keys(monkeypatch):
    import explorer_render_server as srv

    class FakeHead:
        metadata = {"out_channels": 1, "loss_type": "smooth_l1", "std_mean": -21.93,
                    "std_std": 14.53, "epoch": 18, "avg_loss": 0.04, "standardized": True}
        class out_proj:
            weight = type("W", (), {"shape": (1, 1)})()

    monkeypatch.setattr(srv, "load_latch_from_checkpoint", lambda *a, **k: FakeHead())
    e = srv._head_entry("rms_energy_bass", "medium", "/tmp/x.pt", 512.0)
    assert e["slider_min"] == -50.99 and e["slider_max"] == 7.13
    assert e["health"] == "ok" and e["supports_scalar_target"] is True
    assert "512" in e["gain_scale_note"]


def test_an_unloadable_head_still_yields_an_entry_with_a_scan_error(monkeypatch):
    import explorer_render_server as srv

    def boom(*a, **k):
        raise FileNotFoundError("gone")

    monkeypatch.setattr(srv, "load_latch_from_checkpoint", boom)
    e = srv._head_entry("ghost", "chroma", "/nope.pt", 2048.0)
    assert "scan_error" in e and e["name"] == "ghost"
    assert e["slider_min"] == -80.0          # documented fallback, unchanged
