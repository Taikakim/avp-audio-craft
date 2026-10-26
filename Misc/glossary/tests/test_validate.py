# Owner: WINTERMUTE (created 2026-10-26)
"""One test per build error in spec section 5, plus the warnings."""
import pytest

from glossary.glossary_lib import validate
from helpers import make_entry, make_q, other_entry

VIZ = {"batch-noise", "step-size"}


def check(entries, publish=False, used_ids=None):
    return validate(entries, VIZ, publish, used_ids)


def test_a_clean_entry_has_no_errors_or_warnings():
    assert check([make_entry(), other_entry()]) == ([], [])


@pytest.mark.parametrize("field", ["id", "term", "plain", "quiz"])
def test_missing_required_field(field):
    e = make_entry()
    del e[field]
    errors, _ = check([e])
    assert any(f"missing required field '{field}'" in x for x in errors)


def test_empty_required_field_counts_as_missing():
    errors, _ = check([make_entry(plain="")])
    assert any("missing required field 'plain'" in x for x in errors)


@pytest.mark.parametrize("n", [4, 6])
def test_option_count_other_than_five(n):
    q = make_q(1, options=list("abcdef"[:n]))
    errors, _ = check([make_entry(quiz=[q, make_q(2), make_q(3)])])
    assert any("exactly 5 options" in x for x in errors)


@pytest.mark.parametrize("bad", [5, -1, True, "0", 1.0])
def test_answer_out_of_range(bad):
    errors, _ = check([make_entry(quiz=[make_q(1, answer=bad), make_q(2), make_q(3)])])
    assert any("out of range" in x for x in errors)


def test_answer_zero_is_valid():
    assert check([make_entry(quiz=[make_q(1, answer=0), make_q(2), make_q(3)])]) == ([], [])


@pytest.mark.parametrize("n", [0, 2, 6])
def test_question_count_outside_three_to_five(n):
    errors, _ = check([make_entry(quiz=[make_q(1 + i % 3) for i in range(n)])])
    assert errors      # 0 questions is reported as a missing field, 2 and 6 as a count error
    if n:
        assert any("3-5 quiz questions" in x for x in errors)


def test_level_must_be_one_to_three():
    errors, _ = check([make_entry(quiz=[make_q(4), make_q(2), make_q(3)])])
    assert any("level must be" in x for x in errors)


def test_duplicate_id():
    errors, _ = check([make_entry(), make_entry(term="other term")])
    assert any("duplicate id" in x for x in errors)


def test_duplicate_alias_across_entries():
    a = make_entry(aliases=["running average"])
    b = other_entry(aliases=["Running  Average"])           # same after case/space normalising
    errors, _ = check([a, b])
    assert any("alias 'Running  Average' collides with alias of 'momentum'" in x for x in errors)


def test_duplicate_alias_inside_one_entry():
    errors, _ = check([make_entry(aliases=["avg", "AVG"])])
    assert any("duplicate alias" in x for x in errors)


def test_alias_equal_to_another_entrys_term():
    errors, _ = check([other_entry(), make_entry(aliases=["weight"])])
    assert any("alias 'weight' collides with term of 'weight'" in x for x in errors)


def test_duplicate_term_across_entries():
    errors, _ = check([make_entry(), other_entry(term="momentum")])
    assert any("term 'momentum' collides with term of 'momentum'" in x for x in errors)


def test_term_equal_to_another_entrys_alias():
    errors, _ = check([make_entry(aliases=["grad"]), other_entry(term="grad")])
    assert any("term 'grad' collides with alias of 'momentum'" in x for x in errors)


def test_unknown_viz_is_a_warning_in_dry_run_and_an_error_when_publishing():
    e = make_entry(viz={"module": "nope", "params": {}})
    errors, warnings = check([e], publish=False)
    assert errors == [] and any("unknown viz module 'nope'" in w for w in warnings)
    errors, warnings = check([e], publish=True)
    assert any("unknown viz module 'nope'" in x for x in errors) and warnings == []


def test_known_viz_passes():
    assert check([make_entry(viz={"module": "step-size", "params": {}})]) == ([], [])


def test_viz_without_module_is_an_error():
    errors, _ = check([make_entry(viz={"params": {}})])
    assert any("needs a 'module'" in x for x in errors)


def test_wrong_given_for_the_correct_option():
    q = make_q(1, answer=2, wrong={"2": "that is the right one"})
    errors, _ = check([make_entry(quiz=[q, make_q(2), make_q(3)])])
    assert any("correct option" in x for x in errors)


def test_wrong_for_an_incorrect_option_is_fine():
    q = make_q(1, answer=2, wrong={"1": "no, that is EMA"})
    assert check([make_entry(quiz=[q, make_q(2), make_q(3)])]) == ([], [])


def test_wrong_key_must_be_an_option_index():
    q = make_q(1, wrong={"7": "x"})
    errors, _ = check([make_entry(quiz=[q, make_q(2), make_q(3)])])
    assert any("not an option index" in x for x in errors)


def test_plain_longer_than_one_sentence_warns():
    _, warnings = check([make_entry(plain="One thing. Another thing.")])
    assert any("one sentence" in w for w in warnings)


def test_plain_with_code_and_a_decimal_is_one_sentence():
    _, warnings = check([make_entry(plain="Uses `m = 0.9 * m` with beta 0.9, so it remembers about 10 steps.")])
    assert warnings == []


def test_quiz_reviewed_rule_applies_only_to_entries_a_page_uses():
    e, o = make_entry(quiz_reviewed=None), other_entry(quiz_reviewed=None)
    assert check([e, o]) == ([], [])                                  # no page given: rule off
    errors, warnings = check([e, o], used_ids={"momentum"})
    assert errors == [] and len(warnings) == 1 and "momentum" in warnings[0]
    errors, _ = check([e, o], publish=True, used_ids={"momentum"})
    assert len(errors) == 1 and "momentum" in errors[0]
    assert check([e, o], publish=True, used_ids=set()) == ([], [])    # page uses nothing
    assert check([make_entry(), o], publish=True, used_ids={"momentum"}) == ([], [])   # reviewed
