// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TargetBar from "../TargetBar.svelte";

afterEach(() => cleanup());

const noop = () => {};

describe("TargetBar with nothing selected (spec 4.5)", () => {
  it("shows GENERATE and the session name, and no clip row", () => {
    const { getByTestId, queryByTestId } = render(TargetBar, {
      props: {
        target: { kind: "none" }, clipName: null, lane: 0 as const, a2a: null,
        clipHasLatent: false, onA2AToggle: noop, onNoise: noop, op: null, onOp: noop,
      },
    });
    expect(getByTestId("target-tag").textContent).toBe("GENERATE");
    expect(getByTestId("target-name").textContent).toBe("session");
    expect(queryByTestId("target-clip-row")).toBeNull();
  });

  it("renders the SETTINGS PRESET slot disabled with one dash option", () => {
    const { getByTestId } = render(TargetBar, {
      props: {
        target: { kind: "none" }, clipName: null, lane: 0 as const, a2a: null,
        clipHasLatent: false, onA2AToggle: noop, onNoise: noop, op: null, onOp: noop,
      },
    });
    const select = getByTestId("target-settings-preset") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    expect(select.options).toHaveLength(1);
    expect(select.options[0].value).toBe("");
    expect(select.getAttribute("aria-label")).toBe("SETTINGS PRESET");
  });
});

describe("TargetBar on an overlap", () => {
  it("shows INPAINT and the overlap key, and no clip row", () => {
    const { getByTestId, queryByTestId } = render(TargetBar, {
      props: {
        target: { kind: "overlap", key: "c1-c2" }, clipName: null, lane: 0 as const, a2a: null,
        clipHasLatent: false, onA2AToggle: noop, onNoise: noop, op: null, onOp: noop,
      },
    });
    expect(getByTestId("target-tag").textContent).toBe("INPAINT");
    expect(getByTestId("target-name").textContent).toBe("c1-c2");
    expect(queryByTestId("target-clip-row")).toBeNull();
  });
});

describe("TargetBar on a clip", () => {
  it("shows CLIP when a2a is off", () => {
    const { getByTestId } = render(TargetBar, {
      props: {
        target: { kind: "clip", id: "c1" }, clipName: "kick loop", lane: 2 as const,
        a2a: { on: false, noise: 0.4 }, clipHasLatent: true,
        onA2AToggle: noop, onNoise: noop, op: "generate", onOp: noop,
      },
    });
    expect(getByTestId("target-tag").textContent).toBe("CLIP");
    expect(getByTestId("target-name").textContent).toBe("kick loop");
  });

  it("shows A2A when a2a is on", () => {
    const { getByTestId } = render(TargetBar, {
      props: {
        target: { kind: "clip", id: "c1" }, clipName: "kick loop", lane: 2 as const,
        a2a: { on: true, noise: 0.4 }, clipHasLatent: true,
        onA2AToggle: noop, onNoise: noop, op: "generate", onOp: noop,
      },
    });
    expect(getByTestId("target-tag").textContent).toBe("A2A");
  });

  it("shows the A2A toggle, the NOISE field and the OP select", () => {
    const { getByTestId } = render(TargetBar, {
      props: {
        target: { kind: "clip", id: "c1" }, clipName: "kick loop", lane: 0 as const,
        a2a: { on: false, noise: 0.4 }, clipHasLatent: true,
        onA2AToggle: noop, onNoise: noop, op: "generate", onOp: noop,
      },
    });
    expect(getByTestId("target-clip-row")).toBeTruthy();
    expect(getByTestId("target-a2a-toggle").getAttribute("data-help")).toBeTruthy();
    expect((getByTestId("target-noise") as HTMLInputElement).value).toBe("0.4");
    expect(getByTestId("target-noise").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("target-op").getAttribute("data-help")).toBeTruthy();
  });

  it("clicking the A2A toggle calls onA2AToggle with the opposite of the current state", async () => {
    const onA2AToggle = vi.fn();
    const { getByTestId } = render(TargetBar, {
      props: {
        target: { kind: "clip", id: "c1" }, clipName: "kick loop", lane: 0 as const,
        a2a: { on: false, noise: 0.4 }, clipHasLatent: true,
        onA2AToggle, onNoise: noop, op: "generate", onOp: noop,
      },
    });
    await fireEvent.click(getByTestId("target-a2a-toggle"));
    expect(onA2AToggle).toHaveBeenCalledWith(true);
  });

  it("leaves every op selectable whatever clipHasLatent says — the spec's only op gate is RENDER's (M9)", () => {
    const { getByTestId } = render(TargetBar, {
      props: {
        target: { kind: "clip", id: "c1" }, clipName: "kick loop", lane: 0 as const,
        a2a: { on: false, noise: 0.4 }, clipHasLatent: false,
        onA2AToggle: noop, onNoise: noop, op: "decode", onOp: noop,
      },
    });
    const select = getByTestId("target-op") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value))
      .toEqual(["generate", "decode", "longform", "bend"]);
    expect(Array.from(select.options).every((o) => !o.disabled)).toBe(true);
  });

  it("changing the OP select calls onOp with the chosen value", async () => {
    const onOp = vi.fn();
    const { getByTestId } = render(TargetBar, {
      props: {
        target: { kind: "clip", id: "c1" }, clipName: "kick loop", lane: 0 as const,
        a2a: { on: false, noise: 0.4 }, clipHasLatent: true,
        onA2AToggle: noop, onNoise: noop, op: "generate", onOp,
      },
    });
    await fireEvent.change(getByTestId("target-op"), { target: { value: "bend" } });
    expect(onOp).toHaveBeenCalledWith("bend");
  });
});
