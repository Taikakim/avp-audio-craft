"""TDD for rarity_gen grid/shard/naming (pure; the generate loop needs GPU)."""
from rarity_gen import build_variants, build_grid, select, clip_name, promptid

SPECS = [{"prompt": f"p{i}", "band": b, "seed": 1000 + i}
         for i, b in enumerate(["common", "mid", "rare"] * 50)]  # 150 specs


def test_15_model_variants():
    v = build_variants()
    assert len(v) == 15                                   # base 3 + evr1x 6 + newstack 6
    assert sum(1 for x in v if x["source"] == "base") == 3
    assert all(x["weight"] == 1.0 for x in v if x["source"] == "base")
    assert {x["weight"] for x in v if x["source"] == "evr1x"} == {1.0, 1.33}
    assert {x["cfg"] for x in v} == {1.0, 6.0, 16.0}


def test_grid_is_2250():
    assert len(build_grid(build_variants(), SPECS)) == 15 * 150


def test_shards_partition_the_grid_without_overlap():
    grid = build_grid(build_variants(), SPECS)
    seen = []
    for i in range(8):
        seen += select(grid, shard=i, shards=8)
    assert len(seen) == len(grid)                         # every clip covered exactly once
    names = [clip_name(g) for g in seen]
    assert len(set(names)) == len(names)                  # no dup / no overlap across shards


def test_variant_filters():
    grid = build_grid(build_variants(), SPECS)
    only = select(grid, source="evr1x", weight=1.33, cfg=16.0)
    assert len(only) == 150 and all(g["source"] == "evr1x" for g in only)


def test_clip_name_format_and_promptid_stable():
    g = {"source": "evr1x", "weight": 1.33, "cfg": 16.0, "band": "rare",
         "seed": 42, "promptid": promptid("hello")}
    assert clip_name(g) == f"evr1x_w133_cfg16__rare__{promptid('hello')}__s42.wav"
    assert promptid("hello") == promptid("hello")         # deterministic
