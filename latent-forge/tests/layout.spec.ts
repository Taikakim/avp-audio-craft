import { expect, test, type Locator, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";

const SCREENS = fileURLToPath(new URL("./__screens__/", import.meta.url));
const HANDOFF = fileURLToPath(
  new URL("../../docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html", import.meta.url),
);

/** Spec §4.1 / §11.3: the region sizes are exact, asserted to +/- 1 px. */
const REGION_HEIGHT: Record<string, number> = {
  topbar: 42,
  "bottom-pane": 248,
  "ruler-canvas": 30,
  "lane-canvas": 62,
  "master-canvas": 56,
  // Both visible on the default beforeEach page load: the bottom pane's
  // default tab is "prompt" (view store default), and the preview container
  // is always mounted regardless of tab -- neither needs a click first.
  "preview-container": 44,
  "bottom-tab-body": 162,
};

async function height(loc: Locator): Promise<number> {
  const box = await loc.boundingBox();
  if (!box) throw new Error("element has no bounding box");
  return box.height;
}

async function width(loc: Locator): Promise<number> {
  const box = await loc.boundingBox();
  if (!box) throw new Error("element has no bounding box");
  return box.width;
}

function expectPx(actual: number, expected: number, what: string) {
  expect(Math.abs(actual - expected), `${what}: expected ${expected}px, measured ${actual}px`)
    .toBeLessThanOrEqual(1);
}

interface BoxSpacing {
  top: number;
  right: number;
  bottom: number;
  left: number;
  gap: number;
}

/** getComputedStyle's padding box + gap, for the two elements spec §4.1 fixes
 *  by padding/gap rather than by a plain bounding-box height. */
async function spacing(loc: Locator): Promise<BoxSpacing> {
  return loc.evaluate((el) => {
    const cs = getComputedStyle(el);
    const gap = parseFloat(cs.gap || cs.columnGap || cs.rowGap || "0") || 0;
    return {
      top: parseFloat(cs.paddingTop) || 0,
      right: parseFloat(cs.paddingRight) || 0,
      bottom: parseFloat(cs.paddingBottom) || 0,
      left: parseFloat(cs.paddingLeft) || 0,
      gap,
    };
  });
}

test.beforeEach(async ({ page }: { page: Page }) => {
  await page.goto("/");
  await expect(page.locator('[data-region="topbar"]')).toBeVisible();
});

test("every region has the height spec §4.1 fixes", async ({ page }) => {
  for (const [region, px] of Object.entries(REGION_HEIGHT)) {
    const loc = page.locator(`[data-region="${region}"]`).first();
    await expect(loc).toBeVisible();
    expectPx(await height(loc), px, region);
  }
});

test("centre column padding/gap and bottom pane padding match spec §4.1", async ({ page }) => {
  // Centre column: padding 10px all round, gap 8px between its children (spec §4.1).
  const centre = page.locator('[data-region="centre"]');
  const c = await spacing(centre);
  expectPx(c.top, 10, "centre column padding-top");
  expectPx(c.right, 10, "centre column padding-right");
  expectPx(c.bottom, 10, "centre column padding-bottom");
  expectPx(c.left, 10, "centre column padding-left");
  expectPx(c.gap, 8, "centre column gap");

  // Bottom pane: padding 6px 10px 8px (top / right+left / bottom) (spec §4.1).
  const bottomPane = page.locator('[data-region="bottom-pane"]');
  const b = await spacing(bottomPane);
  expectPx(b.top, 6, "bottom pane padding-top");
  expectPx(b.right, 10, "bottom pane padding-right");
  expectPx(b.bottom, 8, "bottom pane padding-bottom");
  expectPx(b.left, 10, "bottom pane padding-left");
});

test("all four lane canvases are 62 px, not just the first", async ({ page }) => {
  const lanes = page.locator('[data-region="lane-canvas"]');
  await expect(lanes).toHaveCount(4);
  for (let i = 0; i < 4; i++) expectPx(await height(lanes.nth(i)), 62, `lane ${i + 1} canvas`);
});

test("the right pane is 296 px and collapses to a 24 px strip", async ({ page }) => {
  const pane = page.locator('[data-region="right-pane"]');
  expectPx(await width(pane), 296, "right pane");
  await page.locator('[data-testid="side-toggle"]').click();
  expectPx(await width(pane), 24, "collapsed right pane");
  await page.locator('[data-testid="side-toggle"]').click();
  expectPx(await width(pane), 296, "re-expanded right pane");
});

test("the page never scrolls horizontally", async ({ page }) => {
  const overflow = await page.evaluate(() => {
    const el = document.documentElement;
    return { scroll: el.scrollWidth, client: el.clientWidth };
  });
  expect(overflow.scroll, "document scrolls horizontally").toBeLessThanOrEqual(overflow.client);
});

test("each bottom tab opens", async ({ page }) => {
  // The tab BUTTONS are data-testid="bottom-tab-<id>"; the one tab BODY is
  // [data-region="bottom-tab-body"] with data-tab set to the current tab (Task 11). An earlier
  // draft clicked [data-tab="<id>"] -- the body, so only the current tab ever matched -- and
  // waited for a [data-tab-body] M1 never emits (reconcile pass 2026-09-25).
  const body = page.locator('[data-region="bottom-tab-body"]');
  for (const id of ["chroma", "prompt", "mix", "terminal"]) {
    await page.locator(`[data-testid="bottom-tab-${id}"]`).click();
    await expect(body).toHaveAttribute("data-tab", id);
    await expect(body).toBeVisible();
    expectPx(await height(page.locator('[data-region="bottom-pane"]')), 248, `bottom pane on ${id}`);
  }
});

test("each right-pane module opens, and OVERLAP is absent without an overlap selected", async ({ page }) => {
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(0);
  for (const id of ["files", "lane-chain", "advanced-sampling", "master-chain"]) {
    const body = page.locator(`[data-module-body="${id}"]`);
    if (!(await body.isVisible())) await page.locator(`[data-module-toggle="${id}"]`).click();
    await expect(body).toBeVisible();
  }
});

test("HELP shows the control's own string for ten sampled controls", async ({ page }) => {
  await page.locator('[data-testid="help-toggle"]').click();
  const box = page.locator('[data-testid="help-box"]');
  const controls = page.locator("[data-help]");
  const total = await controls.count();
  expect(total, "no [data-help] controls rendered at all").toBeGreaterThanOrEqual(10);

  let checked = 0;
  for (let i = 0; i < total && checked < 10; i++) {
    const c = controls.nth(i);
    if (!(await c.isVisible())) continue;
    const expected = await c.getAttribute("data-help");
    await c.hover();
    await expect(box).toBeVisible();
    await expect(box).toHaveText(expected ?? "");
    checked++;
  }
  expect(checked, "fewer than ten visible [data-help] controls").toBe(10);
});

test("DARK flips data-theme and flips back", async ({ page }) => {
  const html = page.locator("html");
  await page.locator('[data-testid="dark-toggle"]').click();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.locator('[data-testid="dark-toggle"]').click();
  await expect(html).not.toHaveAttribute("data-theme", "dark");
});

test("the transport lives in the ruler's left cell (spec §4.3, §10 X1)", async ({ page }) => {
  const transport = page.locator('[data-region="ruler-transport"]');
  await expect(transport).toBeVisible();
  await expect(transport.locator('[data-testid="transport-play"]')).toBeVisible();
  await expect(transport.locator('[data-testid="transport-stop"]')).toBeVisible();
  await expect(transport.locator('[data-testid="transport-loop"]')).toBeVisible();

  // It is inside the ruler row, left of the ruler canvas -- not a separate bar.
  const cell = await transport.boundingBox();
  const ruler = await page.locator('[data-region="ruler-canvas"]').first().boundingBox();
  expect(cell && ruler).toBeTruthy();
  expect(cell!.x + cell!.width).toBeLessThanOrEqual(ruler!.x + 1);
});

test("the FILES module lists the mock server's files and they are draggable", async ({ page }) => {
  const body = page.locator('[data-module-body="files"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="files"]').click();
  const rows = body.locator('[data-file-row]');
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThan(0);
  await expect(rows.first()).toHaveAttribute("draggable", "true");
});

test("screenshots for the side-by-side", async ({ page }) => {
  await page.screenshot({ path: `${SCREENS}latent-forge-1800x900.png`, fullPage: false });
  await page.goto(`file://${HANDOFF}`);
  await expect(page.getByText("SA3 STUDIO").first()).toBeVisible();
  await page.screenshot({ path: `${SCREENS}handoff-v3-1800x900.png`, fullPage: false });
});
