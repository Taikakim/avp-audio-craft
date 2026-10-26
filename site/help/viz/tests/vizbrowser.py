# Owner: WINTERMUTE (created 2026-10-26)
"""Helpers for the viz browser tests. A uniquely named module on purpose: `from conftest import ...` binds to whichever
conftest.py pytest imported last (site/help/tests has one too), which broke mixed runs."""
import glob
import os

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


def chromium_path():
    """The mir venv's Playwright expects a Chromium build that is not installed; use the newest one that is."""
    found = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
    return found[-1] if found else None


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
