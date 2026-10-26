# Owner: WINTERMUTE (created 2026-10-26)
"""Shared fixtures for the viz browser tests (moved out of test_viz_browser.py)."""
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
