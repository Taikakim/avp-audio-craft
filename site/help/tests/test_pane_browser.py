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
