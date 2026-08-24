import os

import pytest
import torch

import ckpt_probe


def _save(path, obj):
    torch.save(obj, path)
    return str(path)


def _dora_sd(n_modules=3, rank=8, in_f=16, out_f=32):
    sd = {}
    for i in range(n_modules):
        base = f"model.transformer.layers.{i}.attn.to_qkv.parametrizations.weight.0"
        sd[f"{base}.lora_A"] = torch.zeros(rank, in_f)
        sd[f"{base}.lora_B"] = torch.zeros(out_f, rank)
        sd[f"{base}.magnitude"] = torch.zeros(out_f)
    return sd


def test_adapter_is_detected_with_rank_and_module_count(tmp_path):
    p = _save(tmp_path / "epoch=3-step=144.weights.ckpt", {
        "state_dict": _dora_sd(n_modules=3, rank=8),
        "epoch": 3, "global_step": 144,
        "lora_config": {"rank": 8, "alpha": 4.0, "adapter_type": "dora-rows"},
    })
    r = ckpt_probe.probe(p)
    assert r["family"] == "adapter"
    assert r["rank"] == 8 and r["alpha"] == 4.0
    assert r["adapter_type"] == "dora-rows"
    assert r["n_target_modules"] == 3
    assert r["epoch"] == 3 and r["step"] == 144
    assert r["probe_error"] is None


def test_control_adapter_is_detected_from_the_top_level_control_mode_key(tmp_path):
    p = _save(tmp_path / "riffer_final.pt", {
        "state_dict": {"enc.0.weight": torch.zeros(2, 2)},
        "control_mode": "melody_contour",
        "args": {"melody_vocab": 77, "control_dim": 768},
    })
    r = ckpt_probe.probe(p)
    assert r["family"] == "control_adapter"
    assert r["control_mode"] == "melody_contour"
    assert r["kind"] == "pt"


def test_fullft_is_detected_when_the_state_dict_covers_the_dit_and_carries_no_lora(tmp_path):
    sd = {f"model.transformer.layers.{i}.attn.to_qkv.weight": torch.zeros(2, 2)
          for i in range(4)}
    sd["model.to_timestep_embed.0.weight"] = torch.zeros(2, 2)
    p = _save(tmp_path / "epoch=7-step=10800.weights.ckpt",
              {"state_dict": sd, "epoch": 7, "global_step": 10800})
    r = ckpt_probe.probe(p)
    assert r["family"] == "fullft"
    assert r["rank"] is None


def test_slim_vs_fat_is_read_from_the_optimizer_states_key(tmp_path):
    fat = _save(tmp_path / "epoch=0-step=1.ckpt", {
        "state_dict": _dora_sd(), "optimizer_states": [{"state": {}}],
        "lora_config": {"rank": 8, "alpha": 8.0, "adapter_type": "dora-rows"}})
    slim = _save(tmp_path / "epoch=0-step=1.weights.ckpt", {
        "state_dict": _dora_sd(),
        "lora_config": {"rank": 8, "alpha": 8.0, "adapter_type": "dora-rows"}})
    assert ckpt_probe.probe(fat)["slim"] is False
    assert ckpt_probe.probe(slim)["slim"] is True


def test_epoch_and_step_fall_back_to_the_filename_when_absent_from_the_payload(tmp_path):
    p = _save(tmp_path / "epoch=12-step=999.weights.ckpt", {"state_dict": _dora_sd()})
    r = ckpt_probe.probe(p)
    assert r["epoch"] == 12 and r["step"] == 999


def test_safetensors_adapter_is_probed_from_its_json_header(tmp_path):
    from safetensors.torch import save_file
    p = tmp_path / "extracted.safetensors"
    save_file({"model.a.parametrizations.weight.0.lora_A": torch.zeros(16, 8),
               "model.a.parametrizations.weight.0.lora_B": torch.zeros(8, 16)}, str(p))
    r = ckpt_probe.probe(p)
    assert r["family"] == "adapter"
    assert r["kind"] == "safetensors"
    assert r["rank"] == 16


def test_an_unreadable_file_returns_unknown_and_an_error_rather_than_raising(tmp_path):
    p = tmp_path / "junk.ckpt"
    p.write_bytes(b"not a zip")
    r = ckpt_probe.probe(p)
    assert r["family"] == "unknown"
    assert r["probe_error"]


def test_probe_reads_only_the_pickle_member_not_the_tensor_payload(tmp_path):
    """A big payload must not make the probe slow -- it is the whole point."""
    big = {"state_dict": dict(_dora_sd(), pad=torch.zeros(8_000_000)),
           "lora_config": {"rank": 8, "alpha": 8.0, "adapter_type": "dora-rows"}}
    p = _save(tmp_path / "epoch=0-step=1.ckpt", big)
    assert os.path.getsize(p) > 30_000_000
    import time
    t0 = time.time()
    r = ckpt_probe.probe(p)
    assert r["family"] == "adapter"
    assert time.time() - t0 < 0.5
