# Owner: WINTERMUTE (created 2026-10-26)
"""Browser tests for site/help/help-pane.js (spec 2026-10-26-help-pane-design.md, section 6).

Run: /home/kim/Projects/mir/mir/bin/python -m pytest test_pane_browser.py -v [--root DIR --page blog/x.html]
"""
import html
import re
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

TAG = re.compile(r"<[^>]+>")


def plain_text(markup):
    """Visible text of an HTML snippet from glossary.json, whitespace-normalised."""
    return " ".join(html.unescape(TAG.sub("", markup or "")).split())


def load_page(page, url):
    """goto + wait until help-pane.js has finished starting (the pane element exists)."""
    page.goto(url)
    page.locator("#help-pane").wait_for(state="attached")


def term_link(page, term, which="first"):
    loc = page.locator(f'a.gl[data-term="{term}"]')
    return loc.first if which == "first" else loc.last


def open_via_click(page, page_url, term, which="first"):
    load_page(page, page_url)
    link = term_link(page, term, which)
    link.click()
    expect(page.locator("#help-pane")).to_be_visible()
    return link


# --------------------------------------------------------------------------- fallbacks (Review Focus 3)

@pytest.mark.parametrize("mode", ["json-404", "json-bad", "script-error"])
def test_links_navigate_when_pane_cannot_start(make_page, page_url, terms_on_page, mode):
    page = make_page()
    if mode == "json-404":
        page.route("**/glossary.json", lambda r: r.fulfill(status=404, body="nope"))
    elif mode == "json-bad":
        page.route("**/glossary.json", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{not json"))
    else:
        page.route("**/help-pane.js", lambda r: r.fulfill(
            status=200, content_type="text/javascript", body="throw new Error('boom');"))
    page.goto(page_url)
    term = terms_on_page[0]
    page.locator(f'a.gl[data-term="{term}"]').first.click()
    page.wait_for_url(re.compile(r"/help/glossary\.html#" + re.escape(term) + r"$"))
    assert page.locator("#help-pane").count() == 0


def test_links_navigate_without_javascript(make_page, page_url, terms_on_page):
    page = make_page(js=False)
    page.goto(page_url)
    term = terms_on_page[0]
    page.locator(f'a.gl[data-term="{term}"]').first.click()
    page.wait_for_url(re.compile(r"/help/glossary\.html#" + re.escape(term) + r"$"))


def test_term_unknown_to_glossary_navigates_normally(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, page_url)
    page.locator('a.gl[data-term="not-in-glossary"]').click()
    page.wait_for_url(re.compile(r"/help/glossary\.html#not-in-glossary$"))

# --------------------------------------------------------------------------- open / close / history

def test_click_opens_docked_pane_and_narrows_article(make_page, page_url, quiz_term, entries):
    page = make_page((1280, 800))
    load_page(page, page_url)
    start_path = page.evaluate("location.pathname")
    term_link(page, quiz_term).click()
    pane = page.locator("#help-pane")
    expect(pane).to_be_visible()
    assert page.evaluate("location.pathname") == start_path          # clicked link did not navigate
    expect(page.locator("body")).to_have_class(re.compile(r"\bhelp-pane-open\b"))
    box = pane.bounding_box()
    assert 0.35 * 1280 <= box["width"] <= 0.45 * 1280
    assert box["x"] + box["width"] >= 1279                           # docked on the right
    wrap_right = page.evaluate("document.querySelector('.wrap').getBoundingClientRect().right")
    assert wrap_right <= box["x"] + 1                                # article narrowed, not covered
    expect(page.locator("#hp-title")).to_have_text(entries[quiz_term]["term"])
    expect(page.locator("#help-pane .hp-plain")).to_have_text(plain_text(entries[quiz_term]["plain"]))
    assert page.evaluate("!!document.activeElement.closest('#help-pane')")   # focus moved into the pane
    assert page.evaluate("location.hash") == f"#gl={quiz_term}"


def test_pane_is_a_labelled_complementary_region_with_live_region(make_page, page_url, quiz_term, entries):
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    assert page.evaluate("document.getElementById('help-pane').tagName") == "ASIDE"
    assert page.evaluate("document.getElementById('help-pane').getAttribute('aria-labelledby')") == "hp-title"
    expect(page.locator("#help-pane [aria-live='polite']")).to_have_count(1)


def test_escape_closes_and_focus_returns_to_the_term(make_page, page_url, quiz_term):
    page = make_page()
    link = open_via_click(page, page_url, quiz_term)
    page.keyboard.press("Escape")
    expect(page.locator("#help-pane")).to_be_hidden()
    expect(page.locator("body")).not_to_have_class(re.compile(r"\bhelp-pane-open\b"))
    assert link.evaluate("el => el === document.activeElement")
    assert page.evaluate("location.hash") == ""


def test_close_button_closes(make_page, page_url, quiz_term):
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    page.locator("#help-pane .hp-close").click()
    expect(page.locator("#help-pane")).to_be_hidden()


def test_back_is_disabled_on_the_first_entry(make_page, page_url, quiz_term):
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    expect(page.locator("#help-pane .hp-back")).to_be_disabled()


def test_pane_link_pushes_history_and_back_returns(make_page, page_url, link_pair, entries):
    src, dst = link_pair
    page = make_page()
    load_page(page, f"{page_url}#gl={src}")
    expect(page.locator("#hp-title")).to_have_text(entries[src]["term"])
    expect(page.locator("#help-pane .hp-back")).to_be_disabled()
    page.locator(f'#help-pane :is(.hp-plain, .hp-ours) a.gl[data-term="{dst}"]').first.click()
    expect(page.locator("#hp-title")).to_have_text(entries[dst]["term"])
    assert page.evaluate("location.hash") == f"#gl={dst}"            # address follows navigation
    expect(page.locator("#help-pane .hp-back")).to_be_enabled()
    page.locator("#help-pane .hp-back").click()
    expect(page.locator("#hp-title")).to_have_text(entries[src]["term"])
    assert page.evaluate("location.hash") == f"#gl={src}"
    expect(page.locator("#help-pane .hp-back")).to_be_disabled()


def test_close_keeps_history_and_reopen_restores_the_last_entry(make_page, page_url, link_pair, entries):
    src, dst = link_pair
    page = make_page()
    load_page(page, f"{page_url}#gl={src}")
    page.locator(f'#help-pane :is(.hp-plain, .hp-ours) a.gl[data-term="{dst}"]').first.click()
    page.locator("#help-pane .hp-close").click()
    expect(page.locator("#help-pane")).to_be_hidden()
    expect(page.locator(".hp-reopen")).to_be_visible()
    page.locator(".hp-reopen").click()
    expect(page.locator("#help-pane")).to_be_visible()
    expect(page.locator("#hp-title")).to_have_text(entries[dst]["term"])    # last entry restored
    assert page.evaluate("location.hash") == f"#gl={dst}"
    page.locator("#help-pane .hp-back").click()                              # history survived the close
    expect(page.locator("#hp-title")).to_have_text(entries[src]["term"])


def test_reload_starts_empty(make_page, page_url, quiz_term):
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    page.locator("#help-pane .hp-close").click()
    page.reload()
    page.locator("#help-pane").wait_for(state="attached")
    expect(page.locator("#help-pane")).to_be_hidden()
    expect(page.locator(".hp-reopen")).to_be_hidden()


def test_reload_with_entry_open_has_no_history(make_page, page_url, link_pair, entries):
    src, dst = link_pair
    page = make_page()
    load_page(page, f"{page_url}#gl={src}")
    page.locator(f'#help-pane :is(.hp-plain, .hp-ours) a.gl[data-term="{dst}"]').first.click()
    page.reload()
    page.locator("#help-pane").wait_for(state="attached")
    expect(page.locator("#hp-title")).to_have_text(entries[dst]["term"])
    expect(page.locator("#help-pane .hp-back")).to_be_disabled()


# --------------------------------------------------------------------------- deep link

def test_deep_link_opens_the_entry_on_load(make_page, page_url, quiz_term, entries):
    page = make_page()
    load_page(page, f"{page_url}#gl={quiz_term}")
    expect(page.locator("#help-pane")).to_be_visible()
    expect(page.locator("#hp-title")).to_have_text(entries[quiz_term]["term"])


@pytest.mark.parametrize("bad_id", ["no-such-term", "constructor", "__proto__", "%E0%A4%A"])
def test_unknown_deep_link_is_ignored(make_page, page_url, bad_id):
    page = make_page()
    load_page(page, f"{page_url}#gl={bad_id}")
    expect(page.locator("#help-pane")).to_be_hidden()
    expect(page.locator(".hp-reopen")).to_be_hidden()
    assert page.hp_errors == []


def test_changing_the_hash_by_hand_opens_an_entry(make_page, page_url, quiz_term, entries):
    page = make_page()
    load_page(page, page_url)
    page.evaluate(f"location.hash = '#gl={quiz_term}'")
    expect(page.locator("#hp-title")).to_have_text(entries[quiz_term]["term"])


# --------------------------------------------------------------------------- marked terms

def test_visited_terms_get_a_fainter_underline_for_this_visit_only(make_page, page_url, terms_on_page):
    if len(terms_on_page) < 2:
        pytest.skip("need two distinct terms on the page")
    a, b = terms_on_page[:2]
    page = make_page()
    load_page(page, page_url)

    def colour(t):
        return term_link(page, t).evaluate("e => getComputedStyle(e).textDecorationColor")

    before_a, before_b = colour(a), colour(b)
    assert before_a == before_b
    term_link(page, a).click()
    page.keyboard.press("Escape")
    assert colour(a) != before_a        # visited: fainter
    assert colour(b) == before_b        # untouched term unchanged
    page.reload()
    page.locator("#help-pane").wait_for(state="attached")
    assert colour(a) == before_a        # memory is per page load only


def test_marked_term_underline_is_dotted_then_solid_on_hover(make_page, page_url, quiz_term):
    page = make_page()
    load_page(page, page_url)
    link = term_link(page, quiz_term)
    assert link.evaluate("e => getComputedStyle(e).textDecorationStyle") == "dotted"
    assert link.evaluate("e => getComputedStyle(e).backgroundColor") == "rgba(0, 0, 0, 0)"
    link.hover()
    assert link.evaluate("e => getComputedStyle(e).textDecorationStyle") == "solid"


def test_pane_header_is_not_styled_like_a_page_section_heading(make_page, page_url, quiz_term):
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    style = page.locator("#hp-title").evaluate(
        "e => { const s = getComputedStyle(e); return [s.textTransform, s.letterSpacing, s.borderBottomWidth]; }")
    assert style == ["none", "normal", "0px"]


# --------------------------------------------------------------------------- entry layout

LAYOUT_ORDER = ["hp-plain", "hp-ours", "hp-viz", "hp-deeper", "hp-papers", "hp-quiz-start"]


def _layout(page):
    return page.evaluate(
        "[...document.querySelectorAll('#help-pane .hp-body > *')].map(n => n.className.split(' ')[0])")


def test_entry_layout_follows_the_documented_order(make_page, page_url, viz_term):
    page = make_page()
    open_via_click(page, page_url, viz_term)
    page.wait_for_timeout(200)
    classes = _layout(page)
    assert classes[0] == "hp-plain"
    idx = [LAYOUT_ORDER.index(c) for c in classes]
    assert idx == sorted(idx), classes


def test_full_entry_has_every_layer_in_order(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, f"{page_url}#gl=ema")
    assert _layout(page) == LAYOUT_ORDER
    assert page.evaluate("document.querySelector('#help-pane .hp-deeper').open") is False   # collapsed
    expect(page.locator("#help-pane .hp-deeper summary")).to_have_text("Going deeper")
    expect(page.locator("#help-pane .hp-ours h3")).to_have_text("In our models")
    expect(page.locator("#help-pane .hp-quiz-start")).to_have_text("Check your understanding (3 questions)")
    paper = page.locator("#help-pane .hp-papers a").first
    assert paper.get_attribute("href") == "https://example.org/polyak"
    assert paper.get_attribute("rel") == "noopener noreferrer"
    page.locator("#help-pane .hp-deeper summary").click()
    assert page.evaluate("document.querySelector('#help-pane .hp-deeper').open") is True


def test_entry_without_optional_layers_shows_only_what_it_has(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, f"{page_url}#gl=momentum")        # no viz
    assert _layout(page) == ["hp-plain", "hp-ours", "hp-deeper", "hp-papers", "hp-quiz-start"]


# --------------------------------------------------------------------------- animation modules (C5)

def _viz_log(page):
    return page.evaluate("window.__vizLog || []")


def test_viz_module_is_mounted_with_params_and_help_object(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, f"{page_url}#gl=ema")
    expect(page.locator("#help-pane [data-testid=fixture-viz]")).to_be_visible()
    mounted = [x for x in _viz_log(page) if x.startswith("mounted:")]
    assert len(mounted) == 1
    info = __import__("json").loads(mounted[0][len("mounted:"):])
    assert info["params"] == {"decay": 0.999}
    assert info["keys"] == ["colors", "openTerm", "reducedMotion"]
    assert info["colorKeys"] == ["accent", "bad", "bg", "fg", "good", "muted"]
    assert info["openTerm"] == "function" and info["reducedMotion"] == "boolean"


def test_viz_is_destroyed_when_the_entry_changes_closes_or_the_quiz_opens(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, f"{page_url}#gl=ema")
    expect(page.locator("[data-testid=fixture-viz]")).to_be_visible()
    page.locator("#fixture-open-term").click()            # help.openTerm('momentum') from inside the viz
    expect(page.locator("#hp-title")).to_have_text("momentum")
    assert _viz_log(page).count("destroyed") == 1
    page.locator("#help-pane .hp-back").click()           # back to ema: a fresh mount
    expect(page.locator("[data-testid=fixture-viz]")).to_be_visible()
    assert len([x for x in _viz_log(page) if x.startswith("mounted:")]) == 2
    page.locator("#help-pane .hp-quiz-start").click()     # leaving the entry for the quiz
    expect(page.locator("#help-pane [data-testid=fixture-viz]")).to_have_count(0)
    assert _viz_log(page).count("destroyed") == 2


def test_viz_is_destroyed_on_close(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, f"{page_url}#gl=ema")
    expect(page.locator("[data-testid=fixture-viz]")).to_be_visible()
    page.keyboard.press("Escape")
    assert _viz_log(page).count("destroyed") == 1


def test_enlarge_moves_the_running_animation_to_a_full_page_overlay(make_page, page_url, fixture_only):
    page = make_page((1280, 800))
    load_page(page, f"{page_url}#gl=ema")
    page.locator("#help-pane .hp-enlarge").click()
    overlay = page.locator(".hp-overlay")
    expect(overlay).to_be_visible()
    box = overlay.bounding_box()
    assert (round(box["width"]), round(box["height"])) == (1280, 800)
    expect(overlay.locator("[data-testid=fixture-viz]")).to_be_visible()
    assert "destroyed" not in _viz_log(page)                  # moved, not remounted
    page.keyboard.press("Escape")                              # first Escape closes only the overlay
    expect(overlay).to_have_count(0)
    expect(page.locator("#help-pane")).to_be_visible()
    expect(page.locator("#help-pane [data-testid=fixture-viz]")).to_be_visible()
    assert "destroyed" not in _viz_log(page)
    assert len([x for x in _viz_log(page) if x.startswith("mounted:")]) == 1
    assert page.evaluate("document.activeElement.classList.contains('hp-enlarge')")
    page.keyboard.press("Escape")                              # second Escape closes the pane
    expect(page.locator("#help-pane")).to_be_hidden()


def test_enlarge_overlay_close_button(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, f"{page_url}#gl=ema")
    page.locator("#help-pane .hp-enlarge").click()
    page.locator(".hp-overlay .hp-overlay-close").click()
    expect(page.locator(".hp-overlay")).to_have_count(0)
    expect(page.locator("#help-pane [data-testid=fixture-viz]")).to_be_visible()


@pytest.mark.parametrize("term", ["adamw", "lora"])    # adamw: mount() throws; lora: module file is missing (404)
def test_failed_animation_shows_text_and_the_pane_keeps_working(make_page, page_url, entries, fixture_only, term):
    page = make_page()
    load_page(page, f"{page_url}#gl={term}")
    expect(page.locator("#help-pane .hp-plain")).to_have_text(plain_text(entries[term]["plain"]))
    expect(page.locator("#help-pane .hp-viz-stage")).to_contain_text("Animation unavailable.")
    expect(page.locator("[data-testid=half-built]")).to_have_count(0)      # partial DOM from a throwing mount is cleared
    expect(page.locator("#help-pane .hp-enlarge")).to_be_hidden()
    page.locator("#help-pane .hp-quiz-start").click()                       # pane still operable
    expect(page.locator("#help-pane .hp-progress")).to_have_text(f"Question 1 of {len(entries[term]['quiz'])}")
    page.keyboard.press("Escape")
    expect(page.locator("#help-pane")).to_be_hidden()
    expect(term_link(page, "momentum")).to_be_visible()                     # article untouched
    assert page.hp_errors == []


def test_leaving_an_entry_before_its_animation_loads_does_not_mount_it(make_page, page_url, fixture_only):
    page = make_page()
    page.route("**/viz/fixture-ok.js", lambda r: (page.wait_for_timeout(400), r.continue_()))
    load_page(page, f"{page_url}#gl=ema")
    page.locator("#help-pane .hp-close").click()
    page.wait_for_timeout(900)
    assert [x for x in _viz_log(page) if x.startswith("mounted:")] == []
    expect(page.locator("[data-testid=fixture-viz]")).to_have_count(0)


# --------------------------------------------------------------------------- quiz

def _answer(page, q, choice):
    """Select option `choice` on the current question, submit, return the feedback locator."""
    radios = page.locator("#help-pane input[type=radio]")
    expect(radios).to_have_count(5)
    submit = page.locator("#help-pane .hp-answer")
    expect(submit).to_be_disabled()                      # nothing chosen yet
    radios.nth(choice).check()
    expect(submit).to_be_enabled()
    submit.click()
    fb = page.locator("#help-pane .hp-feedback")
    expect(fb).to_be_visible()
    expect(radios).to_have_count(0)                      # the question was replaced by its feedback
    return fb


def _run_quiz(page, questions, wrong_on):
    """Answer every question (wrong where index in wrong_on); return the number answered correctly."""
    n, score = len(questions), 0
    for k, q in enumerate(questions):
        expect(page.locator("#help-pane .hp-progress")).to_have_text(f"Question {k + 1} of {n}")
        right = k not in wrong_on
        choice = q["answer"] if right else (q["answer"] + 1) % 5
        fb = _answer(page, q, choice)
        expect(fb.locator(".hp-why")).to_have_text(plain_text(q["why"]))
        live = page.locator("#help-pane [aria-live='polite']")
        if right:
            score += 1
            expect(fb).to_have_class(re.compile(r"\bhp-right\b"))
            expect(fb.locator(".hp-verdict")).to_have_text("Correct.")
            expect(fb.locator(".hp-wrong-note")).to_have_count(0)
            expect(live).to_contain_text("Correct.")
        else:
            expect(fb).to_have_class(re.compile(r"\bhp-wrong\b"))
            expect(fb.locator(".hp-verdict")).to_have_text("Not quite.")
            note = (q.get("wrong") or {}).get(str(choice))
            if note:
                expect(fb.locator(".hp-wrong-note")).to_have_text(plain_text(note))
            else:
                expect(fb.locator(".hp-wrong-note")).to_have_count(0)
            expect(fb.locator(".hp-right-answer")).to_contain_text(plain_text(q["options"][q["answer"]]))
            expect(live).to_contain_text("Not quite.")
        expect(live).to_contain_text(plain_text(q["why"])[:40])
        assert page.evaluate("document.activeElement.classList.contains('hp-feedback')")   # focus follows the swap
        page.locator("#help-pane .hp-next").click()
    return score


def test_quiz_full_run_with_score_try_again_and_back_to_entry(make_page, page_url, quiz_term, entries):
    questions = entries[quiz_term]["quiz"]
    n = len(questions)
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    expect(page.locator("#help-pane .hp-quiz-start")).to_contain_text(f"({n} question")
    page.locator("#help-pane .hp-quiz-start").click()
    assert page.evaluate("location.hash") == f"#gl={quiz_term}"
    score = _run_quiz(page, questions, wrong_on={0})            # first wrong, the rest right
    assert score == n - 1
    expect(page.locator("#help-pane .hp-score-line")).to_contain_text(f"{score} of {n}")
    page.locator("#help-pane .hp-again").click()                # Try again: back to question 1, score reset
    expect(page.locator("#help-pane .hp-progress")).to_have_text(f"Question 1 of {n}")
    score2 = _run_quiz(page, questions, wrong_on=set())
    expect(page.locator("#help-pane .hp-score-line")).to_contain_text(f"{score2} of {n}")
    assert score2 == n
    page.locator("#help-pane .hp-entry-back").click()           # Back to the entry
    expect(page.locator("#help-pane .hp-plain")).to_be_visible()
    expect(page.locator("#help-pane .hp-quiz-start")).to_be_visible()
    expect(page.locator("#help-pane .hp-back")).to_be_disabled()


def test_quiz_all_wrong_scores_zero(make_page, page_url, quiz_term, entries):
    questions = entries[quiz_term]["quiz"]
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    page.locator("#help-pane .hp-quiz-start").click()
    score = _run_quiz(page, questions, wrong_on=set(range(len(questions))))
    assert score == 0
    expect(page.locator("#help-pane .hp-score-line")).to_contain_text(f"0 of {len(questions)}")


def test_back_from_a_quiz_returns_to_its_entry(make_page, page_url, quiz_term, entries):
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    page.locator("#help-pane .hp-quiz-start").click()
    expect(page.locator("#help-pane .hp-progress")).to_be_visible()
    expect(page.locator("#help-pane .hp-back")).to_be_enabled()
    page.locator("#help-pane .hp-back").click()
    expect(page.locator("#help-pane .hp-plain")).to_have_text(plain_text(entries[quiz_term]["plain"]))
    expect(page.locator("#help-pane .hp-progress")).to_have_count(0)


def test_back_in_the_middle_of_a_quiz_returns_to_the_entry_and_a_new_quiz_starts_fresh(
        make_page, page_url, quiz_term, entries):
    questions = entries[quiz_term]["quiz"]
    page = make_page()
    open_via_click(page, page_url, quiz_term)
    page.locator("#help-pane .hp-quiz-start").click()
    _answer(page, questions[0], questions[0]["answer"])
    page.locator("#help-pane .hp-back").click()
    page.locator("#help-pane .hp-quiz-start").click()
    expect(page.locator("#help-pane .hp-progress")).to_have_text(f"Question 1 of {len(questions)}")


def test_a_term_inside_quiz_feedback_opens_its_entry_and_back_returns_to_the_feedback(
        make_page, page_url, fixture_only, entries):
    page = make_page()
    load_page(page, f"{page_url}#gl=ema")
    page.locator("#help-pane .hp-quiz-start").click()
    q = entries["ema"]["quiz"][0]
    _answer(page, q, q["answer"])
    page.locator('#help-pane .hp-feedback a.gl[data-term="momentum"]').click()
    expect(page.locator("#hp-title")).to_have_text("momentum")
    expect(page.locator("#help-pane .hp-plain")).to_be_visible()
    page.locator("#help-pane .hp-back").click()
    expect(page.locator("#hp-title")).to_have_text("EMA")
    expect(page.locator("#help-pane .hp-feedback")).to_be_visible()      # quiz state kept in the trail


def test_quiz_options_and_feedback_render_inline_markup(make_page, page_url, fixture_only):
    page = make_page()
    load_page(page, f"{page_url}#gl=momentum")
    page.locator("#help-pane .hp-quiz-start").click()
    for _ in range(2):                                    # questions 1 and 2: pick any answer and continue
        page.locator("#help-pane input[type=radio]").first.check()
        page.locator("#help-pane .hp-answer").click()
        page.locator("#help-pane .hp-next").click()
    expect(page.locator("#help-pane .hp-opt code")).to_have_count(5)   # question 3 options are <code>
    page.locator("#help-pane input[type=radio]").nth(2).check()
    page.locator("#help-pane .hp-answer").click()
    expect(page.locator("#help-pane .hp-verdict")).to_have_text("Correct.")


def test_last_question_button_leads_to_the_score(make_page, page_url, fixture_only, entries):
    page = make_page()
    load_page(page, f"{page_url}#gl=ema")
    page.locator("#help-pane .hp-quiz-start").click()
    qs = entries["ema"]["quiz"]
    for k, q in enumerate(qs):
        _answer(page, q, q["answer"])
        expect(page.locator("#help-pane .hp-next")).to_have_text(
            "See your score" if k == len(qs) - 1 else "Next question")
        page.locator("#help-pane .hp-next").click()
    expect(page.locator("#help-pane .hp-score-line")).to_contain_text("3 of 3")


# --------------------------------------------------------------------------- phone

SWIPE = """([sel, dist]) => {
  const t = document.querySelector(sel);
  const touch = (y) => new Touch({ identifier: 1, target: t, clientX: 60, clientY: y });
  const fire = (type, y, live) => t.dispatchEvent(new TouchEvent(type, {
    bubbles: true, cancelable: true,
    touches: live ? [touch(y)] : [], targetTouches: live ? [touch(y)] : [], changedTouches: [touch(y)] }));
  fire('touchstart', 300, true);
  fire('touchmove', 300 + dist / 2, true);
  fire('touchmove', 300 + dist, true);
  fire('touchend', 300 + dist, false);
}"""


def _no_scroll_lock(page):
    assert page.evaluate("getComputedStyle(document.body).overflow") != "hidden"
    assert page.evaluate("getComputedStyle(document.documentElement).overflow") != "hidden"
    assert page.evaluate("getComputedStyle(document.body).paddingBottom") == "0px"
    page.evaluate("window.scrollTo(0, 0)")
    page.mouse.move(100, 300)
    page.mouse.wheel(0, 300)
    page.wait_for_function("window.scrollY > 0")                      # the article scrolls again


@pytest.mark.parametrize("how", ["swipe", "button"])
def test_phone_bottom_sheet_opens_above_the_term_and_leaves_no_scroll_lock(
        make_page, page_url, quiz_term, how):
    page = make_page((390, 800), touch=True)
    load_page(page, page_url)
    link = term_link(page, quiz_term, "last")        # on the fixture page this one is below the fold
    link.tap()
    pane = page.locator("#help-pane")
    expect(pane).to_be_visible()
    page.wait_for_timeout(350)                                        # let the 0.18s rise animation settle
    box = pane.bounding_box()
    assert abs(box["width"] - 390) <= 1
    assert abs(box["height"] - 560) <= 6                              # about 70% of the screen
    assert abs(box["y"] + box["height"] - 800) <= 1                   # glued to the bottom
    assert page.evaluate("getComputedStyle(document.body).paddingRight") == "0px"
    page.wait_for_function(                                           # the term is not hidden under the sheet
        "sel => document.querySelectorAll(sel)[document.querySelectorAll(sel).length - 1]"
        ".getBoundingClientRect().bottom <= 800 * 0.3 + 2",
        arg=f'a.gl[data-term="{quiz_term}"]')
    if how == "swipe":
        page.evaluate(SWIPE, [".hp-head", 160])
    else:
        page.locator("#help-pane .hp-close").tap()
    expect(pane).to_be_hidden()
    assert page.evaluate("document.querySelector('#help-pane').style.transform") == ""
    _no_scroll_lock(page)
    assert link.evaluate("el => el === document.activeElement")


def test_short_swipe_does_not_dismiss_and_the_sheet_snaps_back(make_page, page_url, quiz_term):
    page = make_page((390, 800), touch=True)
    load_page(page, page_url)
    term_link(page, quiz_term).tap()
    expect(page.locator("#help-pane")).to_be_visible()
    page.evaluate(SWIPE, [".hp-head", 30])
    expect(page.locator("#help-pane")).to_be_visible()
    assert page.evaluate("document.querySelector('#help-pane').style.transform") == ""


def test_phone_shows_the_full_screen_wording_and_escape_still_works(make_page, page_url, fixture_only):
    page = make_page((390, 800), touch=True)
    load_page(page, f"{page_url}#gl=ema")
    expect(page.locator("#help-pane .hp-enlarge .hp-narrow")).to_be_visible()
    expect(page.locator("#help-pane .hp-enlarge .hp-wide")).to_be_hidden()
    page.locator("#help-pane .hp-enlarge").tap()
    box = page.locator(".hp-overlay").bounding_box()
    assert (round(box["width"]), round(box["height"])) == (390, 800)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator("#help-pane")).to_be_hidden()
    _no_scroll_lock(page)


def test_wide_layout_is_restored_after_the_phone_sheet_is_not_needed(make_page, page_url, quiz_term):
    page = make_page((1280, 800))
    open_via_click(page, page_url, quiz_term)
    assert page.evaluate("getComputedStyle(document.body).paddingBottom") == "0px"
    assert page.evaluate("getComputedStyle(document.querySelector('#help-pane .hp-grip')).display") == "none"

# --------------------------------------------------------------------------- privacy and network guards

STORAGE_GUARD = """
(() => {
  const touches = (window.__storageTouches = []);
  const block = (name) => ({ configurable: true, get() { touches.push(name); throw new DOMException('blocked ' + name, 'SecurityError'); } });
  for (const n of ['localStorage', 'sessionStorage', 'indexedDB']) {
    try { Object.defineProperty(window, n, block(n)); } catch (e) { touches.push('guard-failed:' + n); }
  }
  try {
    Object.defineProperty(Document.prototype, 'cookie', {
      configurable: true,
      get() { touches.push('cookie:get'); return ''; },
      set(v) { touches.push('cookie:set'); },
    });
  } catch (e) { touches.push('guard-failed:cookie'); }
})();
"""


def test_the_pane_never_touches_browser_storage(make_page, page_url, quiz_term, entries):
    page = make_page(init_script=STORAGE_GUARD)
    load_page(page, page_url)
    # prove the guard works (these reads are ours, then the log is cleared)
    page.evaluate("try { localStorage } catch (e) {} try { document.cookie } catch (e) {}")
    assert page.evaluate("window.__storageTouches.length") >= 2
    assert not any(t.startswith("guard-failed") for t in page.evaluate("window.__storageTouches"))
    page.evaluate("window.__storageTouches.length = 0")
    # a complete session: open, enlarge if any, quiz with a wrong and a right answer, history, close, reopen
    term_link(page, quiz_term).click()
    questions = entries[quiz_term]["quiz"]
    page.locator("#help-pane .hp-quiz-start").click()
    _answer(page, questions[0], (questions[0]["answer"] + 1) % 5)
    page.locator("#help-pane .hp-next").click()
    page.locator("#help-pane .hp-back").click()
    page.locator("#help-pane .hp-close").click()
    page.locator(".hp-reopen").click()
    page.keyboard.press("Escape")
    assert page.evaluate("window.__storageTouches") == []
    assert page.hp_errors == []


def test_the_only_requests_after_load_are_viz_modules(make_page, page_url, viz_term, quiz_term, entries):
    page = make_page()
    load_page(page, page_url)
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    for t in dict.fromkeys([viz_term, quiz_term]):
        term_link(page, t).click()
        page.wait_for_timeout(250)
        page.locator("#help-pane .hp-quiz-start").click()
        first = entries[t]["quiz"][0]
        _answer(page, first, first["answer"])
        page.locator("#help-pane .hp-close").click()
    for u in requests:
        parsed = urlparse(u)
        if parsed.scheme not in ("http", "https"):
            continue
        assert parsed.path.startswith("/help/viz/"), f"unexpected request after load: {u}"
        assert parsed.path.endswith(".js"), u


# --------------------------------------------------------------------------- keyboard-only path

def _tab_until(page, predicate_js, limit=60):
    for _ in range(limit):
        if page.evaluate(predicate_js):
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"never reached: {predicate_js}")


def test_keyboard_only_path_open_quiz_answer_close(make_page, page_url, quiz_term, entries):
    questions = entries[quiz_term]["quiz"]
    page = make_page()
    load_page(page, page_url)
    link = term_link(page, quiz_term)
    link.focus()
    page.keyboard.press("Enter")                                             # a term is a real, tab-reachable link
    expect(page.locator("#help-pane")).to_be_visible()
    assert page.evaluate("!!document.activeElement.closest('#help-pane')")   # focus moved into the pane
    _tab_until(page, "document.activeElement.classList.contains('hp-quiz-start')")
    page.keyboard.press("Enter")
    expect(page.locator("#help-pane .hp-progress")).to_be_visible()
    _tab_until(page, "document.activeElement.type === 'radio'")
    page.keyboard.press("Space")                                             # chooses the focused option
    _tab_until(page, "document.activeElement.classList.contains('hp-answer')")
    page.keyboard.press("Enter")
    expect(page.locator("#help-pane .hp-feedback")).to_be_visible()
    assert page.evaluate("document.activeElement.classList.contains('hp-feedback')")
    _tab_until(page, "document.activeElement.classList.contains('hp-next')")
    page.keyboard.press("Enter")
    if len(questions) > 1:
        expect(page.locator("#help-pane .hp-progress")).to_have_text(f"Question 2 of {len(questions)}")
    page.keyboard.press("Escape")
    expect(page.locator("#help-pane")).to_be_hidden()
    assert link.evaluate("el => el === document.activeElement")              # focus back on the term
