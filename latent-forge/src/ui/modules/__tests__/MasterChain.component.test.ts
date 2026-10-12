// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS, MASTER_DEFAULT } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { HELP } from "../../../lib/help/strings";
import * as latch from "../../../lib/chains/latch";
import LatchGuidance from "../LatchGuidance.svelte";
import MasterChain from "../MasterChain.svelte";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const HARDNESS = {
  name: "hardness", family: "medium", default_gain: 512, health: "ok",
  supports_kinds: ["constant", "ramp_up", "ramp_down"], slider_min: 59.2, slider_max: 73.2, value_default: 66.2,
  std_mean: 66.2, std_std: 3.5, usable_max_gain: 128, usable_max_weight: 0.25,
};
const CHROMA = {
  name: "chroma_other", family: "chroma", default_gain: 2048, health: "ok",
  supports_kinds: ["constant"], slider_min: 0, slider_max: 1, value_default: 0.5,
};

beforeEach(() => {
  arrangement.master = structuredClone(MASTER_DEFAULT);
  vi.spyOn(latch, "fetchLatchHeads").mockResolvedValue({ chroma_other: CHROMA, hardness: HARDNESS });
});

async function pickHead(slot: number, name: string, family: string) {
  const head = await screen.findByLabelText(`MASTER HEAD — slot ${slot}`);
  await screen.findAllByRole("option", { name: `${name} · ${family}` });
  await fireEvent.change(head, { target: { value: name } });
}

describe("MASTER CHAIN (spec §4.6.5)", () => {
  it("shows the applied-after-the-lane-chains note verbatim", async () => {
    render(MasterChain);
    expect(await screen.findByText("applied to the mixed latent, after the lane chains")).toBeTruthy();
  });

  it("toggling LATCH GUIDANCE mutates arrangement.master.latch_on in place", async () => {
    render(MasterChain);
    const before = arrangement.master;
    await fireEvent.click(await screen.findByTestId("master-latch-toggle"));
    expect(arrangement.master.latch_on).toBe(true);
    expect(arrangement.master).toBe(before);
  });

  it("has the lane's two slots: each lists /info.latch_heads and writes arrangement.master.slots", async () => {
    render(MasterChain);
    await pickHead(1, "chroma_other", "chroma");
    await pickHead(2, "hardness", "medium");
    expect(arrangement.master.slots[0].head).toBe("chroma_other");
    expect(arrangement.master.slots[1].head).toBe("hardness");
  });

  it("has the lane's per-slot fields and hyperparameters, written into the master", async () => {
    render(MasterChain);
    await pickHead(1, "hardness", "medium");
    await fireEvent.input(await screen.findByLabelText("MASTER TARGET — slot 1"), { target: { value: "70" } });
    await fireEvent.input(await screen.findByLabelText("MASTER WEIGHT — slot 1"), { target: { value: "0.2" } });
    await fireEvent.input(await screen.findByLabelText("MASTER START % — slot 1"), { target: { value: "10" } });
    await fireEvent.input(await screen.findByLabelText("MASTER END % — slot 1"), { target: { value: "50" } });
    await fireEvent.input(await screen.findByLabelText("MASTER ρ VARIANCE"), { target: { value: "2" } });
    await fireEvent.input(await screen.findByLabelText("MASTER μ MEAN"), { target: { value: "3" } });
    await fireEvent.input(await screen.findByLabelText("MASTER γ NOISE"), { target: { value: "0.5" } });
    await fireEvent.input(await screen.findByLabelText("MASTER MEAN ITER"), { target: { value: "9" } });
    const m = arrangement.master;
    expect(m.slots[0]).toMatchObject({ head: "hardness", value: 70, weight: 0.2, start_pct: 0.1, end_pct: 0.5 });
    expect(m.hparams).toMatchObject({ rho: 2, mu: 3, gamma: 0.5, n_iter: 9 });
  });

  it("takes a ramp with two ends, and the hardness weight limit, exactly as a lane does", async () => {
    render(MasterChain);
    await pickHead(1, "hardness", "medium");
    expect(arrangement.master.slots[0].weight).toBe(0.25);
    const kind = await screen.findByLabelText("MASTER KIND — slot 1");
    await screen.findAllByRole("option", { name: "ramp_up" });
    await fireEvent.change(kind, { target: { value: "ramp_up" } });
    expect(arrangement.master.slots[0].value_from).toBeCloseTo(62.7, 5);
    expect(arrangement.master.slots[0].value).toBeCloseTo(69.7, 5);
    expect(await screen.findByLabelText("MASTER FROM — slot 1")).toBeTruthy();
  });

  it("NOISE is the master's own: how deep the guided pass re-noises the mix", async () => {
    render(MasterChain);
    const noise = (await screen.findByLabelText("MASTER LATCH NOISE")) as HTMLInputElement;
    expect(noise.value).toBe("0.25");
    await fireEvent.input(noise, { target: { value: "0.4" } });
    expect(arrangement.master.noise).toBe(0.4);
    expect(noise.getAttribute("data-help")).toBe(HELP.masterNoise);
  });

  it("LATENT NORMALISE defaults on and toggles off", async () => {
    render(MasterChain);
    expect(arrangement.master.norm_on).toBe(true);
    await fireEvent.click(await screen.findByTestId("master-norm-toggle"));
    expect(arrangement.master.norm_on).toBe(false);
  });

  it("attaches HELP.latentNormalise to the existing label, and the toggle's help to the toggle", async () => {
    render(MasterChain);
    expect((await screen.findByText("LATENT NORMALISE")).getAttribute("data-help")).toBe(HELP.latentNormalise);
    expect((await screen.findByTestId("master-latch-toggle")).getAttribute("data-help")).toBe(HELP.masterLatchToggle);
  });
});

describe("one LatCH paradigm for the lane and the master", () => {
  /** Every accessible name the component puts on a control. */
  function names(): string[] {
    return [...document.querySelectorAll("[aria-label]")].map((e) => e.getAttribute("aria-label") as string).sort();
  }

  it("a lane's block and the master's block offer exactly the same controls", async () => {
    vi.mocked(latch.fetchLatchHeads).mockResolvedValue({ hardness: HARDNESS });
    render(LatchGuidance, {
      props: { block: structuredClone(CHAIN_DEFAULTS), toggleTestId: "latch-toggle", toggleHelp: "latchToggle" },
    });
    await screen.findAllByRole("option", { name: "hardness · medium" });
    const laneNames = names();
    cleanup();
    render(LatchGuidance, {
      props: {
        block: structuredClone(MASTER_DEFAULT), toggleTestId: "master-latch-toggle",
        toggleHelp: "masterLatchToggle", namePrefix: "MASTER ",
      },
    });
    await screen.findAllByRole("option", { name: "hardness · medium" });
    expect(names().map((n) => n.replace(/^MASTER /, ""))).toEqual(laneNames);
    expect(laneNames.length).toBeGreaterThan(20);        // two slots of ten names each (a slider and a text field each for four of them), and four hyperparameters
  });

  it("the prefix keeps two instances on screen apart", () => {
    render(LatchGuidance, {
      props: { block: structuredClone(CHAIN_DEFAULTS), toggleTestId: "a", toggleHelp: "latchToggle" },
    });
    render(LatchGuidance, {
      props: { block: structuredClone(MASTER_DEFAULT), toggleTestId: "b", toggleHelp: "masterLatchToggle", namePrefix: "MASTER " },
    });
    expect(screen.getByLabelText("HEAD — slot 1")).not.toBe(screen.getByLabelText("MASTER HEAD — slot 1"));
  });
});
