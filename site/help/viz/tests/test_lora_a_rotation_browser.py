# Owner: WINTERMUTE (created 2026-10-27)
"""Browser tests for the lora-a-rotation module, written against the DOM contract in
docs/superpowers/plans/2026-10-27-lora-a-rotation.md. Run:
/home/kim/Projects/mir/mir/bin/python -m pytest site/help/viz/tests/test_lora_a_rotation_browser.py
"""
import json
import re
from urllib.parse import quote

from vizbrowser import open_page

ROOT = ".vz-rot"
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
B1 = "button:text-is('×1')"
B20 = "button:text-is('×20')"
DONE = "parseInt(document.querySelector('.vz-rot').dataset.step, 10) === 300"


def url(base, rm=False, params=None):
    u = f"{base}/viz/dev.html?m=lora-a-rotation"
    if rm:
        u += "&rm=1"
    if params is not None:
        u += "&p=" + quote(json.dumps(params))
    return u


def attr(page, name):
    return page.get_attribute(ROOT, name)


def step(page):
    return int(attr(page, "data-step"))


def angle(page):
    return float(page.get_attribute("svg.vz-rot-a line.arrow", "data-angle"))


def overlap_pct(page):
    text = page.inner_text("#vz-rot-overlap")
    m = PCT.search(text)
    assert m, f"no percentage in {text!r}"
    return float(m.group(1))


def wait_done(page, timeout=10000):
    page.wait_for_function(DONE, timeout=timeout)


def test_mounts_clean_with_both_panels_and_note(browser, base_url):
    ctx, page, errors = open_page(browser, url(base_url))
    assert attr(page, "data-mult") == "1"
    assert page.locator("svg.vz-rot-a").count() == 1
    assert page.locator("svg.vz-rot-b").count() == 1
    for cls in ("svg.vz-rot-a", "svg.vz-rot-b"):
        assert page.locator(f"{cls} line.arrow").count() == 1
        assert page.locator(f"{cls} line.target").count() == 1
        assert page.locator(f"{cls} polyline.trail").count() == 1
    assert page.locator("svg.vz-chart").count() >= 1
    assert page.locator("text=What's real here").count() >= 1
    page.wait_for_timeout(300)
    assert errors == []
    ctx.close()


def test_steps_grow_and_run_finishes(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    page.wait_for_function(
        "parseInt(document.querySelector('.vz-rot').dataset.step, 10) > 0", timeout=1000
    )
    wait_done(page)
    assert step(page) == 300
    ctx.close()


def test_x1_ends_with_a_barely_turned(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    wait_done(page)
    assert angle(page) < 10
    assert overlap_pct(page) > 99
    ctx.close()


def test_x20_restarts_and_a_rotates(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    btn1 = page.locator(B1)
    btn20 = page.locator(B20)
    assert btn1.get_attribute("aria-pressed") == "true"
    assert btn20.get_attribute("aria-pressed") == "false"
    wait_done(page)
    # read data-step synchronously in the same task as the click, before any frame can advance the new run
    n = page.evaluate(
        """() => { const b = [...document.querySelectorAll('.vz-rot button')].find(x => x.textContent.trim() === '×20');
            b.click(); return parseInt(document.querySelector('.vz-rot').dataset.step, 10); }"""
    )
    assert n < 50
    assert btn20.get_attribute("aria-pressed") == "true"
    assert btn1.get_attribute("aria-pressed") == "false"
    assert attr(page, "data-mult") == "20"
    wait_done(page)
    assert abs(angle(page) - 70) <= 2
    assert overlap_pct(page) < 80
    ctx.close()


def test_replay_restarts(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    wait_done(page)
    n = page.evaluate(
        """() => { const b = [...document.querySelectorAll('.vz-rot button')].find(x => x.textContent.trim() === 'Replay');
            b.click(); return parseInt(document.querySelector('.vz-rot').dataset.step, 10); }"""
    )
    assert n < 50
    wait_done(page)
    ctx.close()


def test_reduced_motion_holds_until_step(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    assert step(page) == 0
    page.wait_for_timeout(1000)
    assert step(page) == 0
    page.click("button:text-is('Step')")
    page.wait_for_function(
        "parseInt(document.querySelector('.vz-rot').dataset.step, 10) === 25", timeout=2000
    )
    assert step(page) == 25
    ctx.close()


def test_destroy_leaves_no_frame_and_no_root(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    page.wait_for_function("window.__rafOutstanding.size >= 1", timeout=2000)
    assert page.evaluate("(() => { window.__viz.destroy(); return window.__rafOutstanding.size; })()") == 0
    assert page.locator(ROOT).count() == 0
    ctx.close()


def test_no_horizontal_overflow_at_360(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url), viewport={"width": 360, "height": 740})
    check = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    page.wait_for_timeout(300)
    assert page.evaluate(check)
    wait_done(page)
    assert page.evaluate(check)
    ctx.close()


def test_keyboard_reaches_x20_and_enter_sets_it(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    probe = "document.activeElement ? document.activeElement.textContent.trim() : ''"
    for _ in range(15):
        page.keyboard.press("Tab")
        if page.evaluate(probe) == "×20":
            break
    else:
        raise AssertionError("Tab never reached the x20 button")
    page.keyboard.press("Enter")
    page.wait_for_function(
        "document.querySelector('.vz-rot').dataset.mult === '20'", timeout=2000
    )
    assert attr(page, "data-mult") == "20"
    ctx.close()


def test_params_set_mult_and_invalid_falls_back(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"mult": 20}))
    assert attr(page, "data-mult") == "20"
    assert page.locator(B20).get_attribute("aria-pressed") == "true"
    ctx.close()
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"mult": 5}))
    assert attr(page, "data-mult") == "1"
    assert page.locator(B1).get_attribute("aria-pressed") == "true"
    ctx.close()


def test_note_keeps_the_honesty_lines(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    text = page.inner_text(ROOT)
    assert "99.2%" in text
    assert "35%" in text
    assert "not clean" in text
    ctx.close()
