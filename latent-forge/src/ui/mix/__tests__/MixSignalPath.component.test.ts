// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MASTER_DEFAULT, MIX_DEFAULT } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { forgeApi } from "../../../lib/forge/api";
import { HELP } from "../../../lib/help/strings";
import { jobs } from "../../../lib/render/jobs.svelte";
import * as mixdownModule from "../../../lib/render/mixdown.svelte";
import MixSignalPath from "../MixSignalPath.svelte";

const REF = { kind: "upload", sha256: "a".repeat(64) } as const;

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

beforeEach(() => {
  arrangement.mix = structuredClone(MIX_DEFAULT);
  arrangement.master = structuredClone(MASTER_DEFAULT);
  arrangement.clips.splice(0, arrangement.clips.length);
});

describe("MIX ORDER", () => {
  it("defaults to the tree label and shows three node boxes", async () => {
    render(MixSignalPath);
    const select = await screen.findByLabelText("MIX ORDER");
    expect(select).toHaveValue("tree");
    expect(screen.getAllByText("LERP")).toHaveLength(3);
    expect(screen.getAllByText("SLERP")).toHaveLength(3);
  });

  it("switching to quad shows four weight sliders instead of node boxes", async () => {
    render(MixSignalPath);
    const select = await screen.findByLabelText("MIX ORDER");
    await fireEvent.change(select, { target: { value: "quad" } });
    expect(arrangement.mix.order).toBe("quad");
    expect(screen.queryAllByText("LERP")).toHaveLength(0);
    expect(screen.getAllByLabelText(/quad weight/i)).toHaveLength(4);
  });

  it("a node's T slider writes MixSpec.nodes[id].t in place", async () => {
    render(MixSignalPath);
    const t = await screen.findByLabelText("M1 position");
    await fireEvent.input(t, { target: { value: "0.25" } });
    expect(arrangement.mix.nodes.M1.t).toBe(0.25);
  });

  it("LERP/SLERP set a node's interp in place", async () => {
    render(MixSignalPath);
    await fireEvent.click(await screen.findByTestId("m1-lerp"));
    expect(arrangement.mix.nodes.M1.interp).toBe("lerp");
    await fireEvent.click(await screen.findByTestId("m1-slerp"));
    expect(arrangement.mix.nodes.M1.interp).toBe("slerp");
  });
});

describe("fold / expand (spec 4.5's own summary row)", () => {
  it("toggling the fold button switches to the one-line summary, and expand switches back", async () => {
    render(MixSignalPath);
    await fireEvent.click(await screen.findByTestId("mix-fold"));
    expect(screen.queryByLabelText("MIX ORDER")).toBeNull();
    expect(await screen.findByText("MIX + SIGNAL PATH")).toBeTruthy();
    await fireEvent.click(await screen.findByTestId("mix-expand"));
    expect(await screen.findByLabelText("MIX ORDER")).toBeTruthy();
  });
});

describe("SIGNAL PATH", () => {
  it("lists the nine stages live, and lights LANE CHAINS with the idle note when a chain is on with no A2A clip", async () => {
    arrangement.lanes[0].chain.latch_on = true;
    render(MixSignalPath);
    const row = await screen.findByText("LANE CHAINS");
    expect(row.closest("[data-signal-stage]")).toHaveAttribute("data-lit", "true");
    expect(await screen.findByText("chain idle — no A2A clip in lane")).toBeTruthy();
  });
});

describe("▸ MIXDOWN — UI only this milestone", () => {
  it("is clickable and calls no job submission (M9's boundary, same as OVERLAP-INPAINT's render button)", async () => {
    const spy = vi.spyOn(forgeApi, "submitJob");
    render(MixSignalPath);
    await fireEvent.click((await screen.findAllByText("▸ MIXDOWN"))[0]);
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("HELP ids", () => {
  it("attaches the three new mix-control ids", async () => {
    render(MixSignalPath);
    const { HELP } = await import("../../../lib/help/strings");
    await fireEvent.change(await screen.findByLabelText("MIX ORDER"), { target: { value: "quad" } });
    expect((await screen.findAllByLabelText(/quad weight/i))[0].getAttribute("data-help")).toBe(HELP.mixQuadWeight);
    await fireEvent.change(await screen.findByLabelText("MIX ORDER"), { target: { value: "tree" } });
    expect((await screen.findByTestId("m1-lerp")).getAttribute("data-help")).toBe(HELP.mixLerp);
    expect((await screen.findByTestId("m1-slerp")).getAttribute("data-help")).toBe(HELP.mixSlerp);
  });
});

describe("the MIX-tab MIXDOWN buttons (M9 T4)", () => {
  it("carry a testid and the MIXDOWN help id, not HELP.renderButton", () => {
    const { getByTestId } = render(MixSignalPath, { props: {} });
    const button = getByTestId("mix-mixdown");
    expect(button.getAttribute("data-help")).toBe(HELP.mixdownButton);
    expect(button.getAttribute("data-help")).not.toBe(HELP.renderButton);
  });

  it("run the same commit action as the top bar's button", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
    const run = vi.spyOn(mixdownModule, "runMixdown").mockResolvedValue(undefined);
    const { getByTestId } = render(MixSignalPath, { props: {} });
    (getByTestId("mix-mixdown") as HTMLButtonElement).click();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("read SAMPLING · N steps left while a commit runs, like the top bar's", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
    jobs.active = { forgeJobId: "forge-1", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mixdown", progress: null };
    jobs.active.progress = { job_id: "forge-1", op: "commit", stage: "MIX", stage_index: 7, stage_count: 9, step: 0, steps: 0, steps_left_total: 12, steps_total: 24 };
    const { getByTestId } = render(MixSignalPath, { props: {} });
    expect(getByTestId("mix-mixdown").textContent?.trim()).toBe("SAMPLING · 12 steps left");
  });
});
