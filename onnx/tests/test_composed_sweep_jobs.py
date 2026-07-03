"""Tests for the composed-sweep driver's job construction (Misc/composed_sweep_eval.py).

Run: python3 -m pytest onnx/tests/test_composed_sweep_jobs.py -q  (from SAO root)
"""
import importlib.util
import json
import sys
from pathlib import Path

SAO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SAO / "onnx"))

spec = importlib.util.spec_from_file_location(
    "composed_sweep_eval", SAO / "Misc" / "composed_sweep_eval.py")
cse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cse)

FIT = {"bin_centers": [1.0, 5.0, 9.0], "bin_means": [0.7, 1.1, 1.5],
       "support": [0.5, 9.7], "linear": {"a": 0.1, "b": 0.6, "r2": 0.35}, "n": 100}


def _base(**kw):
    d = dict(prompt="goa", prompt_idx=0, seed=1234, gain=2.0, density=5.0,
             steps=24, cfg=6.0, fit=FIT, latch_cfg=None, name="x")
    d.update(kw)
    return d


def test_job_without_latch_has_no_latch_key():
    job, in_support = cse.build_job(**_base())
    assert "latch" not in job
    assert job["onset_density"] == 5.0 and job["gain"] == 2.0 and job["seed"] == 1234
    assert in_support


def test_job_with_latch_maps_density_to_raw_target():
    lc = {"head_ckpt": "h.pt", "rho": 256.0, "mu": 256.0}
    job, in_support = cse.build_job(**_base(latch_cfg=lc))
    assert job["latch"]["head_ckpt"] == "h.pt"
    assert abs(job["latch"]["target_raw"] - 1.1) < 1e-9   # density 5 -> bin mean 1.1
    assert job["latch"]["rho"] == 256.0
    assert in_support


def test_extrapolated_density_flagged():
    lc = {"head_ckpt": "h.pt", "rho": 256.0, "mu": 256.0}
    job, in_support = cse.build_job(**_base(density=12.0, latch_cfg=lc))
    assert not in_support
    assert job["latch"]["target_raw"] > 1.5               # edge-slope continuation


def test_seed_reaches_job_verbatim():
    job, _ = cse.build_job(**_base(seed=4242))
    assert job["seed"] == 4242
