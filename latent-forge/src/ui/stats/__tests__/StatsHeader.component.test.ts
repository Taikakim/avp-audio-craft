// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import StatsHeader from "../StatsHeader.svelte";

afterEach(() => cleanup());

describe("StatsHeader renders the spec §4.4 header row", () => {
  it("renders ANALYSE and all five lane-selection buttons with the fixed data-stats-lane values", () => {
    const { getByTestId, container } = render(StatsHeader, {
      props: { selection: "all", onSelectionChange: () => {}, onAnalyse: () => {} },
    });
    expect(getByTestId("stats-analyse").textContent).toBe("ANALYSE");
    const attrs = Array.from(container.querySelectorAll("[data-stats-lane]")).map((el) =>
      el.getAttribute("data-stats-lane"),
    );
    expect(attrs).toEqual(["1", "2", "3", "4", "all"]);
  });

  it("marks the current selection active and the others not", () => {
    const { container } = render(StatsHeader, {
      props: { selection: 2, onSelectionChange: () => {}, onAnalyse: () => {} },
    });
    const lane2 = container.querySelector('[data-stats-lane="2"]')!;
    const lane3 = container.querySelector('[data-stats-lane="3"]')!;
    expect(lane2.classList.contains("active")).toBe(true);
    expect(lane3.classList.contains("active")).toBe(false);
  });

  it("renders the sidecar note verbatim", () => {
    const { getByText } = render(StatsHeader, {
      props: { selection: "all", onSelectionChange: () => {}, onAnalyse: () => {} },
    });
    expect(getByText("features read from the sidecars (.TIMESERIES.npz, .json)")).toBeTruthy();
  });

  it("clicking ANALYSE calls onAnalyse with the current selection prop", async () => {
    const onAnalyse = vi.fn();
    const { getByTestId } = render(StatsHeader, {
      props: { selection: 3, onSelectionChange: () => {}, onAnalyse },
    });
    await fireEvent.click(getByTestId("stats-analyse"));
    expect(onAnalyse).toHaveBeenCalledWith(3);
  });

  it("clicking a lane button calls onSelectionChange with that lane, not onAnalyse", async () => {
    const onSelectionChange = vi.fn();
    const onAnalyse = vi.fn();
    const { container } = render(StatsHeader, {
      props: { selection: "all", onSelectionChange, onAnalyse },
    });
    await fireEvent.click(container.querySelector('[data-stats-lane="4"]')!);
    expect(onSelectionChange).toHaveBeenCalledWith(4);
    expect(onAnalyse).not.toHaveBeenCalled();
  });
});
