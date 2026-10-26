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
