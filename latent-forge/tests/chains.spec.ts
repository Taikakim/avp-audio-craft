import { expect, test } from "@playwright/test";

// Same testid convention M4's own e2e fragment verified against the real BottomPane.svelte
// (data-testid="bottom-tab-<id>" to click, tests/sampling.spec.ts:beforeEach) -- and, since the
// reconcile pass of 2026-09-25, the one M1's own layout spec uses too (Global Constraint #5).

test("LANE CHAIN and MASTER CHAIN modules open from the right pane", async ({ page }) => {
  await page.goto("/");
  for (const id of ["lane-chain", "master-chain"]) {
    const body = page.locator(`[data-module-body="${id}"]`);
    if (!(await body.isVisible())) await page.locator(`[data-module-toggle="${id}"]`).click();
    await expect(body).toBeVisible();
  }
});

test("the MIX + SIGNAL PATH tab renders", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-testid=bottom-tab-mix]").click();
  await expect(page.locator("[data-tab-body=mix]")).toBeVisible();
});

test("the fold / summary toggle works", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-testid=bottom-tab-mix]").click();
  await page.locator('[data-testid="mix-fold"]').click();
  await expect(page.locator('[aria-label="MIX ORDER"]')).toHaveCount(0);
  await page.locator('[data-testid="mix-expand"]').click();
  await expect(page.locator('[aria-label="MIX ORDER"]')).toBeVisible();
});

test("a lane's chain dot lights when its LANE CHAIN goes non-default", async ({ page }) => {
  await page.goto("/");
  // lane-chain is OPEN by default (view.openModules = ["files", "lane-chain"], M1 plan line 3148),
  // and ModuleShell renders the body only while open -- an unconditional click would close it.
  const body = page.locator('[data-module-body="lane-chain"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="lane-chain"]').click();
  // M5's LaneHeader.svelte carries no data-testid on the dot itself (verified against
  // docs/superpowers/plans/.../m5-timeline-fidelity.md:2594) -- .dot is the only hook there is.
  const dot = page.locator(".header").first().locator(".dot");
  await expect(dot).not.toHaveClass(/lit/);
  await page.locator('[data-testid="latch-toggle"]').click();
  await expect(dot).toHaveClass(/lit/);
});
