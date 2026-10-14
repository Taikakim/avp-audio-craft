// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import ModelLoadBar from "../ModelLoadBar.svelte";

afterEach(() => cleanup());

const base = { target: "medium-base", stage: "base model", stage_index: 2, stage_count: 3, elapsed_sec: 4.2 };

describe("ModelLoadBar", () => {
  it("shows a determinate fill and the ETA", () => {
    const { getByRole, getByTestId } = render(ModelLoadBar, {
      load: { ...base, expected_sec: 10, eta_sec: 5.8, fraction: 0.42 },
    });
    expect(getByRole("progressbar").getAttribute("aria-valuenow")).toBe("42");
    expect(getByTestId("model-load").textContent).toContain("base model 2/3 · ETA ~6s");
  });

  it("says finishing once the load runs over its estimate", () => {
    const { getByTestId } = render(ModelLoadBar, {
      load: { ...base, expected_sec: 10, eta_sec: 0, fraction: 0.99 },
    });
    expect(getByTestId("model-load").textContent).toContain("finishing…");
  });

  it("runs indeterminate with elapsed seconds when there is no estimate", () => {
    const { getByRole, getByTestId } = render(ModelLoadBar, {
      load: { ...base, expected_sec: null, eta_sec: null, fraction: null },
    });
    expect(getByRole("progressbar").hasAttribute("aria-valuenow")).toBe(false);
    expect(getByTestId("model-load").querySelector(".indet")).not.toBeNull();
    expect(getByTestId("model-load").textContent).toContain("base model 2/3 · 4s");
  });
});
