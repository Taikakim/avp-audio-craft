// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chromaTarget } from "../../../lib/chroma/targetStore.svelte";
import { HELP } from "../../../lib/help/strings";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import TargetRow from "../TargetRow.svelte";

beforeEach(() => {
  chromaTarget.dispose();
  arrangement.setTargetLane(null);
});

afterEach(() => {
  chromaTarget.dispose();
  arrangement.setTargetLane(null);
  cleanup();
});

describe("TargetRow's DOM contract", () => {
  it("gives the chord field M1 T14's own id and the drawing's placeholder (v3 323)", () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    const field = getByTestId("chroma-chord") as HTMLInputElement;
    expect(field.getAttribute("data-help")).toBe(HELP.chromaChord);
    expect(field.placeholder).toBe("chord symbol");
  });

  it("ships the two mode buttons and the twelve keys WITHOUT data-help, because M1 has no id", () => {
    chromaTarget.setMode("set");
    const { container, getByTestId } = render(TargetRow);
    expect(getByTestId("chroma-target-mode-lane").hasAttribute("data-help")).toBe(false);
    expect(getByTestId("chroma-target-mode-set").hasAttribute("data-help")).toBe(false);
    const keys = container.querySelectorAll("[data-chroma-key]");
    expect(keys).toHaveLength(12);
    for (const k of keys) expect(k.hasAttribute("data-help")).toBe(false);
  });
});

describe("lane mode reads the TARGET lane from the arrangement store", () => {
  it("names the lane the timeline made the target", () => {
    arrangement.setTargetLane(2);
    const { getByTestId } = render(TargetRow);
    expect(getByTestId("chroma-target-mode-lane").textContent).toBe("LANE 3");
  });

  it("says so honestly when no lane is the target, instead of drawing an empty profile", () => {
    const { getByText } = render(TargetRow);
    expect(getByText("no TARGET lane — press TARGET in a lane header")).toBeTruthy();
  });
});

describe("SEMITONE SET mode (spec §5.4)", () => {
  it("shows the twelve pitch classes, C first, with sharp spellings", () => {
    chromaTarget.setMode("set");
    const { container } = render(TargetRow);
    const labels = [...container.querySelectorAll("[data-chroma-key]")].map((k) => k.textContent);
    expect(labels).toEqual(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]);
  });

  it("toggles a key through the store, not through local state", async () => {
    chromaTarget.setMode("set");
    const { container } = render(TargetRow);
    const e = container.querySelector('[data-chroma-key="4"]')!;
    await fireEvent.click(e);
    expect(chromaTarget.keys[4]).toBe(true);
  });

  it("fills the key row from a chord symbol (v3 323)", async () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    await fireEvent.input(getByTestId("chroma-chord"), { target: { value: "F#m" } });
    expect(chromaTarget.keys[6]).toBe(true);
    expect(chromaTarget.keys[9]).toBe(true);
    expect(chromaTarget.keys[1]).toBe(true);
  });

  it("lists the selected classes beside the field, or says there are none", async () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    expect(getByTestId("chroma-chord-hint").textContent).toBe("no classes selected");
    await fireEvent.input(getByTestId("chroma-chord"), { target: { value: "C" } });
    expect(getByTestId("chroma-chord-hint").textContent).toBe("C E G");
  });

  it("marks an unrecognised chord rather than silently ignoring it", async () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    await fireEvent.input(getByTestId("chroma-chord"), { target: { value: "Hmaj9" } });
    expect(getByTestId("chroma-chord").getAttribute("aria-invalid")).toBe("true");
  });
});
