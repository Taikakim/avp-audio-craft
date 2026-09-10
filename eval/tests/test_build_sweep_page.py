import json
import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import build_sweep_page as B


def _manifest(tmp_path, recs):
    p = tmp_path / "manifest.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return p


def _rec(**kw):
    base = {"schema": 1, "cell_id": "c1", "coords": {"strength": 1.0, "seed": 7},
            "status": "ok", "files": ["/tmp/a.wav"], "latents": ["/tmp/a.z0.npy"],
            "z0_missing": False, "seed": 7, "payload": {"prompt": "goa"},
            "sweep": {"name": "s", "preset": "p"}}
    base.update(kw)
    return base


def test_reading_skips_corrupt_lines(tmp_path):
    p = _manifest(tmp_path, [_rec()])
    with open(p, "a") as f:
        f.write("{ nope\n")
    assert len(B.read_manifest(p)) == 1


def test_two_axes_pivot_to_rows_and_columns(tmp_path):
    recs = [_rec(cell_id=f"c{i}", coords={"strength": s, "cfg": c, "seed": 7})
            for i, (s, c) in enumerate([(0.5, 7), (0.5, 16), (1.0, 7), (1.0, 16)])]
    piv = B.pivot(recs)
    assert piv["rows"] == [0.5, 1.0] and piv["cols"] == [7, 16]


def test_the_model_axis_is_always_the_column_axis(tmp_path):
    recs = [_rec(cell_id=f"c{i}", coords={"model": m, "strength": s, "seed": 7})
            for i, (m, s) in enumerate([("A", 0.5), ("B", 0.5), ("A", 1.0), ("B", 1.0)])]
    piv = B.pivot(recs)
    assert piv["cols"] == ["A", "B"]


def test_the_page_carries_all_three_audience_blocks(tmp_path):
    p = _manifest(tmp_path, [_rec()])
    out = tmp_path / "page.html"
    B.build(p, out)
    html = out.read_text()
    assert "what this sweep tests" in html.lower()          # audience 3: learning
    assert "goa" in html                                     # audience 2: the payload
    assert "playhead" in html.lower()                        # audience 1: the tool
    assert "sweep_run.py" in html                            # reproduction command


def test_errors_and_missing_z0_are_visible_not_hidden(tmp_path):
    p = _manifest(tmp_path, [_rec(status="error", error="boom", files=[]),
                             _rec(cell_id="c2", z0_missing=True)])
    out = tmp_path / "page.html"
    B.build(p, out)
    html = out.read_text()
    assert "boom" in html and "z0" in html.lower()


def test_a_strength_axis_gets_its_plain_language_sentence(tmp_path):
    assert "as trained" in B.explainer_html({"axes": ["strength"]}).lower()


def test_an_axis_with_no_written_explainer_says_so_rather_than_going_silent(tmp_path):
    assert "no explainer written" in B.explainer_html({"axes": ["quux"]}).lower()


def test_an_empty_manifest_produces_a_page_that_says_so_rather_than_crashing(tmp_path):
    p = tmp_path / "manifest.jsonl"
    p.write_text("")
    out = tmp_path / "page.html"
    B.build(p, out)
    assert "no cells" in out.read_text().lower()


def test_the_wide_table_gets_its_own_horizontal_scroll_wrapper(tmp_path):
    # build_evals.CSS sets overflow-x:hidden on html+body so the waveform popup
    # centres correctly on mobile; a wide table therefore MUST bring its own
    # scroller or it is simply clipped (Kim, 2026-07-10).
    p = _manifest(tmp_path, [_rec()])
    out = tmp_path / "page.html"
    B.build(p, out)
    assert "overflow-x:auto" in out.read_text()


def test_nowrap_is_confined_to_table_cells_which_have_their_own_scroller(tmp_path):
    # build_evals.CSS sets overflow-x:hidden on html+body, so a nowrap element
    # wider than the viewport would be clipped rather than scrolled. Keep nowrap
    # inside the table (which brings its own overflow-x:auto) and let the header,
    # which carries a full manifest path, wrap.
    p = _manifest(tmp_path, [_rec()])
    out = tmp_path / "page.html"
    B.build(p, out)
    css = out.read_text()
    assert ".sw-meta{font-size:10.5px;color:var(--faint);overflow-wrap:anywhere}" in css
    assert ".sw-cell .sw-meta{white-space:nowrap}" in css
