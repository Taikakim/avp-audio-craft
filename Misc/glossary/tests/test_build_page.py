# Owner: WINTERMUTE (created 2026-10-26)
import json
from pathlib import Path

import pytest

from glossary import build_page as bp
from helpers import make_entry, make_q, other_entry

FIX = Path(__file__).parent / "fixtures" / "glossary"


def write(dirpath, entries, name="topic.json"):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / name).write_text(json.dumps(entries), encoding="utf-8")
    return dirpath


def viz_dir(tmp_path, *names):
    d = tmp_path / "viz"
    (d / "lib").mkdir(parents=True)
    (d / "lib" / "maths.js").write_text("")
    for n in names:
        (d / f"{n}.js").write_text("")
    return d


def test_known_viz_is_the_js_stems_without_lib(tmp_path):
    assert bp.known_viz(viz_dir(tmp_path, "step-size", "routing")) == {"step-size", "routing"}
    assert bp.known_viz(tmp_path / "missing") == set()


def test_build_writes_json_per_contract_c4_and_html(tmp_path):
    mom = make_entry(plain="A running average of weights and **momentum**.", ours="Our `weight` setup.",
                     papers=[{"title": "Muon", "url": "https://kellerjordan.github.io/posts/muon/"}],
                     quiz=[make_q(3, q="Hard one about weight?", wrong={"1": "Not the weight."}),
                           make_q(1, q="Easy one"), make_q(2, q="Middle one")])
    wei = other_entry(viz={"module": "batch-noise", "params": {"k": 1}})
    out = tmp_path / "help"
    errors, warnings = bp.build(write(tmp_path / "g", [mom, wei]), viz_dir(tmp_path, "batch-noise"), out)
    assert errors == [] and warnings == []
    data = json.loads((out / "glossary.json").read_text(encoding="utf-8"))
    assert data["version"] == 1 and list(data["entries"]) == ["momentum", "weight"]
    m = data["entries"]["momentum"]
    assert m["term"] == "momentum"
    # inline syntax rendered, other terms marked relative to help/, own term left alone
    assert m["plain"] == ('A running average of <a class="gl" data-term="weight" href="glossary.html#weight">weights</a>'
                          ' and <strong>momentum</strong>.')
    assert m["ours"] == "Our <code>weight</code> setup."                     # inside code: a skip zone
    assert m["deeper"] == "" and m["viz"] is None
    assert m["papers"] == [{"title": "Muon", "url": "https://kellerjordan.github.io/posts/muon/"}]
    assert [q["level"] for q in m["quiz"]] == [1, 2, 3]                      # sorted by level
    assert m["quiz"][2]["wrong"] == {"1": 'Not the <a class="gl" data-term="weight" href="glossary.html#weight">weight</a>.'}
    assert data["entries"]["weight"]["viz"] == {"module": "batch-noise", "params": {"k": 1}}
    page = (out / "glossary.html").read_text(encoding="utf-8")
    assert 'id="momentum"' in page and 'id="weight"' in page and "<script" not in page
    assert 'href="../edg3.css"' in page and "Check your understanding (3 questions)" in page
    assert "Answer: A." in page


def test_own_term_never_links_to_itself(tmp_path):
    out = tmp_path / "help"
    bp.build(write(tmp_path / "g", [make_entry(plain="momentum keeps momentum.")]), viz_dir(tmp_path), out)
    assert 'data-term="momentum"' not in (out / "glossary.json").read_text(encoding="utf-8")


def test_errors_stop_the_build_and_write_nothing(tmp_path):
    out = tmp_path / "help"
    errors, _ = bp.build(write(tmp_path / "g", [make_entry(quiz=[make_q(1)])]), viz_dir(tmp_path), out)
    assert errors and not out.exists()


def test_unreadable_glossary_is_an_error(tmp_path):
    g = tmp_path / "g"
    g.mkdir()
    (g / "bad.json").write_text("{")
    errors, _ = bp.build(g, viz_dir(tmp_path), tmp_path / "help")
    assert errors and "bad.json" in errors[0]


def test_reachable_follows_links_between_entries(tmp_path):
    ents = [make_entry(plain="Uses the weight.", id="momentum"), other_entry(plain="See bias."),
            other_entry(id="bias", term="bias", plain="Offset."), other_entry(id="lonely", term="lonely", plain="x.")]
    compiled = bp.compile_entries(ents)
    assert bp.reachable({"momentum"}, compiled) == {"momentum", "weight", "bias"}
    assert bp.reachable({"unknown"}, compiled) == set()


def test_quiz_options_are_not_marked_but_question_and_why_are():
    q = {"level": 1, "q": "What is a weight?", "options": ["a weight", "b", "c", "d", "e"], "answer": 0,
         "why": "Each weight is a number."}
    ents = [make_entry(quiz=[q, q, q]), other_entry()]          # other_entry() is the "weight" entry
    item = bp.compile_entries(ents)["momentum"]["quiz"][0]
    assert 'class="gl"' not in item["options"][0]
    assert 'data-term="weight"' in item["q"] and 'data-term="weight"' in item["why"]


def test_cli_exit_codes_and_publish_flag(tmp_path, capsys):
    g = write(tmp_path / "g", [make_entry(viz={"module": "nope", "params": {}})])
    args = ["--glossary-dir", str(g), "--viz-dir", str(viz_dir(tmp_path)), "--out", str(tmp_path / "help")]
    assert bp.main(args) == 0
    assert "unknown viz module 'nope'" in capsys.readouterr().out          # a warning
    assert bp.main(args + ["--publish"]) == 1
    assert "ERROR: " in capsys.readouterr().out


def test_real_entries_copied_into_fixtures_build_cleanly(tmp_path):
    mods = {e["viz"]["module"] for f in FIX.glob("*.json") for e in json.loads(f.read_text()) if e.get("viz")}
    errors, warnings = bp.build(FIX, viz_dir(tmp_path, *mods), tmp_path / "help")
    assert errors == []
    data = json.loads((tmp_path / "help" / "glossary.json").read_text(encoding="utf-8"))
    assert {"momentum", "gradient-history", "weight", "weight-matrix"} <= set(data["entries"])
