"""eval/ckpt_weights.py on tiny synthetic checkpoints shaped like each trainer's real output."""
import json
import os
import sys

import pytest
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ckpt_weights  # noqa: E402


def _dit(prefix, n=3):
    return {f"{prefix}transformer.layers.{i}.attn.to_qkv.weight": torch.zeros(4, 4) for i in range(n)}


def test_residual_matches_closed_form():
    r = ckpt_weights.ema_residual(1500, 0.999)
    assert r["residual_start"] == pytest.approx(0.999 ** 1500)
    assert r["residual_start"] == pytest.approx(0.223, abs=1e-3)   # the morph L3 step-12000 number
    assert r["halflife_updates"] == pytest.approx(692.8, abs=0.1)
    assert ckpt_weights.ema_residual(None, 0.999) is None


def test_fullft_with_ema_uses_ema_step_not_global_step(tmp_path):
    sd = {**_dit("diffusion.model."), **_dit("diffusion_ema.ema_model."),
          "diffusion_ema.ema_step": torch.tensor(7792)}
    p = tmp_path / "epoch=1-step=3896.ckpt"
    torch.save({"state_dict": sd, "global_step": 3896, "epoch": 1}, p)
    (tmp_path / "run_meta.json").write_text(json.dumps(
        {"recipe": {"ema_beta": 0.9995, "init_state_ckpt": "/x/fullft_avp_t4096/epoch=7-step=1.ckpt"}}))
    r = ckpt_weights.weight_report(p)
    assert r["family"] == "fullft"
    assert [w["name"] for w in r["weight_sets"]] == ["online", "ema"]
    assert r["default_weights"] == "online"
    e = r["ema"]
    assert e["updates"] == 7792 - 100 and e["beta"] == 0.9995
    assert e["updates_per_optimizer_step"] == 2.0
    assert r["init"]["name"] == "fullft_avp_t4096/epoch=7-step=1.ckpt"
    assert r["init"]["source"].startswith("run_meta.recipe")


def test_fullft_without_ema_and_assumed_beta(tmp_path):
    p = tmp_path / "epoch=0-step=10.ckpt"
    torch.save({"state_dict": _dit("diffusion.model."), "global_step": 10}, p)
    r = ckpt_weights.weight_report(p)
    assert [w["name"] for w in r["weight_sets"]] == ["online"] and r["ema"] is None


def test_init_from_train_log_when_run_meta_silent(tmp_path):
    p = tmp_path / "epoch=0-step=10.ckpt"
    torch.save({"state_dict": _dit("diffusion.model."), "global_step": 10}, p)
    (tmp_path / "train.log").write_text("noise\n[init] full-FT warm-start from /r/goaft/last.ckpt (EMA)\n")
    r = ckpt_weights.weight_report(p)
    assert r["init"]["name"] == "goaft/last.ckpt" and "train log" in r["init"]["source"]


def _riffer(tmp_path, name="riffer_step12000.pt", **over):
    args = {"model": "medium-base", "ema": 0.999, "grad_accum": 8, "optimizer": "lion",
            "resume": "", "resume_exact": "", "base_state_ckpt": None, "base_state_online": False}
    args.update(over.pop("args", {}))
    ck = {"state": {"adapter.0.w": torch.zeros(2)}, "args": args, "control_mode": "melody_contour",
          "model_train": {"adapter.0.w": torch.zeros(2)}, "step": 12000, "opt": {}}
    ck.update(over)
    p = tmp_path / name
    torch.save(ck, p)
    return p


def test_control_adapter_ema_counts_optimizer_steps(tmp_path):
    p = _riffer(tmp_path, lora_state={"model.transformer.x.lora_A": torch.zeros(2)})
    r = ckpt_weights.weight_report(p)
    assert r["family"] == "control_adapter"
    names = [w["name"] for w in r["weight_sets"]]
    assert names == ["ema", "train_iterate"]
    assert "NO DoRA" in r["weight_sets"][1]["covers"]
    assert r["ema"]["updates"] == 1500
    assert r["ema"]["residual_start"] == pytest.approx(0.223, abs=1e-3)
    assert "zero-init" in r["ema"]["start_point"]
    assert r["steps"]["optimizer_steps"] == 1500


def test_control_adapter_sf_plus_ema_without_state_online_is_flagged(tmp_path):
    p = _riffer(tmp_path, args={"optimizer": "fusion"})
    r = ckpt_weights.weight_report(p)
    assert r["weight_sets"][0]["name"] == "sf_average?"
    assert r["ema"] is None          # not an EMA, so no residual is claimed


def test_control_adapter_resume_exact_restarts_the_shadow(tmp_path):
    src = _riffer(tmp_path, name="riffer_step4000.pt", step=4000)
    p = _riffer(tmp_path, args={"resume_exact": str(src)}, state_online={"adapter.0.w": torch.zeros(2)})
    old = ckpt_weights.RESUME_EMA_FIX_TS - 86400          # saved before WINTERMUTE's a1335a0 fix
    os.utime(p, (old, old))
    r = ckpt_weights.weight_report(p)
    assert r["ema"]["updates"] == (12000 - 4000) // 8
    assert "forgot" in r["ema"]["start_point"]
    assert r["init"]["source"] == "args.resume_exact"
    assert "online" in [w["name"] for w in r["weight_sets"]]


def test_latch_head_ema_and_siblings(tmp_path):
    base = {"state_dict": {"out_proj.weight": torch.zeros(2)}, "feature_stats": {}, "epoch": 10,
            "ema": 0.999, "grad_accum": 1, "effective_batch": 16, "selected_on": "val_loss",
            "init_from": None}
    p = tmp_path / "latch_sa3_onset_ep10.pt"
    torch.save(base, p)
    torch.save({**base, "ema": 0.0, "weights": "online_sf_average"}, tmp_path / "latch_sa3_onset_ep10_online.pt")
    r = ckpt_weights.weight_report(p)
    assert r["family"] == "latch_head"
    assert r["weight_sets"][0]["name"] == "ema"
    assert r["siblings"] == ["latch_sa3_onset_ep10_online.pt"]
    r2 = ckpt_weights.weight_report(tmp_path / "latch_sa3_onset_ep10_online.pt")
    assert r2["weight_sets"][0]["name"] == "online" and r2["ema"] is None


def test_never_raises_on_garbage(tmp_path):
    p = tmp_path / "broken.ckpt"
    p.write_bytes(b"not a zip")
    r = ckpt_weights.weight_report(p)
    assert r["errors"] and r["weight_sets"] == []
    assert isinstance(ckpt_weights.summary_line(r), str)


def test_deconvolved_riffer_is_not_reported_as_ema(tmp_path):
    p = _riffer(tmp_path, ema_deconvolved={"beta": 0.999, "gap_optimizer_steps": 250, "from": "riffer_step12000.pt",
                                           "prev": "riffer_step10000.pt", "note": "windowed average"})
    r = ckpt_weights.weight_report(p)
    assert r["weight_sets"][0]["name"] == "online_deconvolved" and r["ema"] is None


def test_production_style_head_without_feature_stats_is_a_latch_head(tmp_path):
    p = tmp_path / "latch_sa3_hpcp_best.pt"
    torch.save({"state_dict": {"out_proj.weight": torch.zeros(2)}, "feature_name": "hpcp",
                "std_mean": 0.0, "epoch": 30}, p)
    r = ckpt_weights.weight_report(p)
    assert r["family"] == "latch_head" and r["weight_sets"][0]["name"] == "online"


def test_control_adapter_resume_exact_after_the_fix_keeps_the_history(tmp_path):
    src = _riffer(tmp_path, name="riffer_step4000.pt", step=4000)
    p = _riffer(tmp_path, args={"resume_exact": str(src)})       # mtime = now, after a1335a0
    r = ckpt_weights.weight_report(p)
    assert r["ema"]["updates"] == 12000 // 8 and "forgot" not in r["ema"]["start_point"]
