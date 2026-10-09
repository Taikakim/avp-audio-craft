// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MASTER_DEFAULT } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import * as latch from "../../../lib/chains/latch";
import MasterChain from "../MasterChain.svelte";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

beforeEach(() => {
  arrangement.master = structuredClone(MASTER_DEFAULT);
  vi.spyOn(latch, "fetchLatchHeads").mockResolvedValue({
    chroma_other: { name: "chroma_other", family: "chroma", default_gain: 2048, health: "ok",
      supports_kinds: ["constant"], slider_min: 0, slider_max: 1, value_default: 0.5 },
  });
});

describe("MASTER CHAIN (spec §4.6.5)", () => {
  it("shows the applied-after-the-lane-chains note verbatim", async () => {
    render(MasterChain);
    expect(await screen.findByText("applied to the mixed latent, after the lane chains")).toBeTruthy();
  });

  it("toggling LATCH HEAD mutates arrangement.master.latch_on in place", async () => {
    render(MasterChain);
    const before = arrangement.master;
    await fireEvent.click(await screen.findByTestId("master-latch-toggle"));
    expect(arrangement.master.latch_on).toBe(true);
    expect(arrangement.master).toBe(before);
  });

  it("the head select lists /info.latch_heads and writes arrangement.master.head", async () => {
    render(MasterChain);
    const select = await screen.findByLabelText("MASTER LATCH HEAD");
    // wait for the fetched option -- the select renders before the heads resolve
    await screen.findByRole("option", { name: "chroma_other · chroma" });
    await fireEvent.change(select, { target: { value: "chroma_other" } });
    expect(arrangement.master.head).toBe("chroma_other");
  });

  it("GAIN drags over 0-120 with default 64", async () => {
    render(MasterChain);
    const gain = await screen.findByLabelText("GAIN");
    expect(gain).toHaveValue(64);                       // the text field beside the slider
    await fireEvent.input(gain, { target: { value: "80" } });
    expect(arrangement.master.gain).toBe(80);
  });

  it("LATENT NORMALISE defaults on and toggles off", async () => {
    render(MasterChain);
    expect(arrangement.master.norm_on).toBe(true);
    await fireEvent.click(await screen.findByTestId("master-norm-toggle"));
    expect(arrangement.master.norm_on).toBe(false);
  });

  it("attaches HELP.latentNormalise to the existing label, and the three new ids to the new controls", async () => {
    render(MasterChain);
    const { HELP } = await import("../../../lib/help/strings");
    expect((await screen.findByText("LATENT NORMALISE")).getAttribute("data-help")).toBe(HELP.latentNormalise);
    expect((await screen.findByTestId("master-latch-toggle")).getAttribute("data-help")).toBe(HELP.masterLatchToggle);
    expect((await screen.findByLabelText("MASTER LATCH HEAD")).getAttribute("data-help")).toBe(HELP.masterHead);
    expect((await screen.findByLabelText("GAIN")).getAttribute("data-help")).toBe(HELP.masterGain);
  });
});
