import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "STATISTICS" }).click();
});

test("the statistics view is reachable from the WORKSPACE / STATISTICS tabs (spec §4.2)", async ({ page }) => {
  await expect(page.locator('[data-region="stats-view"]')).toBeVisible();
});

test("all three panels and all five lane-selection buttons are present (spec §4.4)", async ({ page }) => {
  await expect(page.locator('[data-stats-panel="xcorr"]')).toBeVisible();
  await expect(page.locator('[data-stats-panel="xy"]')).toBeVisible();
  await expect(page.locator('[data-stats-panel="timeseries"]')).toBeVisible();
  await expect(page.locator("[data-stats-lane]")).toHaveCount(5);
  for (const v of ["1", "2", "3", "4", "all"]) {
    await expect(page.locator(`[data-stats-lane="${v}"]`)).toBeVisible();
  }
});

test("the xcorr canvas is 300px tall, spec §4.4's fixed panel size", async ({ page }) => {
  const canvas = page.locator('[data-stats-panel="xcorr"] canvas');
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeCloseTo(300, 0);
});

test("the bottom pane stays hidden in the statistics view (spec §4.4)", async ({ page }) => {
  await expect(page.locator('[data-region="bottom-pane"]')).toHaveCount(0);
});
