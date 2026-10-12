import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  // M1 T11's bottom tabs are plain `<button class="tab" data-testid="bottom-tab-...">` with
  // no `role="tab"` (M1:5554 names these testids as the Playwright surface), so a role
  // locator matches nothing.
  await page.locator("[data-testid=bottom-tab-prompt]").click();
});

test("the bottom pane keeps 4.1's geometry with the tab open", async ({ page }) => {
  const pane = page.locator("[data-region=bottom-pane]");
  await expect(pane).toHaveCount(1);
  expect((await pane.boundingBox())!.height).toBeCloseTo(248, 0);

  const body = page.locator("[data-tab-body=prompt]");
  expect((await body.boundingBox())!.height).toBeCloseTo(162, 0);

  const preview = page.locator("[data-region=preview-container]");
  expect((await preview.boundingBox())!.height).toBeCloseTo(44, 0);
});

test("the three columns and the sigma canvas are present", async ({ page }) => {
  await expect(page.locator("[data-col=prompt]")).toBeVisible();
  await expect(page.locator("[data-col=model-stage]")).toBeVisible();
  await expect(page.locator("[data-col=sigma]")).toBeVisible();
  await expect(page.locator("canvas[data-canvas=sigma]")).toBeVisible();
});

test("POST greys CFG and says why; BASE restores it", async ({ page }) => {
  await expect(page.getByLabel("CFG")).toBeEnabled();
  await page.getByRole("button", { name: "POST" }).click();
  await page.getByRole("button", { name: "continue" }).click();
  await expect(page.getByLabel("CFG")).toBeDisabled();
  await expect(page.getByText("POST: guidance is distilled in — CFG is off")).toBeVisible();

  await page.getByRole("button", { name: "BASE" }).click();
  await page.getByRole("button", { name: "continue" }).click();
  await expect(page.getByLabel("CFG")).toBeEnabled();
});

test("ADVANCED SAMPLING shows sigma max read-only at 1.00 with no clip selected", async ({ page }) => {
  await page.locator("[data-module-toggle=advanced-sampling]").click();
  const sigmaMax = page.getByLabel("σ MAX");
  await expect(sigmaMax).toHaveValue("1.00");
  await expect(sigmaMax).toHaveAttribute("readonly", "");
});
