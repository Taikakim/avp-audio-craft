# Owner: WINTERMUTE (created 2026-10-26)
"""Fixtures for the help-pane browser tests.

Serves a site root (C1 layout) over a stdlib http.server thread (ES modules need http, not file://) and
drives Chromium through Playwright. `--root` / `--page` let the integration task run the same generic tests
against the real dry-run build; tests marked via `fixture_only` skip on any other root.
"""
import functools
import http.server
import json
import re
import threading
from pathlib import Path

import pytest

HERE = Path(__file__).parent
FIXTURE_ROOT = (HERE / "fixture").resolve()


def pytest_addoption(parser):
    parser.addoption("--root", default=str(FIXTURE_ROOT),
                     help="site root to serve (C1 layout: blog/, help/, edg3.css). Default: tests/fixture")
    parser.addoption("--page", default="blog/page.html",
                     help="page under --root that carries the pane (C3)")


@pytest.fixture(scope="session")
def root(request):
    p = Path(request.config.getoption("--root")).resolve()
    assert (p / "help" / "glossary.json").exists(), f"{p}/help/glossary.json missing"
    return p


@pytest.fixture(scope="session")
def is_fixture_root(root):
    return root == FIXTURE_ROOT


@pytest.fixture
def fixture_only(is_fixture_root):
    if not is_fixture_root:
        pytest.skip("depends on fixture-specific entries")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep pytest output clean
        pass

    def translate_path(self, path):
        # The fixture root holds no copy of the pane itself: serve the real files from site/help/ so the
        # tests always run the code under test (any other --root brings its own copy).
        rel = path.split("?", 1)[0].split("#", 1)[0]
        if Path(self.directory).resolve() == FIXTURE_ROOT and rel in ("/help/help-pane.js", "/help/help-pane.css"):
            return str(HERE.parent / rel.rsplit("/", 1)[1])
        return super().translate_path(path)


@pytest.fixture(scope="session")
def base_url(root):
    handler = functools.partial(_Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="session")
def page_rel(request):
    return request.config.getoption("--page")


@pytest.fixture(scope="session")
def page_url(base_url, page_rel):
    return f"{base_url}/{page_rel}"


@pytest.fixture(scope="session")
def entries(root):
    data = json.loads((root / "help" / "glossary.json").read_text(encoding="utf-8"))
    return data["entries"]


@pytest.fixture(scope="session")
def terms_on_page(root, page_rel, entries):
    text = (root / page_rel).read_text(encoding="utf-8")
    seen = []
    for t in re.findall(r'<a class="gl" data-term="([^"]+)"', text):
        if t in entries and t not in seen:
            seen.append(t)
    assert seen, f"{page_rel} has no a.gl links that match glossary.json"
    return seen


@pytest.fixture(scope="session")
def quiz_term(terms_on_page, entries):
    for t in terms_on_page:
        if entries[t].get("quiz"):
            return t
    pytest.skip("no term on the page has a quiz")


@pytest.fixture(scope="session")
def viz_term(terms_on_page, entries, quiz_term):
    for t in terms_on_page:
        if entries[t].get("viz"):
            return t
    return quiz_term


@pytest.fixture(scope="session")
def link_pair(entries):
    for src, e in entries.items():
        text = (e.get("plain") or "") + (e.get("ours") or "")
        for dst in re.findall(r'class="gl" data-term="([^"]+)"', text):
            if dst in entries and dst != src:
                return src, dst
    pytest.skip("no entry links to another entry in plain/ours")


@pytest.fixture(scope="session")
def pw_browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # the mir venv's Playwright expects Chromium 1208 but only a newer build is cached: use the newest one found
        import glob
        found = sorted(glob.glob(str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
        b = p.chromium.launch(executable_path=found[-1]) if found else p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def make_page(pw_browser):
    contexts = []

    def make(viewport=(1280, 800), js=True, touch=False, init_script=None):
        ctx = pw_browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            java_script_enabled=js, has_touch=touch)
        contexts.append(ctx)
        if init_script:
            ctx.add_init_script(init_script)
        page = ctx.new_page()
        page.hp_errors = []
        page.on("pageerror", lambda e: page.hp_errors.append(str(e)))
        return page

    yield make
    for c in contexts:
        c.close()
