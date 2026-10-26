# Owner: WINTERMUTE (created 2026-10-26)
"""publish_blog.py help-pane integration. Nothing here talks to the server: dry-run paths only."""
import json
import sys
from pathlib import Path

import pytest

import publish_blog as pb
from glossary import mark as gmark
from helpers import make_entry, other_entry

DRAFT = """<!-- DRAFT 2026-10-26
{flag}
-->
# The weight guide

The weight matrix and the weights. Also `weight` in code.

## weight heading

Momentum helps.
"""


@pytest.fixture
def site_help(tmp_path, monkeypatch):
    sh = tmp_path / "site_help"
    (sh / "viz" / "lib").mkdir(parents=True)
    (sh / "tests").mkdir()
    (sh / "help-pane.js").write_text("// pane")
    (sh / "help-pane.css").write_text("/* pane */")
    (sh / "viz" / "step-size.js").write_text("export function mount(){}")
    (sh / "viz" / "lib" / "maths.js").write_text("")
    (sh / "tests" / "test_pane_browser.py").write_text("")
    monkeypatch.setattr(pb, "SITE_HELP", sh)
    return sh


def write_glossary(tmp_path, entries):
    g = tmp_path / "glossary"
    g.mkdir(exist_ok=True)
    (g / "t.json").write_text(json.dumps(entries), encoding="utf-8")
    return g


def draft(tmp_path, flag="help-pane: on", name="2026-10-26-pane-test-DRAFT.md"):
    p = tmp_path / name
    p.write_text(DRAFT.format(flag=flag), encoding="utf-8")
    return p


GL = [make_entry(), other_entry(id="weight-matrix", term="weight matrix", plain="A grid of weights."),
      other_entry()]


@pytest.mark.parametrize("flag,expected", [("help-pane: on", True), ("  Help-Pane:  ON  ", True),
                                           ("help-pane: off", False), ("no flag here", False),
                                           ("help-pane: onwards", False)])
def test_help_pane_on_reads_the_header_comment(flag, expected):
    assert pb.help_pane_on(DRAFT.format(flag=flag)) is expected


def test_flag_outside_the_header_comment_is_ignored():
    assert pb.help_pane_on("# Title\n\nhelp-pane: on\n") is False
    assert pb.help_pane_on("# T\n<!--\nhelp-pane: on\n-->\n") is False      # comment must come first


def test_post_without_the_flag_is_unchanged(tmp_path):
    doc, title = pb.render_post(draft(tmp_path, flag="nothing"), GL)
    assert title == "The weight guide"
    assert doc.endswith("</article>\n</div></body></html>")
    assert "help-pane" not in doc and 'class="gl"' not in doc


def test_post_with_the_flag_marks_terms_and_adds_the_c3_tags(tmp_path):
    doc, _ = pb.render_post(draft(tmp_path), GL)
    assert '<a class="gl" data-term="weight-matrix" href="../help/glossary.html#weight-matrix">weight matrix</a>' in doc
    assert 'data-term="weight" href="../help/glossary.html#weight">weights</a>' in doc
    assert "<code>weight</code>" in doc and "<h1>The weight guide</h1>" in doc    # skip zones
    assert "<h2>weight heading</h2>" in doc
    assert 'data-term="momentum"' in doc
    assert doc.endswith('</div>\n<link rel="stylesheet" href="../help/help-pane.css">\n'
                        '<script type="module" src="../help/help-pane.js" data-glossary="../help/glossary.json" '
                        'data-viz-base="../help/viz/"></script>\n</body></html>')
    assert gmark.used_ids(doc) == {"weight-matrix", "weight", "momentum"}


def test_flag_without_a_glossary_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no glossary"):
        pb.render_post(draft(tmp_path), None)


def test_build_help_dir_assembles_pane_files_and_glossary(tmp_path, site_help):
    out = tmp_path / "help"
    pb.build_help_dir(out, write_glossary(tmp_path, GL), publish=True, page_used_ids={"weight"})
    for rel in ("help-pane.js", "help-pane.css", "viz/step-size.js", "viz/lib/maths.js",
                "glossary.json", "glossary.html"):
        assert (out / rel).is_file(), rel
    assert not (out / "tests").exists()
    assert set(json.loads((out / "glossary.json").read_text())["entries"]) == {"momentum", "weight-matrix", "weight"}


def test_unreviewed_entry_used_by_the_page_blocks_publishing_but_not_dry_run(tmp_path, site_help, capsys):
    gloss = [make_entry(quiz_reviewed=None), other_entry()]
    g = write_glossary(tmp_path, gloss)
    with pytest.raises(SystemExit, match="quiz_reviewed"):
        pb.build_help_dir(tmp_path / "a", g, publish=True, page_used_ids={"momentum"})
    pb.build_help_dir(tmp_path / "b", g, publish=False, page_used_ids={"momentum"})
    assert "WARNING (glossary): momentum: quiz_reviewed is empty" in capsys.readouterr().out


def test_unreviewed_entry_the_page_does_not_use_is_fine(tmp_path, site_help):
    g = write_glossary(tmp_path, [make_entry(quiz_reviewed=None), other_entry()])
    pb.build_help_dir(tmp_path / "a", g, publish=True, page_used_ids={"weight"})


def test_unreviewed_entry_reachable_from_a_used_entry_blocks_publishing(tmp_path, site_help):
    g = write_glossary(tmp_path, [make_entry(plain="Averages the weights."), other_entry(quiz_reviewed=None)])
    with pytest.raises(SystemExit, match="weight: quiz_reviewed"):
        pb.build_help_dir(tmp_path / "a", g, publish=True, page_used_ids={"momentum"})


def test_unknown_viz_blocks_publishing_only(tmp_path, site_help):
    g = write_glossary(tmp_path, [make_entry(viz={"module": "ghost", "params": {}})])
    with pytest.raises(SystemExit, match="unknown viz module 'ghost'"):
        pb.build_help_dir(tmp_path / "a", g, publish=True, page_used_ids=set())
    pb.build_help_dir(tmp_path / "b", g, publish=False, page_used_ids=set())


def test_glossary_that_leaks_a_path_is_refused(tmp_path, site_help):
    g = write_glossary(tmp_path, [make_entry(ours="Stored under /home/kim/secret/place.")])
    with pytest.raises(SystemExit, match="leaks"):
        pb.build_help_dir(tmp_path / "a", g, publish=False, page_used_ids=set())


def test_glossary_errors_refuse_before_anything_is_written(tmp_path, site_help):
    g = write_glossary(tmp_path, [make_entry(quiz=[])])
    with pytest.raises(SystemExit, match="REFUSING: glossary errors"):
        pb.build_help_dir(tmp_path / "a", g, publish=False, page_used_ids=set())
    assert not (tmp_path / "a" / "glossary.json").exists()


def test_reset_dryrun_creates_the_c1_root_and_guards_its_name(tmp_path):
    root = tmp_path / "blog_dryrun"
    (root / "stale").mkdir(parents=True)
    pb._reset_dryrun(root)
    assert (root / "blog").is_dir() and (root / "edg3.css").is_file() and not (root / "stale").exists()
    with pytest.raises(ValueError, match="blog_dryrun"):
        pb._reset_dryrun(tmp_path)


def test_dry_run_main_writes_the_c1_layout(tmp_path, site_help, monkeypatch, capsys):
    root = tmp_path / "blog_dryrun"
    monkeypatch.setattr(pb, "DRYRUN_ROOT", root)
    monkeypatch.setattr(pb, "_live_slugs", lambda: None)            # no ssh in tests
    p = draft(tmp_path)
    monkeypatch.setattr(sys, "argv", ["publish_blog.py", "--dry-run", "--glossary-dir",
                                      str(write_glossary(tmp_path, GL)), str(p)])
    pb.main()
    page = (root / "blog" / "2026-10-26-pane-test.html").read_text()
    assert 'data-term="weight-matrix"' in page and "../help/help-pane.js" in page
    assert (root / "blog" / "index.html").is_file() and (root / "edg3.css").is_file()
    for rel in ("help/help-pane.js", "help/viz/step-size.js", "help/glossary.json", "help/glossary.html"):
        assert (root / rel).is_file(), rel
    assert "nothing pushed" in capsys.readouterr().out


def test_dry_run_main_without_pane_posts_builds_no_help_dir(tmp_path, site_help, monkeypatch):
    root = tmp_path / "blog_dryrun"
    monkeypatch.setattr(pb, "DRYRUN_ROOT", root)
    monkeypatch.setattr(pb, "_live_slugs", lambda: None)
    monkeypatch.setattr(sys, "argv", ["publish_blog.py", "--dry-run",
                                      str(draft(tmp_path, flag="x", name="2026-10-26-plain-DRAFT.md"))])
    pb.main()
    assert (root / "blog" / "2026-10-26-plain.html").is_file() and not (root / "help").exists()
