"""ckpt_tag must not collapse DDP replicas onto one label.

A -vN checkpoint is a SEPARATELY TRAINED model (Pattern-2 incident, A4/A9/A10), not a
duplicate. Collapsing it destroys replica identity in the render filename, upstream of
every rating — GHOST-NOTE verified 22,036 clip rows carry no -vN marker as a result.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_matrix_gen import ckpt_tag


def test_bare_unchanged_so_existing_joins_survive():
    assert ckpt_tag("epoch=19-step=5980.ckpt") == "ep19"
    assert ckpt_tag("epoch=7-step=100.weights.ckpt") == "ep7"


def test_replicas_get_distinct_tags():
    assert ckpt_tag("epoch=19-step=5980-v1.ckpt") == "ep19v1"
    assert ckpt_tag("epoch=19-step=5980-v7.ckpt") == "ep19v7"


def test_replica_and_bare_never_collide():
    tags = {ckpt_tag(f"epoch=11-step=3588{sfx}.ckpt") for sfx in ("", "-v1", "-v2", "-v3")}
    assert len(tags) == 4, f"replicas collapsed onto {tags}"


def test_non_epoch_filename_still_falls_back():
    assert ckpt_tag("riffer_final.pt") == "riffer_final"
