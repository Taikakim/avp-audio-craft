import json

import pytest
import torch

import model_db
from model_roots import Root


def _adapter_ckpt(path, rank=8, epoch=0, step=1):
    sd = {}
    for i in range(2):
        b = f"model.transformer.layers.{i}.attn.to_qkv.parametrizations.weight.0"
        sd[f"{b}.lora_A"] = torch.zeros(rank, 4)
        sd[f"{b}.lora_B"] = torch.zeros(4, rank)
        sd[f"{b}.magnitude"] = torch.zeros(4)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": sd, "epoch": epoch, "global_step": step,
                "lora_config": {"rank": rank, "alpha": float(rank),
                                "adapter_type": "dora-rows"}}, path)
    return path


def _root(tmp_path, rid="r1"):
    return Root(id=rid, label=rid, path=str(tmp_path), priority=10, enabled=True,
                available=True, template="${X}")


def test_scan_root_finds_ckpt_safetensors_and_pt(tmp_path):
    _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    (tmp_path / "ctrl").mkdir()
    torch.save({"control_mode": "melody_contour", "state_dict": {}},
               tmp_path / "ctrl" / "riffer_final.pt")
    (tmp_path / "x.safetensors").write_bytes(b"\x02\x00\x00\x00\x00\x00\x00\x00{}")
    names = {e["name"] for e in model_db.scan_root(_root(tmp_path))}
    assert "fam/arm/epoch=0-step=1.weights.ckpt" in names
    assert "ctrl/riffer_final.pt" in names, "riffer_*.pt must not be invisible"
    assert "x.safetensors" in names


def test_record_carries_family_arm_and_detected_fields(tmp_path):
    p = _adapter_ckpt(tmp_path / "bf16_twin" / "armA" / "epoch=3-step=144.weights.ckpt",
                      rank=16, epoch=3, step=144)
    rec = model_db.record_for(str(p), _root(tmp_path), {})
    assert rec["family"] == "adapter"
    assert rec["family_dir"] == "bf16_twin" and rec["arm"] == "armA"
    assert rec["label"] == "armA"
    assert rec["rank"] == 16 and rec["epoch"] == 3 and rec["step"] == 144
    assert rec["loadable"] is True
    assert rec["id"].startswith("MDB-")


def test_run_meta_is_found_by_walking_up_and_both_shapes_parse(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    (tmp_path / "fam" / "run_meta.json").write_text(json.dumps({
        "purpose": "recon style",
        "reconstructed_by": "someone",
        "training": {"corpus": "avp", "crop_frames": 512, "optimizer": "adamw",
                     "lr": None, "base_precision": "bf16", "seed": 1},
        "status": "COMPLETE", "kim_feedback": None}))
    rec = model_db.record_for(str(p), _root(tmp_path), {})
    assert rec["corpus"] == "avp" and rec["crop_frames"] == 512
    assert rec["precision"] == "bf16"
    assert rec["provenance"]["corpus"].startswith("run_meta")

    q = _adapter_ckpt(tmp_path / "fam2" / "arm" / "epoch=0-step=1.weights.ckpt")
    (tmp_path / "fam2" / "arm" / "run_meta.json").write_text(json.dumps({
        "run": "x", "purpose": "launch style",
        "dataset": {"name": "suomi"},
        "recipe": {"adapter": "lora", "rank": 16, "lr": "1e-4", "frames": 256,
                   "optimizer": "adamw", "precision": "bf16"}}))
    rec2 = model_db.record_for(str(q), _root(tmp_path), {})
    assert rec2["corpus"] == "suomi" and rec2["lr"] == "1e-4"
    assert rec2["crop_frames"] == 256


def test_checkpoint_derived_fields_beat_run_meta_on_conflict(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt", rank=8)
    (tmp_path / "fam" / "run_meta.json").write_text(json.dumps({
        "training": {"dora_rank": 999, "corpus": "goa"}}))
    rec = model_db.record_for(str(p), _root(tmp_path), {})
    assert rec["rank"] == 8, "the checkpoint is ground truth, run_meta may be reconstructed"
    assert rec["provenance"]["rank"] == "ckpt"
    assert rec["corpus"] == "goa"


def test_overrides_supply_verdict_and_recipe_but_never_detected_fields(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=0-step=1.weights.ckpt", rank=8)
    ov = {"armA": {"note": "usable at ep3-7", "recipe": "adamw - lr 1e-4"}}
    rec = model_db.record_for(str(p), _root(tmp_path), ov)
    assert rec["verdict"] == "usable at ep3-7"
    assert rec["recipe"] == "adamw - lr 1e-4"
    assert rec["provenance"]["verdict"] == "overrides"
    assert rec["rank"] == 8


def test_dedupe_prefers_the_higher_priority_root_for_an_identical_arm_and_file(tmp_path):
    hi = tmp_path / "hi"
    lo = tmp_path / "lo"
    _adapter_ckpt(hi / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    _adapter_ckpt(lo / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    rh = Root("hi", "hi", str(hi), 30, True, True, "${X}")
    rl = Root("lo", "lo", str(lo), 5, True, True, "${X}")
    recs = model_db.build([rh, rl], overrides_path=None)
    kept = model_db.dedupe(recs)
    assert len(kept) == 1 and kept[0]["root_id"] == "hi"
    assert kept[0]["also_at"] == [str(lo / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")]


def test_load_cost_gb_scales_with_rank(tmp_path):
    small = model_db.record_for(
        str(_adapter_ckpt(tmp_path / "a" / "b" / "epoch=0-step=1.weights.ckpt", rank=8)),
        _root(tmp_path), {})
    assert 0.0 < small["load_cost_gb"] < 1.0


def test_an_unavailable_root_is_reported_stale_not_fatal(tmp_path):
    gone = Root("gone", "gone", None, 10, True, False, "${MISSING}")
    out = model_db.load_or_build([gone.id], rescan=True)  # no journal entry either
    assert "gone" in out["stale_root_ids"] or out["models"] == []


def test_journal_round_trips_and_rescan_forces_a_rewalk(tmp_path, monkeypatch):
    jp = tmp_path / "journal.json"
    monkeypatch.setattr(model_db, "JOURNAL_PATH", jp)
    r = _root(tmp_path)
    _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    monkeypatch.setattr(model_db, "resolve_roots", lambda: [r])
    first = model_db.load_or_build(rescan=True)
    assert len(first["models"]) == 1
    assert json.loads(jp.read_text())["schema"] == model_db.SCHEMA_VERSION
    _adapter_ckpt(tmp_path / "fam" / "arm2" / "epoch=0-step=2.weights.ckpt")
    cached = model_db.load_or_build(rescan=False)
    assert len(cached["models"]) == 1, "cached read must not re-walk"
    fresh = model_db.load_or_build(rescan=True)
    assert len(fresh["models"]) == 2


# --- run_params_extracted.json as a recipe source (2026-09-01) ---------------
# The extraction covers 249 LUMI arms with optimizer/lr/precision/frames read out
# of the launch sbatch, but model_db's source chain was ckpt > run_meta > overrides
# and never consulted it -- so 54 census rows sat blank next to a file that had
# their answer. It slots BELOW run_meta (per-run truth) and ABOVE overrides.

_RP = {"armA": {"optimizer": "fusion", "lr": 0.0001, "precision": "fp32",
                "frames_T": 512, "seed": 1, "dataset": "latents_sa3",
                "rank": 999, "_source": "lumi/sbatch/x.sbatch:100"}}


def test_run_params_fills_recipe_fields_when_run_meta_absent(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=0-step=1.weights.ckpt", rank=16)
    rec = model_db.record_for(str(p), _root(tmp_path), {}, run_params=_RP)
    assert rec["optimizer"] == "fusion"
    assert rec["lr"] == 0.0001
    assert rec["precision"] == "fp32"
    assert rec["crop_frames"] == 512
    assert rec["corpus"] == "latents_sa3"
    assert rec["provenance"]["optimizer"] == "run_params.optimizer"


def test_ckpt_still_wins_over_run_params(tmp_path):
    """rank comes from the checkpoint itself; a stale sbatch must not override it."""
    p = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=0-step=1.weights.ckpt", rank=16)
    rec = model_db.record_for(str(p), _root(tmp_path), {}, run_params=_RP)
    assert rec["rank"] == 16, "checkpoint is ground truth, not the launch script"
    assert rec["provenance"]["rank"] == "ckpt"


def test_run_params_absent_arm_is_a_noop(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "other" / "epoch=0-step=1.weights.ckpt")
    rec = model_db.record_for(str(p), _root(tmp_path), {}, run_params=_RP)
    assert rec["optimizer"] is None and rec["lr"] is None


# --- good / broken flags and the Forge's forge_notes key (WINTERMUTE 2026-10-13) ---

def test_ckpt_tag_key_folds_render_variants_but_keeps_replicas():
    assert model_db.ckpt_tag_key("ep3_native") == "ep3"
    assert model_db.ckpt_tag_key("ep5_20s") == "ep5"
    assert model_db.ckpt_tag_key("ep3_iv0.2-0.8") == "ep3"
    assert model_db.ckpt_tag_key("ep19v1") == "ep19v1"
    assert model_db.ckpt_tag_key("step=1011") == model_db.ckpt_tag_key("step1011") == "step1011"
    assert model_db.ckpt_tag_key("base") == "base"


def test_good_list_marks_the_run_and_only_the_listed_checkpoint(tmp_path):
    good = tmp_path / "cleaned.txt"
    good.write_text("armA:ep2_native\narmA:step=99\n")
    g = model_db.load_good(good)
    p2 = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=2-step=10.weights.ckpt", epoch=2, step=10)
    p3 = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=3-step=99.weights.ckpt", epoch=3, step=99)
    p4 = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=4-step=120.weights.ckpt", epoch=4, step=120)
    r2, r3, r4 = (model_db.record_for(str(p), _root(tmp_path), {}, None, g) for p in (p2, p3, p4))
    assert r2["good_run"] and r2["good_ckpt"]
    assert r3["good_ckpt"]                       # matched by step
    assert r4["good_run"] and not r4["good_ckpt"]
    assert not r2["broken"]


def test_a_failed_status_is_broken_and_beats_the_good_list(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "armB" / "epoch=1-step=5.weights.ckpt", epoch=1, step=5)
    rec = model_db.record_for(str(p), _root(tmp_path), {"armB": {"status": "failed-runaway"}},
                              None, {"armB": {"ep1"}})
    assert rec["broken"] and not rec["good_run"] and not rec["good_ckpt"]


def test_save_forge_notes_touches_only_its_own_key_and_keeps_the_format(tmp_path):
    p = tmp_path / "ov.json"
    orig = {"_doc": "d—x", "armA": {"purpose": "auto purpose", "kim_feedback": "verbatim"}}
    p.write_text(json.dumps(orig, indent=2, ensure_ascii=True) + "\n")
    model_db.save_forge_notes("armA", "sounds dark at cfg 7", p)
    d = json.loads(p.read_text())
    assert d["armA"]["purpose"] == "auto purpose" and d["armA"]["kim_feedback"] == "verbatim"
    assert d["armA"]["forge_notes"] == "sounds dark at cfg 7"
    assert "\\u2014" in p.read_text() and p.read_text().endswith("}\n")
    n = model_db.notes_for("armA", p)
    assert n["fields"]["purpose"] == "auto purpose" and n["forge_notes"] == "sounds dark at cfg 7"
    model_db.save_forge_notes("armA", "", p)                  # clearing removes only our keys
    assert json.loads(p.read_text())["armA"] == orig["armA"]
    model_db.save_forge_notes("medium-base", "new label", p)  # a label with no entry gets one
    assert json.loads(p.read_text())["medium-base"]["forge_notes"] == "new label"
    with pytest.raises(ValueError):
        model_db.save_forge_notes("_doc", "x", p)


def test_notes_key_never_lands_on_a_generic_checkpoints_folder(tmp_path):
    p = _adapter_ckpt(tmp_path / "sa3-run-r64" / "i8nygj4y" / "checkpoints" / "epoch=1-step=5.weights.ckpt",
                      epoch=1, step=5)
    rec = model_db.record_for(str(p), _root(tmp_path), {})
    assert rec["arm"] == "checkpoints" and rec["notes_key"] == "sa3-run-r64"
    q = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=0-step=1.weights.ckpt")
    assert model_db.record_for(str(q), _root(tmp_path), {"fam": {"note": "x"}})["notes_key"] == "fam"
    assert model_db.record_for(str(q), _root(tmp_path), {"armA": {}, "fam": {}})["notes_key"] == "armA"


def test_save_forge_rating_sets_clears_and_validates(tmp_path):
    p = tmp_path / "ov.json"
    orig = {"armA": {"purpose": "auto purpose", "forge_notes": "keep me"}}
    p.write_text(json.dumps(orig, indent=2, ensure_ascii=True) + "\n")
    assert model_db.save_forge_rating("armA", 4, p)["forge_rating"] == 4
    d = json.loads(p.read_text())["armA"]
    assert d["forge_rating"] == 4 and d["purpose"] == "auto purpose" and d["forge_notes"] == "keep me"
    assert model_db.notes_for("armA", p)["forge_rating"] == 4
    for bad in (6, -1, "3", True, 2.5):
        with pytest.raises(ValueError):
            model_db.save_forge_rating("armA", bad, p)
    model_db.save_forge_rating("armA", None, p)               # clearing removes only our keys
    assert json.loads(p.read_text())["armA"] == orig["armA"]
    model_db.save_forge_rating("armA", 2, p)
    q = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=0-step=1.weights.ckpt")
    rec = model_db.record_for(str(q), _root(tmp_path), json.loads(p.read_text()))
    assert rec["rating"] == 2
