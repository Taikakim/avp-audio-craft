# Owner: WINTERMUTE (created 2026-10-27)
"""Browser tests for the routing module, written against the DOM contract in
docs/superpowers/plans/2026-10-27-routing.md. Run:
/home/kim/Projects/mir/mir/bin/python -m pytest site/help/viz/tests/test_routing_browser.py
"""
import json
import re
from pathlib import Path
from urllib.parse import quote

from vizbrowser import open_page

ROOT = ".vz-route"
FIXTURE = json.loads((Path(__file__).parent / "routing_fixture.json").read_text())
RENAME = FIXTURE["rename"]

# row id -> first real parameter name (copied from the contract's row table, block 0)
FIRST_NAME = {
    "input": "latent_proj.weight",
    "time1": "t_embedder.mlp.0.weight",
    "time2": "t_embedder.mlp.2.weight",
    "adaln": "blocks.0.adaLN_mod.1.weight",
    "qkv": "blocks.0.attn.qkv.weight",
    "attn-out": "blocks.0.attn.proj.weight",
    "mlp-up": "blocks.0.mlp.0.weight",
    "mlp-down": "blocks.0.mlp.2.weight",
    "biases": "latent_proj.bias",
    "final-norm": "norm_final.weight",
    "output": "out_proj.weight",
}
ROW_IDS = list(FIRST_NAME)
DIFFERS = {"time1", "time2", "adaln", "qkv"}
OURS_BTN = "button:has-text(\"Our head's names\")"
EXPECTED_BTN = "button:has-text('Names the rules expect')"
TICK = "Number(document.querySelector('.vz-route').dataset.tick)"


def url(base, rm=False, params=None):
    u = f"{base}/viz/dev.html?m=routing"
    if rm:
        u += "&rm=1"
    if params is not None:
        u += "&p=" + quote(json.dumps(params))
    return u


def renamed(name):
    for a, b in RENAME:
        name = name.replace(a, b)
    return name


def attr(page, name):
    return page.get_attribute(ROOT, name)


def row(page, rid):
    return page.locator(f"button.vz-route-row[data-row='{rid}']")


def numbers(text):
    return [int(n) for n in re.findall(r"\d+", text)]


def test_mounts_clean_with_rows_stations_and_note(browser, base_url):
    ctx, page, errors = open_page(browser, url(base_url))
    assert attr(page, "data-view") == "ours"
    assert (attr(page, "data-selected") or "") == ""
    assert page.locator("ul.vz-route-rows li").count() == 11
    assert page.locator("button.vz-route-row").count() == 11
    assert page.locator(".vz-station").count() == 3
    assert page.locator("text=What's real here").count() >= 1
    page.wait_for_timeout(300)
    assert errors == []
    ctx.close()


def test_ours_view_groups_match_fixture(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    for rid, name in FIRST_NAME.items():
        want = FIXTURE["ours"][name]
        assert row(page, rid).get_attribute("data-group") == want["group"], rid
        assert int(row(page, rid).get_attribute("data-blocks")) == want["blocks"], rid
    ctx.close()


def test_switching_names_reroutes_and_back(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    ours, expected = page.locator(OURS_BTN), page.locator(EXPECTED_BTN)
    assert ours.get_attribute("aria-pressed") == "true"
    assert expected.get_attribute("aria-pressed") == "false"
    expected.click()
    assert expected.get_attribute("aria-pressed") == "true"
    assert ours.get_attribute("aria-pressed") == "false"
    assert attr(page, "data-view") == "expected"
    assert int(row(page, "qkv").get_attribute("data-blocks")) == 3
    assert row(page, "adaln").get_attribute("data-group") == "sign"
    assert int(row(page, "adaln").get_attribute("data-blocks")) == 6
    assert row(page, "time1").get_attribute("data-group") == "spectral"
    assert row(page, "time2").get_attribute("data-group") == "spectral"
    for rid, name in FIRST_NAME.items():
        want = FIXTURE["expected_names"][renamed(name)]
        assert row(page, rid).get_attribute("data-group") == want["group"], rid
        assert int(row(page, rid).get_attribute("data-blocks")) == want["blocks"], rid
    ours.click()
    assert attr(page, "data-view") == "ours"
    assert int(row(page, "qkv").get_attribute("data-blocks")) == 1
    assert row(page, "adaln").get_attribute("data-group") == "spectral"
    assert int(row(page, "adaln").get_attribute("data-blocks")) == 1
    assert row(page, "time1").get_attribute("data-group") == "colnorm"
    assert row(page, "time2").get_attribute("data-group") == "colnorm"
    ctx.close()


def test_four_rows_differ_in_both_views(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    for view_btn in (OURS_BTN, EXPECTED_BTN):
        page.click(view_btn)
        yes = {
            rid for rid in ROW_IDS if row(page, rid).get_attribute("data-differs") == "yes"
        }
        assert yes == DIFFERS
        assert page.locator("button.vz-route-row[data-differs='yes']").count() == 4
        for rid in ROW_IDS:
            has_word = "differs" in row(page, rid).inner_text().lower()
            assert has_word == (rid in DIFFERS), rid
    ctx.close()


def test_summary_counts_in_both_views(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    ours = [g["group"] for g in FIXTURE["ours"].values()]
    exp = [g["group"] for g in FIXTURE["expected_names"].values()]
    count = lambda gs: [gs.count("spectral"), gs.count("sign"), gs.count("colnorm")]
    assert count(ours) == [11, 15, 2] and count(exp) == [11, 17, 0]
    assert numbers(page.inner_text("#vz-route-summary")) == [11, 15, 2]
    page.click(EXPECTED_BTN)
    assert numbers(page.inner_text("#vz-route-summary")) == [11, 17, 0]
    ctx.close()


def test_clicking_rows_fills_detail(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    row(page, "qkv").click()
    assert attr(page, "data-selected") == "qkv"
    assert row(page, "qkv").get_attribute("aria-pressed") == "true"
    detail = page.inner_text("#vz-route-detail")
    assert "to_qkv" in detail
    assert "6.3e-4" in detail or "0.00063" in detail
    row(page, "time1").click()
    assert attr(page, "data-selected") == "time1"
    assert row(page, "qkv").get_attribute("aria-pressed") == "false"
    assert "not worked out" in page.inner_text("#vz-route-detail")
    ctx.close()


def test_dots_move_and_reduced_motion_holds_until_step(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    t0 = page.evaluate(TICK)
    page.wait_for_function(
        f"{TICK} > {t0}", timeout=1000
    )
    ctx.close()
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    t0 = page.evaluate(TICK)
    page.wait_for_timeout(1000)
    assert page.evaluate(TICK) == t0
    page.click("button:text-is('Step')")
    page.wait_for_function(f"{TICK} > {t0}", timeout=2000)
    ctx.close()


def test_destroy_leaves_no_frame_and_no_root(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    page.wait_for_timeout(200)
    assert page.evaluate("window.__rafOutstanding.size") >= 1
    assert page.evaluate("(() => { window.__viz.destroy(); return window.__rafOutstanding.size; })()") == 0
    assert page.locator(ROOT).count() == 0
    ctx.close()


def test_no_horizontal_overflow_at_360(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url), viewport={"width": 360, "height": 740})
    page.wait_for_timeout(300)
    check = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    assert page.evaluate(check)
    page.click(EXPECTED_BTN)
    row(page, "qkv").click()
    page.wait_for_timeout(500)
    assert page.evaluate(check)
    ctx.close()


def test_keyboard_reaches_names_and_rows_and_enter_selects(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url))
    probe = "document.activeElement ? document.activeElement.textContent.trim() : ''"
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate(probe) in ("Our head's names", "Names the rules expect"):
            break
    else:
        raise AssertionError("Tab never reached a Names button")
    for _ in range(30):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.classList.contains('vz-route-row')"):
            break
    else:
        raise AssertionError("Tab never reached a row button")
    rid = page.evaluate("document.activeElement.dataset.row")
    page.keyboard.press("Enter")
    page.wait_for_function(
        "(r) => document.querySelector('.vz-route').dataset.selected === r", arg=rid, timeout=2000
    )
    assert row(page, rid).get_attribute("aria-pressed") == "true"
    ctx.close()


def test_params_set_start_state_and_invalid_falls_back(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"view": "expected", "row": "adaln"}))
    assert attr(page, "data-view") == "expected"
    assert attr(page, "data-selected") == "adaln"
    assert page.inner_text("#vz-route-detail").strip() != ""
    assert page.locator(EXPECTED_BTN).get_attribute("aria-pressed") == "true"
    ctx.close()
    ctx, page, _ = open_page(browser, url(base_url, rm=True, params={"view": "x", "row": "nope"}))
    assert attr(page, "data-view") == "ours"
    assert (attr(page, "data-selected") or "") == ""
    ctx.close()


def test_note_keeps_the_honesty_lines(browser, base_url):
    ctx, page, _ = open_page(browser, url(base_url, rm=True))
    text = page.inner_text(ROOT).lower()
    assert "not measured" in text
    assert "hypothetical" in text
    ctx.close()
