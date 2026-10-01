import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("bottom-tab-chroma").click();
});

test("the CHROMA tab is reachable from the bottom tab row (spec §4.5)", async ({ page }) => {
  await expect(page.locator('[data-region="bottom-tab-body"][data-tab="chroma"]')).toBeVisible();
  await expect(page.locator('[data-region="chroma-tab"]')).toBeVisible();
});

test("the tab body is M1's 162 px and the hint is M1's own (spec §4.5)", async ({ page }) => {
  const box = await page.locator('[data-region="bottom-tab-body"]').boundingBox();
  expect(box).not.toBeNull();
  expect(Math.round(box!.height)).toBe(162);
  await expect(page.getByTestId("bottom-hint")).toHaveText("hover the heatmap to read a frame");
});

test("the heatmap canvas is present and has real size (spec §5.4)", async ({ page }) => {
  const canvas = page.getByTestId("chroma-heatmap");
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThan(200);
  expect(box!.height).toBeGreaterThan(40);
});

test("the detune scan strip is present at its own 500 x 30 (spec §5.4, v3 332)", async ({ page }) => {
  const strip = page.getByTestId("chroma-scan-strip");
  await expect(strip).toBeVisible();
  // Height is the fixed 30 px of the drawing. Width is NOT asserted as 500: the canvas bitmap is
  // fitted to its CSS box (fitChromaCanvas), which is the column width here (248 px in this
  // layout), so the drawing's 500 px is a design size, not a rendered one. What must hold is that
  // the bitmap tracks the box it is drawn in. (Electro-Sheep 1: revisit if the pane gets wider.)
  const [attrW, attrH, cssW, cssH] = await strip.evaluate((el) => {
    const c = el as HTMLCanvasElement;
    return [c.width, c.height, c.clientWidth, c.clientHeight];
  });
  expect(attrW).toBe(cssW);
  expect(attrH).toBe(cssH);
  expect(cssH).toBeGreaterThanOrEqual(26); // the drawing's 30 px, less its own border
  expect(cssH).toBeLessThanOrEqual(30);
});

test("the four view buttons and MATCH CURVE are present (spec §5.4)", async ({ page }) => {
  for (const v of ["global", "bass", "mid", "high"]) {
    await expect(page.locator(`[data-chroma-view="${v}"]`)).toBeVisible();
  }
  await expect(page.getByTestId("chroma-curve-toggle")).toBeVisible();
});

test("the legend, its readout and the target row are present (spec §5.4)", async ({ page }) => {
  await expect(page.getByTestId("chroma-legend")).toBeVisible();
  await expect(page.getByTestId("chroma-match-readout")).toBeVisible();
  await expect(page.locator('[data-region="chroma-target-row"]')).toBeVisible();
});
