import pytest

import forge_testutil  # noqa: F401
from forge import render_settings as R
from forge.contract import ForgeError

HEADS = {"rms_energy_bass": {"default_gain": 512.0}, "chroma_other": {"default_gain": 2048.0}}


def test_render_defaults_and_key():
    r = R.parse_render(None)
    assert r["steps"] == 24 and r["cfg_scale"] == 6.0 and r["schedule"]["shape"] == "model"
    assert R.canonical_key(R.parse_render({"prompt": "a", "steps": 8})) == \
        R.canonical_key(R.parse_render({"steps": 8, "prompt": "a"}))
    req = R.to_request(R.parse_render({"prompt": "pad"}), 77)
    assert req["seed"] == 77 and req["prompt"] == "pad" and req["cfg_interval_progress"] == [0.0, 1.0]


@pytest.mark.parametrize("bad", [
    {"steps": 0}, {"steps": 151}, {"cfg_scale": 65}, {"cfg_interval_progress": [0.6, 0.5]},
    {"sampler_type": "k-heun"}, {"scale_phi": 2}, {"bogus": 1}, {"schedule": {"shape": "karras"}},
])
def test_render_rejects(bad):
    with pytest.raises(ForgeError):
        R.parse_render(bad)


def chain(**kw):
    base = {"latch_on": True,
            "slots": [{"head": "rms_energy_bass", "kind": "constant", "value": -12.0, "weight": 2.0,
                       "start_pct": 0.0, "end_pct": 0.6},
                      {"head": "none", "kind": "constant", "value": 0.0, "weight": 1.0,
                       "start_pct": 0.0, "end_pct": 0.6}],
            "hparams": {"rho": 1.0, "mu": 0.5, "gamma": 0.3, "n_iter": 4, "log_norms": True}}
    base.update(kw)
    return R.parse_chain(base)


def test_chain_latch_gains():
    out = R.chain_to_request(chain(), HEADS)
    assert out["latch"] == [{"head": "rms_energy_bass", "kind": "constant", "value": -12.0, "gain": 1024.0,
                             "start_pct": 0.0, "end_pct": 0.6}]
    assert (out["rho"], out["mu"], out["gamma"], out["n_iter"], out["log_norms"]) == (1024.0, 512.0, 0.3, 4, True)
    assert out["film"] is None and out["dora"] is None


def test_chain_film_lora_and_off():
    c = chain(latch_on=False, film_on=True, film={"ckpt": None, "gain": 1.2, "value": 6.0},
              lora_on=True, lora={"ckpt_path": "/x.ckpt", "slot": None, "strength": 0.8})
    out = R.chain_to_request(c, HEADS)
    assert out["latch"] is None
    assert out["film"] == {"ckpt": None, "gain": 1.2, "value": 6.0}
    assert out["dora"] == {"ckpt_path": "/x.ckpt", "strength": 0.8}
    c2 = chain(latch_on=False, lora_on=True, lora={"ckpt_path": None, "slot": 1, "strength": 1.0})
    assert R.chain_to_request(c2, HEADS)["dora"] == {"slot": 1, "strength": 1.0}
    assert R.chain_to_request(None, HEADS) == {"latch": None, "film": None, "dora": None}


def test_chain_rejects():
    with pytest.raises(ForgeError):
        R.chain_to_request(chain(slots=[{"head": "nope", "kind": "constant", "value": 0, "weight": 1,
                                         "start_pct": 0, "end_pct": 0.6}] * 2), HEADS)
    with pytest.raises(ForgeError):
        chain(hparams={"rho": 31, "mu": 1, "gamma": 0.3, "n_iter": 4, "log_norms": False})
    with pytest.raises(ForgeError):
        chain(semitones=30)
