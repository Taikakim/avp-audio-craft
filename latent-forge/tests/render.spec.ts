import { expect, test, type Locator, type Page } from "@playwright/test";

// ---- M5's helpers (tests/timeline.spec.ts), copied verbatim as M7 T10 copied them ----
async function box(loc: Locator) {
  const b = await loc.boundingBox();
  if (!b) throw new Error("element has no bounding box");
  return b;
}
// ---------------------------------------------------------------------------------------

async function openPrompt(page: Page) {
  await page.locator('[data-testid="bottom-tab-prompt"]').click();
  return page.locator('[data-tab-body="prompt"]');
}

/** Opens PROMPT and types one, which every `▸ RENDER` test needs: `BASE_DEFAULTS.prompt` is `""`
 *  (m1 plan:898-899), so on a fresh `page.goto("/")` `renderBlock` returns
 *  `"needs a prompt — /generate requires a non-empty prompt."` and the button is `disabled` with
 *  that as its `title`. The field's testid is M4 T9's (`m4 plan:3765`). */
async function seedPrompt(page: Page) {
  const body = await openPrompt(page);
  await page.locator('[data-testid="prompt-text"]').fill("dub techno, tape hiss");
  await expect(page.locator('[data-testid="preview-render"]')).toBeEnabled();
  return body;
}

const CLIP = '.clip[role="button"]';

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-region="topbar"]')).toBeVisible();
});

test("▸ RENDER submits, labels itself SAMPLING, and lands one HISTORY entry", async ({ page }) => {
  await seedPrompt(page);
  const render = page.locator('[data-testid="preview-render"]');
  await expect(render).toBeEnabled();
  await expect(page.locator('[data-testid="preview-history"]')).toBeDisabled();

  await render.click();
  // §7.1: the control that started the job reads the count; the mock queues before it runs.
  await expect(render).toContainText(/SAMPLING · \d+ steps left/);
  await expect(render).toBeDisabled();

  const history = page.locator('[data-testid="preview-history"]');
  await expect(history).toBeEnabled({ timeout: 30_000 });
  await expect(history.locator("option")).toHaveCount(1);
  await expect(history.locator("option").first()).toContainText("GEN");
  await expect(render).toContainText("▸ RENDER");
});

test("the previewed render drags onto a lane as a clip of its own length, not four seconds", async ({ page }) => {
  await seedPrompt(page);
  await page.locator('[data-testid="preview-render"]').click();
  await expect(page.locator('[data-testid="preview-history"]')).toBeEnabled({ timeout: 30_000 });

  const label = await page.locator('[data-testid="preview-length"]').textContent();
  const shown = Number((label ?? "").replace(/[^\d.]/g, ""));
  expect(shown).toBeGreaterThan(0);

  const canvas = page.locator('[data-region="lane-canvas"]').first();
  const target = await box(canvas);
  await page.locator('[data-testid="preview-drag-handle"]')
    .dragTo(canvas, { targetPosition: { x: 20, y: target.height / 2 } });

  await expect(page.locator(CLIP)).toHaveCount(1);
  // A 4 s clip at the mock's default zoom is visibly narrower than the render; the width is the
  // end-to-end evidence that the drop used the render's length.
  const clipBox = await box(page.locator(CLIP).first());
  expect(clipBox.width).toBeGreaterThan(4 * (target.width / 60));
});

test("MIXDOWN commits and lights the SIGNAL PATH", async ({ page }) => {
  // A commit needs a non-empty arrangement (validate_commit), so seed one from a render.
  await seedPrompt(page);
  await page.locator('[data-testid="preview-render"]').click();
  await expect(page.locator('[data-testid="preview-history"]')).toBeEnabled({ timeout: 30_000 });
  const canvas = page.locator('[data-region="lane-canvas"]').first();
  await page.locator('[data-testid="preview-drag-handle"]')
    .dragTo(canvas, { targetPosition: { x: 20, y: (await box(canvas)).height / 2 } });
  await expect(page.locator(CLIP)).toHaveCount(1);

  const mixdown = page.locator('[data-testid="mixdown-button"]');
  await expect(mixdown).toBeEnabled();
  await mixdown.click();
  await expect(mixdown).toContainText(/SAMPLING · \d+ steps left/);
  await expect(mixdown).toContainText("▸ MIXDOWN", { timeout: 60_000 });

  await page.locator('[data-testid="bottom-tab-mix"]').click();
  const lit = page.locator('[data-tab-body="mix"] [data-signal-stage][data-lit="true"]');
  await expect(lit.first()).toBeVisible();
});

test("the PREVIEW/MIXDOWN A/B is present but unpressable until a commit exists", async ({ page }) => {
  const mix = page.locator('[data-testid="master-source-mixdown"]');
  // Task 9's decision: always in the DOM, disabled with a reason -- not hidden.
  await expect(mix).toBeVisible();
  await expect(mix).toBeDisabled();
  await expect(mix).toHaveAttribute("title", "nothing has been committed yet");
  await expect(page.locator('[data-region="preview-mixdown-toggle"]')).toHaveAttribute("data-help", /.+/);
});

test("a rejected render shows §9.7's inline error, and the next render clears it", async ({ page }) => {
  await page.route("**/forge/jobs", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      status: 400, contentType: "application/json",
      body: JSON.stringify({ ok: false, error: "unknown render field(s): duration_sec" }),
    });
  });
  await seedPrompt(page);
  await page.locator('[data-testid="preview-render"]').click();

  const err = page.locator('[data-testid="render-error"]');
  await expect(err).toBeVisible();
  await expect(err).toContainText("duration_sec");

  await page.unroute("**/forge/jobs");
  await page.locator('[data-testid="preview-render"]').click();
  await expect(err).toHaveCount(0);
});

test("USE SETTINGS copies the render's own settings into the pane; HISTORY alone does not", async ({ page }) => {
  const body = await seedPrompt(page);
  const steps = body.getByLabel("STEPS");
  await steps.fill("31");
  await page.locator('[data-testid="preview-render"]').click();
  await expect(page.locator('[data-testid="preview-history"]')).toBeEnabled({ timeout: 30_000 });

  await steps.fill("12");
  // X15: selecting in HISTORY loads audio only.
  await page.locator('[data-testid="preview-history"]').selectOption({ index: 0 });
  await expect(steps).toHaveValue("12");

  await page.locator('[data-testid="preview-use-settings"]').click();
  await expect(steps).toHaveValue("31");
});
