// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { MIXDOWN_IDLE_LABEL, mixdownLabel } from "../mixdown";
import MixdownSlot from "../MixdownSlot.svelte";

afterEach(() => cleanup());

describe("mixdownLabel is the copy M9 will switch between (spec §4.2)", () => {
  it("is ▸ MIXDOWN while idle", () => {
    expect(mixdownLabel(false, null)).toBe("▸ MIXDOWN");
    expect(MIXDOWN_IDLE_LABEL).toBe("▸ MIXDOWN");
  });

  it("counts the remaining steps while a commit runs", () => {
    expect(mixdownLabel(true, 44)).toBe("SAMPLING · 44 steps left");
    expect(mixdownLabel(true, null)).toBe("SAMPLING · 0 steps left");
  });
});

describe("the M1 MIXDOWN slot is a measurable, disabled frame", () => {
  it("renders the idle copy with every control disabled", () => {
    const { getByTestId } = render(MixdownSlot, { props: {} });
    const button = getByTestId("mixdown-button") as HTMLButtonElement;
    expect(button.textContent?.trim()).toBe("▸ MIXDOWN");
    expect(button.disabled).toBe(true);
    expect((getByTestId("mixdown-play") as HTMLButtonElement).disabled).toBe(true);
  });

  it("gives the waveform its 220×26 backing store (spec §4.2)", () => {
    const { getByTestId } = render(MixdownSlot, { props: {} });
    const canvas = getByTestId("mixdown-canvas") as HTMLCanvasElement;
    expect(canvas.width).toBe(220);
    expect(canvas.height).toBe(26);
    expect(canvas.draggable).toBe(false);
  });
});
