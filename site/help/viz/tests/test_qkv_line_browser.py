# Owner: WINTERMUTE (created 2026-10-27)
"""Browser tests for the qkv-line module, written against the DOM contract in
docs/superpowers/plans/2026-10-27-qkv-line.md. Run:
/home/kim/Projects/mir/mir/bin/python -m pytest site/help/viz/tests/test_qkv_line_browser.py
"""
import json
import re
from urllib.parse import quote

from vizbrowser import open_page

ROOT = ".vz-qkv"
NUM = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", re.I)
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
KSCALES = [0.01, 0.03, 0.1, 0.3, 1, 3, 10]
SCENE_MAKE = "button:has-text('Making Q, K, V')"
SCENE_ORTH = "button:has-text('Orthogonalising the step')"


def url(base, rm=False, params=None):
    u = f"{base}/viz/dev.html?m=qkv-line"
    if rm:
        u += "&rm=1"
    if params is not None:
        u += "&p=" + quote(json.dumps(params))
    return u


def first_number(text):
    m = NUM.search(text or "")
    assert m, f"no number in {text!r}"
    return float(m.group(0))


def attr(page, name):
    return page.get_attribute(ROOT, name)


def inputs(page):
    return int(attr(page, "data-inputs"))


def set_slider(page, index):
    page.evaluate(
        """(i) => { const s = document.querySelector('#vz-qkv-kscale'); s.value = String(i);
            s.dispatchEvent(new Event('input', {bubbles: true}));
            s.dispatchEvent(new Event('change', {bubbles: true})); }""",
        index,
    )


def bar_size(page, block, how):
    return page.get_attribute(f"rect.bar[data-block='{block}'][data-how='{how}']", "data-size")


def test_mounts_clean_in_scene_one(browser, base_url):
    ctx, page, errors = open_page(browser, url(base_url))
    assert attr(page, "data-scene") == "make"
    assert attr(page, "data-mode") == "fused"
    assert page.locator(".vz-qkv-make").is_visible()
    assert page.locator("svg.vz-line g.machine").count() == 1
    assert page.locator("text=What's real here").count() >= 1
    page.wait_for_timeout(300)
    assert errors == []
    ctx.close()


def test_inputs_grow_while_scene_one_plays(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    assert inputs(page) >= 1
    page.wait_for_function(
        "+document.querySelector('.vz-qkv').dataset.inputs > 1", timeout=3000
    )
    ctx.close()


def test_three_machines_flips_mode_restarts_and_diff_is_tiny(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    fused = page.locator("button:has-text('One fused machine')")
    three = page.locator("button:has-text('Three machines')")
    assert fused.get_attribute("aria-pressed") == "true"
    assert three.get_attribute("aria-pressed") == "false"
    assert first_number(page.inner_text("#vz-qkv-diff")) < 1e-9
    page.wait_for_function(
        "+document.querySelector('.vz-qkv').dataset.inputs > 2", timeout=5000
    )
    # read data-inputs synchronously in the same task as the click, before any frame can advance the new line
    n = page.evaluate(
        """() => { const b = [...document.querySelectorAll('.vz-qkv button')].find(x => x.textContent.trim() === 'Three machines');
            b.click(); return +document.querySelector('.vz-qkv').dataset.inputs; }"""
    )
    assert n == 1
    assert three.get_attribute("aria-pressed") == "true"
    assert fused.get_attribute("aria-pressed") == "false"
    assert attr(page, "data-mode") == "separate"
    assert page.locator("svg.vz-line g.machine").count() == 3
    assert first_number(page.inner_text("#vz-qkv-diff")) < 1e-9
    ctx.close()


def test_scene_switch_shows_orth_and_hides_make(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    page.click(SCENE_ORTH)
    assert attr(page, "data-scene") == "orth"
    assert page.locator(".vz-qkv-orth").is_visible()
    assert page.locator(".vz-qkv-orth").get_attribute("hidden") is None
    assert page.locator(".vz-qkv-make").get_attribute("hidden") is not None
    assert not page.locator(".vz-qkv-make").is_visible()
    assert page.locator("button:has-text('Orthogonalising the step')").get_attribute("aria-pressed") == "true"
    page.click(SCENE_MAKE)
    assert attr(page, "data-scene") == "make"
    assert page.locator(".vz-qkv-orth").get_attribute("hidden") is not None
    ctx.close()


def test_slider_squeezes_stacked_q_but_not_separate_q(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"scene": "orth"}))
    assert page.locator("rect.bar").count() == 6
    set_slider(page, 4)
    page.wait_for_function("+document.querySelector('.vz-qkv').dataset.kscale === 1")
    fused_q1 = float(bar_size(page, "q", "fused"))
    sep_q1 = bar_size(page, "q", "separate")
    set_slider(page, 6)
    page.wait_for_function("+document.querySelector('.vz-qkv').dataset.kscale === 10")
    assert attr(page, "data-kscale") == "10"
    assert float(bar_size(page, "q", "fused")) < fused_q1
    assert bar_size(page, "q", "separate") == sep_q1
    m = PCT.search(page.inner_text("#vz-qkv-change"))
    assert m, page.inner_text("#vz-qkv-change")
    assert float(m.group(1)) < 100
    assert first_number(page.inner_text("#vz-qkv-kscale-out")) == 10
    assert page.get_attribute("#vz-qkv-kscale", "aria-valuetext").startswith("key gradient")
    ctx.close()


def test_reduced_motion_holds_until_step(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    assert inputs(page) == 1
    page.wait_for_timeout(1000)
    assert inputs(page) == 1
    page.click("button:text-is('Step')")
    page.wait_for_function(
        "+document.querySelector('.vz-qkv').dataset.inputs > 1", timeout=2000
    )
    ctx.close()


def test_destroy_leaves_no_frame_and_no_root(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    page.wait_for_timeout(200)
    assert page.evaluate("window.__rafOutstanding.size") >= 1
    assert page.evaluate("(() => { window.__viz.destroy(); return window.__rafOutstanding.size; })()") == 0
    assert page.locator(ROOT).count() == 0
    ctx.close()


def test_no_horizontal_overflow_at_360_in_both_scenes(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url), viewport={"width": 360, "height": 740})
    page.wait_for_timeout(300)
    check = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    assert page.evaluate(check)
    page.click(SCENE_ORTH)
    page.wait_for_timeout(500)
    assert page.evaluate(check)
    ctx.close()


def test_keyboard_reaches_scene_buttons_and_slider_arrow(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, params={"scene": "orth"}))
    probe = "document.activeElement ? document.activeElement.textContent.trim() : ''"
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate(probe) in ("Making Q, K, V", "Orthogonalising the step"):
            break
    else:
        raise AssertionError("Tab never reached a scene button")
    assert attr(page, "data-kscale") == "1"
    for _ in range(20):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.id") == "vz-qkv-kscale":
            break
    else:
        raise AssertionError("Tab never reached #vz-qkv-kscale")
    page.keyboard.press("ArrowLeft")
    page.wait_for_function("+document.querySelector('.vz-qkv').dataset.kscale === 0.3")
    ctx.close()


def test_params_set_start_state_and_invalid_falls_back(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"scene": "orth", "kscale": 0.1}))
    assert attr(page, "data-scene") == "orth"
    assert float(attr(page, "data-kscale")) == 0.1
    assert page.locator(".vz-qkv-orth").is_visible()
    ctx.close()
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"kscale": 5, "mode": "x"}))
    assert float(attr(page, "data-kscale")) == 1
    assert attr(page, "data-mode") == "fused"
    assert attr(page, "data-scene") == "make"
    ctx.close()


def test_note_keeps_the_honesty_lines(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    text = page.inner_text(ROOT).lower()
    assert "4 × 4" in text or "4 wide" in text
    assert "not measured" in text
    ctx.close()
