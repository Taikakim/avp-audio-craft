# Owner: WINTERMUTE (created 2026-10-26)
"""Browser tests for the batch-noise module, written against the DOM contract in
docs/superpowers/plans/2026-10-26-batch-noise.md. Run:
/home/kim/Projects/mir/mir/bin/python -m pytest site/help/viz/tests/test_batch_noise_browser.py
"""
import json
import re
from urllib.parse import quote

from conftest import open_page

ROOT = ".vz-noise"
NUM = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", re.I)


def url(base, rm=False, params=None):
    u = f"{base}/viz/dev.html?m=batch-noise"
    if rm:
        u += "&rm=1"
    if params is not None:
        u += "&p=" + quote(json.dumps(params))
    return u


def first_number(text):
    m = NUM.search(text or "")
    assert m, f"no number in {text!r}"
    return float(m.group(0))


def set_slider(page, index):
    """Set the range input to a stop index; dispatch both input and change (the contract names neither)."""
    page.evaluate(
        """(i) => { const s = document.querySelector('#vz-noise-batch'); s.value = String(i);
            s.dispatchEvent(new Event('input', {bubbles: true}));
            s.dispatchEvent(new Event('change', {bubbles: true})); }""",
        index,
    )


def attr(page, name):
    return page.get_attribute(ROOT, name)


def snr(page):
    return first_number(page.inner_text("#vz-noise-snr"))


def test_mounts_clean_with_cloud_and_note(browser, base_url):
    ctx, page, errors = open_page(browser, url(base_url))
    assert page.locator("svg.vz-valley line.cloud").count() == 24
    assert page.locator("svg.vz-valley line.true-grad").count() == 1
    assert page.locator("text=What's real here").count() >= 1
    page.wait_for_timeout(300)
    assert errors == []
    ctx.close()


def test_step_advances_within_500ms(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    s0 = int(attr(page, "data-step"))
    page.wait_for_function(
        "s0 => +document.querySelector('.vz-noise').dataset.step > s0", arg=s0, timeout=500
    )
    ctx.close()


def test_slider_drives_batch_snr_and_tag(browser, base_url):
    # Reduced motion: the ball stays at the start point, so both SNR readings are at the same position.
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    set_slider(page, 2)
    page.wait_for_function("document.querySelector('.vz-noise').dataset.batch === '4'")
    snr4 = snr(page)
    tag4 = page.inner_text("#vz-noise-tag").lower()
    set_slider(page, 6)
    page.wait_for_function("document.querySelector('.vz-noise').dataset.batch === '64'")
    snr64 = snr(page)
    tag64 = page.inner_text("#vz-noise-tag").lower()
    assert abs(snr64 / snr4 - 4.0) <= 0.4          # sqrt(64/4) = 4, 10 %
    assert "measured" in tag64
    assert "extrapolated" in tag4 and "measured" not in tag4
    assert page.get_attribute("#vz-noise-batch", "aria-valuetext") == "batch 64"
    assert first_number(page.inner_text("#vz-noise-batch-out")) == 64
    ctx.close()


def test_momentum_toggle_and_msnr(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    btn = page.locator("button:has-text('Momentum')")
    assert btn.get_attribute("aria-pressed") == "false"
    assert attr(page, "data-momentum") == "off"
    off_text = page.inner_text("#vz-noise-msnr").strip()
    assert not NUM.search(off_text) or not page.locator("#vz-noise-msnr").is_visible()
    btn.click()
    assert btn.get_attribute("aria-pressed") == "true"
    assert attr(page, "data-momentum") == "on"
    assert first_number(page.inner_text("#vz-noise-msnr")) > snr(page)   # averaging only helps
    btn.click()
    assert btn.get_attribute("aria-pressed") == "false"
    assert attr(page, "data-momentum") == "off"
    assert not NUM.search(page.inner_text("#vz-noise-msnr")) or not page.locator("#vz-noise-msnr").is_visible()
    ctx.close()


def test_stage_buttons_and_snr_ordering(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"batch": 64}))
    early = page.locator("button:has-text('Early in training')")
    late = page.locator("button:has-text('Late in training')")
    late.click()
    assert attr(page, "data-stage") == "late"
    assert late.get_attribute("aria-pressed") == "true" and early.get_attribute("aria-pressed") == "false"
    snr_late = snr(page)
    early.click()
    assert attr(page, "data-stage") == "early"
    assert early.get_attribute("aria-pressed") == "true" and late.get_attribute("aria-pressed") == "false"
    assert snr(page) > snr_late
    ctx.close()


def test_reduced_motion_holds_until_step(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    s0 = int(attr(page, "data-step"))
    assert s0 == 0
    page.wait_for_timeout(500)
    assert int(attr(page, "data-step")) == s0
    page.click("button:has-text('Step')")
    assert int(attr(page, "data-step")) > s0
    ctx.close()


def test_destroy_leaves_no_frame_and_no_root(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    page.wait_for_timeout(200)
    assert page.evaluate("window.__rafOutstanding.size") >= 1
    assert page.evaluate("(() => { window.__viz.destroy(); return window.__rafOutstanding.size; })()") == 0
    assert page.locator(ROOT).count() == 0
    ctx.close()


def test_no_horizontal_overflow_at_360(browser, base_url):
    ctx, page, _ = open_page(
        browser, url(base_url), viewport={"width": 360, "height": 740}
    )
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    ctx.close()


def test_keyboard_reaches_slider_and_arrow_steps_batch(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    assert attr(page, "data-batch") == "8"
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.id") == "vz-noise-batch":
            break
    else:
        raise AssertionError("Tab never reached #vz-noise-batch")
    page.keyboard.press("ArrowRight")
    page.wait_for_function("document.querySelector('.vz-noise').dataset.batch === '16'")
    ctx.close()


def test_params_set_start_state_and_invalid_falls_back(browser, base_url):
    ctx, page, _ = open_page(
        browser, url(base_url, rm=True, params={"batch": 64, "momentum": True, "stage": "early"})
    )
    assert attr(page, "data-batch") == "64"
    assert attr(page, "data-momentum") == "on"
    assert attr(page, "data-stage") == "early"
    assert page.locator("button:has-text('Momentum')").get_attribute("aria-pressed") == "true"
    ctx.close()
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"batch": 5}))
    assert attr(page, "data-batch") == "8"
    assert attr(page, "data-momentum") == "off" and attr(page, "data-stage") == "late"
    ctx.close()
