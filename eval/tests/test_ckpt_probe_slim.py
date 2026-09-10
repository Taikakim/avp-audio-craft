"""fat/slim detection across BOTH optimizer-state conventions.

Testing only Lightning's `optimizer_states` reported the entire `riffer_*.pt`
control-adapter family as slim. They are not: measured on a real one, `opt` is
1359.6 MB of 1813 MB — 75% of the file. The consequence was not cosmetic: the
model census told us 32 arms had no resumable copy, and the LUMI pull was sized
4x too small.
"""
import pickle
import sys
import zipfile

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import ckpt_probe


def _fake_ckpt(tmp_path, obj, name="x.pt", protocol=4):
    """A minimal torch-shaped zip: one data.pkl member, pickled like torch does."""
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("archive/data.pkl", pickle.dumps(obj, protocol=protocol))
    return p


def test_lightning_optimizer_states_is_detected_as_fat(tmp_path):
    p = _fake_ckpt(tmp_path, {"state_dict": {}, "optimizer_states": [{"a": 1}]})
    assert ckpt_probe.probe(p)["slim"] is False


def test_the_riffer_opt_key_is_detected_as_fat(tmp_path):
    # the regression this file exists for
    p = _fake_ckpt(tmp_path, {"state": {}, "opt": {"a": 1}, "control_mode": "melody_contour"})
    assert ckpt_probe.probe(p)["slim"] is False


def test_a_weights_only_checkpoint_is_still_slim(tmp_path):
    p = _fake_ckpt(tmp_path, {"state_dict": {}, "epoch": 3})
    assert ckpt_probe.probe(p)["slim"] is True


def test_a_bare_opt_substring_does_not_falsely_mark_fat(tmp_path):
    # "optimizer" / "opt_state" as VALUES or as parts of longer names must not
    # trip the check -- that is why the match is length-prefixed, not a substring.
    p = _fake_ckpt(tmp_path, {"state_dict": {}, "optimizer_name": "adamw",
                              "notes": "opt was stripped; opt_state removed"})
    assert ckpt_probe.probe(p)["slim"] is True


def test_both_pickle_string_encodings_are_matched(tmp_path):
    # protocol 4 writes SHORT_BINUNICODE for short keys, protocol 2 BINUNICODE;
    # torch has emitted both across versions.
    for proto in (2, 4):
        p = _fake_ckpt(tmp_path, {"state": {}, "opt": {"a": 1}},
                       name=f"p{proto}.pt", protocol=proto)
        assert ckpt_probe.probe(p)["slim"] is False, f"protocol {proto}"
