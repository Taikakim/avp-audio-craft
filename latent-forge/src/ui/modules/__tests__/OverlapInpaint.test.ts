// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import OverlapInpaint from "../OverlapInpaint.svelte";

function seedOverlap(): string {
  arrangement.clips.splice(0, arrangement.clips.length);
  const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
  const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
  const [overlap] = arrangement.overlaps;
  view.select({ kind: "overlap", key: overlap.key });
  return overlap.key;
}

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  view.clearSelection();
});

afterEach(() => {
  cleanup();
  arrangement.clips.splice(0, arrangement.clips.length);
  view.clearSelection();
});

describe("OverlapInpaint.svelte (spec §4.6.1)", () => {
  it("shows the info line naming the lane and both clips", () => {
    seedOverlap();
    const { getByText } = render(OverlapInpaint);
    expect(getByText(/lane 1 · A → B · mask/)).toBeTruthy();
  });

  it("CHROMA CROSSFADE is on by default and toggling it writes through setOverlapParams", async () => {
    const key = seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    const toggle = getByTestId("overlap-chroma-xfade");
    expect(toggle.textContent).toContain("ON");
    await fireEvent.click(toggle);
    expect(arrangement.overlapParams(key).chroma_xfade).toBe(false);
    expect(toggle.textContent).toContain("OFF");
  });

  it("LOCAL STEPS / CFG is off by default, and the STEPS/CFG fields are disabled until it is on", async () => {
    const key = seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    expect(arrangement.overlapParams(key).override).toBe(false);
    expect((getByTestId("overlap-steps") as HTMLInputElement).disabled).toBe(true);
    expect((getByTestId("overlap-cfg") as HTMLInputElement).disabled).toBe(true);
    await fireEvent.click(getByTestId("overlap-override"));
    expect(arrangement.overlapParams(key).override).toBe(true);
    expect((getByTestId("overlap-steps") as HTMLInputElement).disabled).toBe(false);
  });

  it("STEPS and CFG show OVERLAP_DEFAULT's values (28, 3.0)", () => {
    seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    expect((getByTestId("overlap-steps") as HTMLInputElement).value).toBe("28");
    expect((getByTestId("overlap-cfg") as HTMLInputElement).value).toBe("3");
  });

  it("mounts the 64px CROSSFADE CURVE editor, always active, over the overlap's own curve", () => {
    const key = seedOverlap();
    const { getByTestId, container } = render(OverlapInpaint);
    const wrapper = container.querySelector(".curve-editor") as HTMLElement;
    expect(wrapper).toBeTruthy();
    expect(getByTestId("envelope-node-0")).toBeTruthy();
    const region = getByTestId("envelope-node-0").closest('[data-region="envelope-overlay"]') as HTMLElement;
    expect(region.dataset.active).toBe("true");
    void key;
  });

  it("the INPAINT OVERLAP button is present, enabled, and a no-op this milestone", async () => {
    seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    const btn = getByTestId("inpaint-overlap-button");
    expect(btn.textContent?.trim()).toBe("▸ INPAINT OVERLAP");
    expect((btn as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(btn);   // no throw, no network call -- M9 wires the job
  });

  it("data-help matches the four verified v3 ids (460, 464, 466, 467)", () => {
    seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    expect(getByTestId("overlap-chroma-xfade").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("overlap-override").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("overlap-steps").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("overlap-cfg").getAttribute("data-help")).toBeTruthy();
  });

  it("renders nothing for a selected overlap key that no longer exists (a load or a clip move removed it)", () => {
    // peekOverlapParams never returns null, so `{#if params}` alone would render a body for a
    // stale key; the body is gated on the overlap itself too (critic pass 2 #5).
    view.select({ kind: "overlap", key: "gone-a-gone-b" });
    const { container, queryByTestId } = render(OverlapInpaint);
    expect(queryByTestId("inpaint-overlap-button")).toBeNull();
    expect(container.querySelector(".overlap")).toBeNull();
  });
});
