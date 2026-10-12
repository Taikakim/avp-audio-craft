# Owner: GHOST-NOTE (created 2026-10-12)
"""Preset FOLDERS (ComfyUI-style): 'folder/name' round-trips, lists with its folder, and cannot escape the preset dir."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import presets  # noqa: E402


def test_folder_roundtrip_and_listing(tmp_path):
    presets.save("v7-full/d4-o2 variant", {"prompt": "x"}, notes="n", dir=tmp_path)
    presets.save("plain", {"prompt": "y"}, dir=tmp_path)
    assert (tmp_path / "v7-full" / "d4-o2-variant.json").exists()
    assert presets.load("v7-full/d4-o2 variant", dir=tmp_path)["payload"]["prompt"] == "x"
    got = {p["name"]: p["folder"] for p in presets.list_presets(dir=tmp_path)}
    assert got == {"v7-full/d4-o2 variant": "v7-full", "plain": ""}


def test_cannot_escape_the_dir(tmp_path):
    p = presets.save("../../evil/../x", {"prompt": "z"}, dir=tmp_path / "root")
    assert (tmp_path / "root") in p.parents
