# Owner: WINTERMUTE (created 2026-10-26)
"""Shared fixtures for the viz browser tests (moved out of test_viz_browser.py). Plain helpers live in vizbrowser.py."""
# Last edited: WINTERMUTE 2026-10-26 -- review fixes (open_page, RAF_SPY, chromium_path moved to vizbrowser.py)
import functools
import http.server
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from vizbrowser import chromium_path

HELP_ROOT = Path(__file__).resolve().parents[2]          # .../site/help

@pytest.fixture(scope="module")
def base_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HELP_ROOT))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chromium_path())
        yield b
        b.close()
