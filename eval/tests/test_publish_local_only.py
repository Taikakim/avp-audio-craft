"""What score_and_publish withholds from the public rsync.

The leak scan is the last gate before bytes leave the box, and it fails LOUDLY -- which
is right, but it means every artefact that carries local paths BY DESIGN has to be
withheld structurally, or it blocks every publish until someone redacts a file that was
never meant to ship. Two such classes exist beyond the named run_meta/_meta sidecars,
and both were found blocking a real publish on 2026-09-09 (W).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import score_and_publish as sp                                    # noqa: E402


def _stage(tmp_path, monkeypatch, *names):
    for n in names:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    monkeypatch.setattr(sp, "STAGE", tmp_path)


def test_named_sidecars_withheld(tmp_path, monkeypatch):
    _stage(tmp_path, monkeypatch, "a/run_meta.json", "a/_meta.json", "soup/BLEND.ptm_a050.json",
           "d/AUDIT_2026-09-07_duration.json")
    for f in ("a/run_meta.json", "a/_meta.json", "soup/BLEND.ptm_a050.json",
              "d/AUDIT_2026-09-07_duration.json"):
        assert sp.is_local_only(f), f


def test_per_clip_sidecar_withheld_but_page_data_published(tmp_path, monkeypatch):
    # The sidecar is named after its clip, so only the sibling test can catch it.
    _stage(tmp_path, monkeypatch, "s/ptm__goa__st24.m4a", "s/ptm__goa__st24.json",
           "s/descriptors.json", "manifest_live.jsonl")
    assert sp.is_local_only("s/ptm__goa__st24.json")
    assert not sp.is_local_only("s/descriptors.json")     # no sibling clip -> page data
    assert not sp.is_local_only("manifest_live.jsonl")


def test_page_with_redacted_twin_withheld(tmp_path, monkeypatch):
    _stage(tmp_path, monkeypatch, "morph/index.html", "morph/index_public.html",
           "model_matrix.html")
    assert sp.is_local_only("morph/index.html")
    assert not sp.is_local_only("morph/index_public.html")   # the twin IS what ships
    assert not sp.is_local_only("model_matrix.html")         # no twin -> normal page
