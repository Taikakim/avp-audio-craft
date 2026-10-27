# Owner: WINTERMUTE (created 2026-10-27)
"""Browser tests for the lora-rank module, written against the DOM contract in
docs/superpowers/plans/2026-10-27-lora-rank.md. Run:
/home/kim/Projects/mir/mir/bin/python -m pytest site/help/viz/tests/test_lora_rank_browser.py
"""
import json
import re
from urllib.parse import quote

from vizbrowser import open_page

ROOT = ".vz-rank"
RANKS = [16, 32, 64, 128, 256, 512, 1024, 1536]
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
MARKER = "svg.vz-energy circle.marker"


def url(base, rm=False, params=None):
    u = f"{base}/viz/dev.html?m=lora-rank"
    if rm:
        u += "&rm=1"
    if params is not None:
        u += "&p=" + quote(json.dumps(params))
    return u


def attr(page, name):
    return page.get_attribute(ROOT, name)


def rank(page):
    return int(attr(page, "data-rank"))


def marker_e(page):
    return float(page.get_attribute(MARKER, "data-e"))


def set_slider(page, index):
    page.evaluate(
        """(i) => { const s = document.querySelector('#vz-rank-r'); s.value = String(i);
            s.dispatchEvent(new Event('input', {bubbles: true}));
            s.dispatchEvent(new Event('change', {bubbles: true})); }""",
        index,
    )


def dora_button(page):
    return page.locator(f"{ROOT} button:text-is('DoRA')")


def dials_visible(page):
    """Count of g.dial whose computed visibility is visible and that have no hidden-attribute ancestor."""
    return page.evaluate(
        """() => [...document.querySelectorAll('g.dials g.dial')].filter(d => {
            if (getComputedStyle(d).visibility === 'hidden') return false;
            for (let n = d; n && n !== document.body; n = n.parentElement)
                if (n.hasAttribute('hidden') || n.getAttribute('visibility') === 'hidden') return false;
            return true; }).length"""
    )


def cell_values(page, kind):
    return page.evaluate(
        """(k) => [...document.querySelectorAll('svg.vz-heat.' + k + ' rect.cell')].map(c => c.getAttribute('data-v'))""",
        kind,
    )


def test_mounts_clean_with_defaults_and_note(browser, base_url):
    ctx, page, errors = open_page(browser, url(base_url))
    assert rank(page) == 128
    assert attr(page, "data-dora") == "off"
    assert page.locator("text=What's real here").count() >= 1
    page.wait_for_timeout(300)
    assert errors == []
    ctx.close()


def test_default_readouts_at_rank_128(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    params = page.inner_text("#vz-rank-params")
    assert "393,216" in params or "393216" in params
    energy = page.inner_text("#vz-rank-energy")
    assert "25.7" in energy or "26" in energy
    assert "measured" in page.inner_text("#vz-rank-kind")
    ctx.close()


def test_slider_interpolated_then_full_matrix(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    set_slider(page, 1)
    page.wait_for_function("parseInt(document.querySelector('.vz-rank').dataset.rank) === 32", timeout=3000)
    assert "interpolated between r16 and r64" in page.inner_text("#vz-rank-kind")
    page.wait_for_function(
        """() => { const e = parseFloat(document.querySelector('svg.vz-energy circle.marker').dataset.e);
            return e > 0.045 && e < 0.148; }""",
        timeout=3000,
    )
    assert 0.045 < marker_e(page) < 0.148
    set_slider(page, 7)
    page.wait_for_function("parseInt(document.querySelector('.vz-rank').dataset.rank) === 1536", timeout=3000)
    assert "the full matrix" in page.inner_text("#vz-rank-kind")
    assert int(attr(page, "data-toyrank")) == 12
    page.wait_for_function(
        """() => { const cs = [...document.querySelectorAll('svg.vz-heat.missing rect.cell')];
            return cs.length === 144 && cs.every(c => c.hasAttribute('data-v') && Math.abs(parseFloat(c.getAttribute('data-v'))) < 1e-9); }""",
        timeout=5000,
    )
    ctx.close()


def test_element_counts(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    assert page.locator("svg.vz-energy circle.measured").count() == 5
    assert page.locator("svg.vz-energy circle.full").count() == 1
    assert page.locator("svg.vz-energy path.interp").count() == 1
    for kind in ("full", "kept", "missing"):
        assert page.locator(f"svg.vz-heat.{kind} rect.cell").count() == 144, kind
    ctx.close()


def test_kept_plus_missing_equals_full_at_rank_512(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, params={"rank": 512}))
    assert int(attr(page, "data-toyrank")) == 4
    page.wait_for_function(
        """() => { const q = (k) => [...document.querySelectorAll('svg.vz-heat.' + k + ' rect.cell')].map(c => c.getAttribute('data-v'));
            const f = q('full'), k = q('kept'), m = q('missing');
            if (f.length !== 144 || k.length !== 144 || m.length !== 144) return false;
            if ([...f, ...k, ...m].some(v => v === null)) return false;
            return f.every((v, i) => Math.abs(parseFloat(k[i]) + parseFloat(m[i]) - parseFloat(v)) < 1e-9); }""",
        timeout=5000,
    )
    full, kept, missing = (cell_values(page, k) for k in ("full", "kept", "missing"))
    for i in (0, 13, 77, 130, 143):
        assert abs(float(kept[i]) + float(missing[i]) - float(full[i])) < 1e-9, i
    # the kept part must be a real partial change, not all zeros
    assert any(abs(float(v)) > 1e-6 for v in kept)
    ctx.close()


def test_dora_toggles_dials_and_row_readout(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    btn = dora_button(page)
    assert btn.get_attribute("aria-pressed") == "false"
    assert page.locator("g.dials g.dial").count() == 12
    assert dials_visible(page) == 0
    btn.click()
    assert btn.get_attribute("aria-pressed") == "true"
    assert attr(page, "data-dora") == "on"
    assert dials_visible(page) == 12
    page.wait_for_function(
        "document.querySelector('#vz-rank-rows').textContent.includes('match exactly')", timeout=3000
    )
    btn.click()
    assert btn.get_attribute("aria-pressed") == "false"
    assert attr(page, "data-dora") == "off"
    assert dials_visible(page) == 0
    assert PCT.search(page.inner_text("#vz-rank-rows"))
    ctx.close()


def test_keyboard_slider_and_dora_button(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    active_id = "document.activeElement && document.activeElement.id"
    for _ in range(25):
        page.keyboard.press("Tab")
        if page.evaluate(active_id) == "vz-rank-r":
            break
    else:
        raise AssertionError("Tab never reached #vz-rank-r")
    assert rank(page) == 128
    page.keyboard.press("ArrowRight")
    page.wait_for_function("parseInt(document.querySelector('.vz-rank').dataset.rank) === 256", timeout=3000)
    for _ in range(25):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement ? document.activeElement.textContent.trim() : ''") == "DoRA":
            break
    else:
        raise AssertionError("Tab never reached the DoRA button")
    page.keyboard.press("Space")
    assert dora_button(page).get_attribute("aria-pressed") == "true"
    assert attr(page, "data-dora") == "on"
    ctx.close()


def test_reduced_motion_jumps_to_final_marker(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    set_slider(page, 5)
    assert rank(page) == 512
    assert abs(marker_e(page) - 0.65) < 1e-9
    set_slider(page, 0)
    assert abs(marker_e(page) - 0.045) < 1e-9
    ctx.close()


def test_destroy_leaves_no_frame_and_no_root(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    page.wait_for_timeout(200)
    assert page.evaluate("(() => { window.__viz.destroy(); return window.__rafOutstanding.size; })()") == 0
    assert page.locator(ROOT).count() == 0
    ctx.close()


def test_no_horizontal_overflow_at_360(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url), viewport={"width": 360, "height": 740})
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    ctx.close()


def test_params_set_start_state_and_invalid_falls_back(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"rank": 1024, "dora": True}))
    assert rank(page) == 1024
    assert attr(page, "data-dora") == "on"
    assert dora_button(page).get_attribute("aria-pressed") == "true"
    ctx.close()
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"rank": 100, "dora": "yes"}))
    assert rank(page) == 128
    assert attr(page, "data-dora") == "off"
    ctx.close()


def test_note_states_measured_numbers_and_interpolation(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    text = page.inner_text(ROOT)
    assert "89.5%" in text
    assert "interpolated" in text.lower()
    ctx.close()


# KUANG 2026-10-27: the slider repeated under the three panels, and the June rank-ladder clips (enlarged view only)
def test_bottom_slider_mirrors_the_top(browser, base_url):
    ctx, page, errors = open_page(browser, url(base_url))
    assert page.locator(f"{ROOT} input[type=range]").count() == 2
    page.evaluate(
        """() => { const s = document.querySelector('#vz-rank-r2'); s.value = '7';
            s.dispatchEvent(new Event('input', {bubbles: true})); }"""
    )
    page.wait_for_function("parseInt(document.querySelector('.vz-rank').dataset.rank) === 1536", timeout=3000)
    assert page.eval_on_selector("#vz-rank-r", "s => s.value") == "7"
    assert page.inner_text("#vz-rank-r2-out") == "1536"
    set_slider(page, 1)
    page.wait_for_function("parseInt(document.querySelector('.vz-rank').dataset.rank) === 32", timeout=3000)
    assert page.eval_on_selector("#vz-rank-r2", "s => s.value") == "1"
    assert errors == []
    ctx.close()


def test_rank_clips_show_only_in_the_enlarged_view(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    assert page.eval_on_selector(".vz-rank .vz-clips", "c => getComputedStyle(c).display") == "none"
    page.evaluate("() => document.getElementById('root').classList.add('hp-viz-big')")   # what the pane's Enlarge adds
    assert page.eval_on_selector(".vz-rank .vz-clips", "c => getComputedStyle(c).display") == "block"
    srcs = page.eval_on_selector_all(".vz-rank .vz-clips audio", "as => as.map(a => a.getAttribute('src'))")
    assert len(srcs) == 12
    assert all("/evals/riffer/clips_dora_aac/" in s and s.endswith("_seed1234.m4a") for s in srcs)
    assert page.eval_on_selector_all(".vz-rank .vz-clips audio", "as => as.every(a => a.preload === 'none')")
    ctx.close()
