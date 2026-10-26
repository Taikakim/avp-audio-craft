# Owner: WINTERMUTE (created 2026-10-26)
"""Browser smoke test for the step-size module. Run:
/home/kim/Projects/mir/mir/bin/python -m pytest /home/kim/Projects/SAO/site/help/viz/tests/test_viz_browser.py
"""
# Last edited: WINTERMUTE 2026-10-26 -- shared fixtures moved to conftest.py; review fixes: open_page imported from vizbrowser.py
import pytest  # noqa: F401
from vizbrowser import open_page


def test_step_size_mounts_and_animates(browser, base_url):
    ctx, page, errors = open_page(browser, f"{base_url}/viz/dev.html?m=step-size")
    assert page.locator("svg line.wire").count() == 32              # 16 wires x two networks
    assert page.locator("svg.vz-chart polyline").count() == 2
    assert page.locator("text=What's real here").count() >= 1
    s0 = int(page.get_attribute(".vz-step", "data-step"))
    page.wait_for_timeout(400)
    assert int(page.get_attribute(".vz-step", "data-step")) > s0
    assert errors == []
    ctx.close()


def test_scenario_and_precision_controls(browser, base_url):
    ctx, page, _ = open_page(browser, f"{base_url}/viz/dev.html?m=step-size")
    page.click("button:has-text('Gradient drops 100x')")
    assert page.get_attribute(".vz-step", "data-scenario") == "drop"
    page.wait_for_function("+document.querySelector('.vz-step').dataset.step > 10")
    page.select_option("#vz-step-prec", "fp32")
    assert page.locator("line.wire[data-lost='1']").count() == 0
    page.select_option("#vz-step-prec", "fp8e4m3")
    assert page.locator("line.wire[data-lost='1']").count() == 32   # a step of ~6e-5 on a weight of ~0.05 is rounded away
    ctx.close()


def test_destroy_leaves_no_animation_frame(browser, base_url):
    ctx, page, _ = open_page(browser, f"{base_url}/viz/dev.html?m=step-size")
    page.wait_for_timeout(200)
    assert page.evaluate("window.__rafOutstanding.size") >= 1
    # Measured in the same task as destroy(): a frame left pending would still be outstanding here
    # (it would fire harmlessly a few ms later, so waiting first would hide the leak).
    assert page.evaluate("(() => { window.__viz.destroy(); return window.__rafOutstanding.size; })()") == 0
    assert page.locator(".vz-step").count() == 0
    ctx.close()


def test_reduced_motion_starts_still_with_step_button(browser, base_url):
    ctx, page, _ = open_page(browser, f"{base_url}/viz/dev.html?m=step-size", reduced_motion="reduce")
    s0 = int(page.get_attribute(".vz-step", "data-step"))
    page.wait_for_timeout(300)
    assert int(page.get_attribute(".vz-step", "data-step")) == s0
    assert page.evaluate("window.__rafOutstanding.size") == 0
    page.click("button:has-text('Step')")
    assert int(page.get_attribute(".vz-step", "data-step")) > s0
    ctx.close()


def test_reduced_motion_scenario_change_and_replay_draw_a_first_frame(browser, base_url):
    ctx, page, _ = open_page(browser, f"{base_url}/viz/dev.html?m=step-size", reduced_motion="reduce")
    page.click("button:has-text('Step')")
    page.click("button:has-text('Step')")
    assert int(page.get_attribute(".vz-step", "data-step")) > 1
    page.click("button:has-text('Gradient drops 100x')")
    assert page.get_attribute(".vz-step", "data-scenario") == "drop"
    assert int(page.get_attribute(".vz-step", "data-step")) == 1          # a fresh run, first frame drawn
    assert page.locator("line.wire").first.get_attribute("stroke-width") != "0"
    page.click("button:has-text('Step')")
    page.click("button:has-text('Replay')")
    assert int(page.get_attribute(".vz-step", "data-step")) == 1
    ctx.close()


def test_legend_uses_swatches_not_colour_names_and_muon_hue_differs(browser, base_url):
    ctx, page, _ = open_page(browser, f"{base_url}/viz/dev.html?m=step-size")
    text = page.inner_text(".vz-step").lower()
    for word in ("blue", "green", "teal", "purple", "violet", "red"):
        assert word not in text.split(), word
    assert page.locator(".vz-legend .vz-sw").count() == 2
    sw = page.eval_on_selector_all(".vz-legend .vz-sw", "n => n.map(e => getComputedStyle(e).backgroundColor)")
    assert sw[0] != sw[1]
    ctx.close()
