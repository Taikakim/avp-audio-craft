# Owner: WINTERMUTE (created 2026-10-26)
import json

import pytest

from glossary import glossary_lib as gl


def test_inline_matches_the_blog_rules():
    assert gl.inline("a `x<y` and **bold** and *em*") == "a <code>x&lt;y</code> and <strong>bold</strong> and <em>em</em>"
    assert gl.inline("see [paper](https://arxiv.org/abs/1) now") == 'see <a href="https://arxiv.org/abs/1">paper</a> now'
    # only http(s) links are links; a local path stays visible text
    assert gl.inline("[x](assets/a.png)") == "[x](assets/a.png)"
    assert gl.inline("5 < 6 & 7") == "5 &lt; 6 &amp; 7"


def test_publish_blog_uses_the_shared_inline():
    import publish_blog as pb
    assert pb._inline is gl.inline
    assert pb.md_to_html("# T\n\nsome `code` here") == "<h1>T</h1>\n<p>some <code>code</code> here</p>"


def test_load_glossary_reads_all_files_in_name_order(tmp_path):
    (tmp_path / "b.json").write_text(json.dumps([{"id": "b"}]))
    (tmp_path / "a.json").write_text(json.dumps([{"id": "a1"}, {"id": "a2"}]))
    (tmp_path / "notes.txt").write_text("ignored")
    assert [e["id"] for e in gl.load_glossary(tmp_path)] == ["a1", "a2", "b"]


def test_load_glossary_rejects_bad_files(tmp_path):
    (tmp_path / "x.json").write_text("{not json")
    with pytest.raises(ValueError, match="x.json"):
        gl.load_glossary(tmp_path)
    (tmp_path / "x.json").write_text('{"id": "a"}')
    with pytest.raises(ValueError, match="list"):
        gl.load_glossary(tmp_path)
