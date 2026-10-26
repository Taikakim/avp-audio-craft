# Owner: WINTERMUTE (created 2026-10-26)
"""Browser smoke test for the step-size module. Run:
/home/kim/Projects/mir/mir/bin/python -m pytest /home/kim/Projects/SAO/site/help/viz/tests/test_viz_browser.py
"""
import functools
import glob
import http.server
import os
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

HELP_ROOT = Path(__file__).resolve().parents[2]          # .../site/help

RAF_SPY = """
(() => {
  const out = new Set();
  const req = window.requestAnimationFrame.bind(window);
  const cancel = window.cancelAnimationFrame.bind(window);
  window.__rafOutstanding = out;
  window.requestAnimationFrame = (cb) => { const id = req((t) => { out.delete(id); cb(t); }); out.add(id); return id; };
  window.cancelAnimationFrame = (id) => { out.delete(id); cancel(id); };
})();
"""


@pytest.fixture(scope="module")
def base_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HELP_ROOT))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def chromium_path():
    """The mir venv's Playwright expects a Chromium build that is not installed; use the newest one that is."""
    found = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
    return found[-1] if found else None


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chromium_path())
        yield b
        b.close()


def open_page(browser, url, **ctx):
    context = browser.new_context(**ctx)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.add_init_script(RAF_SPY)
    page.goto(url)
    page.wait_for_selector("body[data-mounted='1']")
    return context, page, errors


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
