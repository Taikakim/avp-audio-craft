// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import AdapterMixTab from "../AdapterMixTab.svelte";

afterEach(cleanup);
beforeEach(() => {
  view.setActiveLane(0);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
});

describe("ADAPTER MIX tab", () => {
  it("says what is missing when the lane has no adapter on", () => {
    render(AdapterMixTab);
    expect(screen.getByTestId("adapter-missing").textContent).toMatch(/LORA \/ DORA/);
  });

  it("ADVANCED FX creates a flat amount curve on the active lane's chain, in place", async () => {
    arrangement.lanes[0].chain.lora_on = true;
    arrangement.lanes[0].chain.lora.ckpt_path = "/a.ckpt";
    const before = arrangement.lanes[0].chain;
    render(AdapterMixTab);
    await fireEvent.click(screen.getByTestId("adapter-fx-toggle"));
    expect(arrangement.lanes[0].chain).toBe(before);
    expect(arrangement.lanes[0].chain.lora.blend).toEqual({ on: true, mode: "amount", curve: Array(24).fill(1) });
  });

  it("a shape and a transform rewrite the curve", async () => {
    arrangement.lanes[0].chain.lora = { ckpt_path: "/a.ckpt", slot: null, strength: 1,
      blend: { on: true, mode: "amount", curve: Array(24).fill(1) } };
    arrangement.lanes[0].chain.lora_on = true;
    render(AdapterMixTab);
    await fireEvent.change(screen.getByTestId("adapter-shape"), { target: { value: "last8_off" } });
    expect(arrangement.lanes[0].chain.lora.blend!.curve.slice(16)).toEqual(Array(8).fill(0));
    await fireEvent.click(screen.getByTestId("adapter-invert"));
    expect(arrangement.lanes[0].chain.lora.blend!.curve[0]).toBe(0);
  });

  it("follows the active lane", async () => {
    arrangement.lanes[1].chain.lora_on = true;
    arrangement.lanes[1].chain.lora = { ckpt_path: "/b.ckpt", slot: null, strength: 1,
      blend: { on: true, mode: "direction", curve: Array(24).fill(0.5) } };
    render(AdapterMixTab);
    view.setActiveLane(1);
    await tick();
    expect((screen.getByTestId("adapter-mode") as HTMLSelectElement).value).toBe("direction");
    expect(screen.getByTestId("curve-col-0").getAttribute("data-value")).toBe("0.5");
  });
});
