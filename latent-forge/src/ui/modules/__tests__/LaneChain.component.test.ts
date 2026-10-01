// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import { forgeApi } from "../../../lib/forge/api";
import * as models from "../../../lib/forge/models";
import * as latch from "../../../lib/chains/latch";
import LaneChain from "../LaneChain.svelte";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

beforeEach(() => {
  view.setActiveLane(0);
  // every lane, not just lane 0: two tests below assert on lane 1 staying default
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  vi.spyOn(latch, "fetchLatchHeads").mockResolvedValue({
    rms_energy_bass: { name: "rms_energy_bass", family: "medium", default_gain: 512, health: "ok",
      supports_kinds: ["constant", "beat_grid"], slider_min: -35.2, slider_max: -0.13, value_default: -12 },
  });
  vi.spyOn(models, "fetchFilmCkpts").mockResolvedValue([]);
  vi.spyOn(models, "fetchSlots").mockResolvedValue({ ok: true, active: null, backbone: null, slots: [], max_slots: 4, vram_floor_gb: 6, free_gb: 9 });
  vi.spyOn(models, "fetchAdapters").mockResolvedValue([{ path: "/SERVER/lora1.safetensors", name: "lora1" }]);
  vi.spyOn(forgeApi, "presets").mockResolvedValue({ ok: true, names: [] });
  // The component calls forgeApi.info() itself (FILM's /info.film_default fallback). Unmocked, a
  // relative fetch("/info") rejects in jsdom and vitest fails the run on the unhandled rejection
  // even when every assertion passed -- so it is stubbed for every test, and the component
  // .catch()es it besides.
  vi.spyOn(forgeApi, "info").mockResolvedValue({ ok: true });
});

describe("LATCH GUIDANCE toggle", () => {
  it("mutates arrangement.lanes[activeLane].chain.latch_on in place, not by reassigning chain", async () => {
    render(LaneChain);
    const before = arrangement.lanes[0].chain;
    await fireEvent.click(await screen.findByTestId("latch-toggle"));
    expect(arrangement.lanes[0].chain.latch_on).toBe(true);
    expect(arrangement.lanes[0].chain).toBe(before); // same object, mutated -- not replaced
  });
});

describe("LatCH slot fields write through the live chain", () => {
  it("writing WEIGHT sets chain.slots[0].weight", async () => {
    render(LaneChain);
    const weight = await screen.findByLabelText("WEIGHT — slot 1");
    await fireEvent.input(weight, { target: { value: "5" } });
    expect(arrangement.lanes[0].chain.slots[0].weight).toBe(5);
  });

  it("writing the head select sets chain.slots[0].head from the fetched /info.latch_heads list", async () => {
    render(LaneChain);
    const head = await screen.findByLabelText("HEAD — slot 1");
    // The select exists before the heads arrive; wait for the option itself, or the change below
    // sets a value no <option> has and the select falls back to "".
    await screen.findAllByRole("option", { name: "rms_energy_bass · medium" });
    await fireEvent.change(head, { target: { value: "rms_energy_bass" } });
    expect(arrangement.lanes[0].chain.slots[0].head).toBe("rms_energy_bass");
  });

  it("choosing a head starts TARGET at head.value_default and ranges it over slider_min..slider_max (spec 5.5)", async () => {
    render(LaneChain);
    const head = await screen.findByLabelText("HEAD — slot 1");
    await screen.findAllByRole("option", { name: "rms_energy_bass · medium" });
    await fireEvent.change(head, { target: { value: "rms_energy_bass" } });
    expect(arrangement.lanes[0].chain.slots[0].value).toBe(-12);
    const target = (await screen.findByLabelText("TARGET — slot 1")) as HTMLInputElement;
    expect(target.min).toBe("-35.2");
    expect(target.max).toBe("-0.13");
    // a fractional step, not the browser's default of 1 -- chroma_other's [0, 1] range would
    // otherwise allow only 0 or 1
    expect(Number(target.step)).toBeLessThan(1);
  });

  it("the beat_grid kind turns TARGET into a 60-200 BPM slider (spec 5.5)", async () => {
    render(LaneChain);
    const head = await screen.findByLabelText("HEAD — slot 1");
    await screen.findAllByRole("option", { name: "rms_energy_bass · medium" });
    await fireEvent.change(head, { target: { value: "rms_energy_bass" } });
    const kind = await screen.findByLabelText("KIND — slot 1");
    await screen.findAllByRole("option", { name: "beat_grid" });
    await fireEvent.change(kind, { target: { value: "beat_grid" } });
    expect(arrangement.lanes[0].chain.slots[0].kind).toBe("beat_grid");
    const target = (await screen.findByLabelText("TARGET — slot 1")) as HTMLInputElement;
    expect(target.min).toBe("60");
    expect(target.max).toBe("200");
    expect(arrangement.lanes[0].chain.slots[0].value).toBeGreaterThanOrEqual(60);
    expect(arrangement.lanes[0].chain.slots[0].value).toBeLessThanOrEqual(200);
  });
});

describe("FILM", () => {
  it("toggling FILM sets chain.film_on", async () => {
    render(LaneChain);
    await fireEvent.click(await screen.findByTestId("film-toggle"));
    expect(arrangement.lanes[0].chain.film_on).toBe(true);
  });

  it("SCALE writes chain.film.gain over its 0-2 range", async () => {
    render(LaneChain);
    const scale = await screen.findByLabelText("FILM SCALE");
    await fireEvent.input(scale, { target: { value: "1.5" } });
    expect(arrangement.lanes[0].chain.film.gain).toBe(1.5);
  });

  it("falls back to /info.film_default when the control_adapter/scalar list is empty", async () => {
    // A non-null default ckpt, so the assertion can only pass if the component actually read
    // /info.film_default -- chain.film.ckpt is null by default, so checking the select's value
    // alone would pass with or without the fallback.
    vi.spyOn(forgeApi, "info").mockResolvedValue({ ok: true, film_default: { ckpt: "/SERVER/film_default.ckpt", gain: 1.75 } });
    render(LaneChain);
    const ckpt = await screen.findByLabelText("FILM CKPT");
    expect(await screen.findByRole("option", { name: "server default (/SERVER/film_default.ckpt)" })).toBeTruthy();
    expect(ckpt).toHaveValue(""); // null ckpt -> the "server default" option, not a blank/broken select
  });
});

describe("LORA / DORA", () => {
  it("tries fetchSlots() before fetchAdapters() for the model list", async () => {
    vi.spyOn(models, "fetchSlots").mockResolvedValue({
      ok: true, active: 0, backbone: "medium-base",
      slots: [{ index: 0, path: "/SERVER/resident.safetensors", label: "resident", family: "adapter", cost_gb: 1, strength: 1 }],
      max_slots: 4, vram_floor_gb: 6, free_gb: 9,
    });
    render(LaneChain);
    const model = (await screen.findByLabelText("LORA / DORA MODEL")) as HTMLSelectElement;
    // options arrive one or two promise hops after the select renders -- wait for the last one
    await screen.findByRole("option", { name: "lora1" });
    const options = Array.from(model.options).map((o) => o.textContent);
    // an explicit "none" first (ckpt_path null must not display as the first adapter), then the
    // resident slot, then the /models adapter fallback
    expect(options).toEqual(["none", "resident", "lora1"]);
    expect(model).toHaveValue("");
    // picking a resident slot records its slot index as well as its path (LaneChain.lora.slot, M1 T3)
    await fireEvent.change(model, { target: { value: "/SERVER/resident.safetensors" } });
    expect(arrangement.lanes[0].chain.lora.ckpt_path).toBe("/SERVER/resident.safetensors");
    expect(arrangement.lanes[0].chain.lora.slot).toBe(0);
    // an adapter that is not resident clears it again
    await fireEvent.change(model, { target: { value: "/SERVER/lora1.safetensors" } });
    expect(arrangement.lanes[0].chain.lora.slot).toBeNull();
  });

  it("SCALE writes chain.lora.strength over its 0-1 range", async () => {
    render(LaneChain);
    const scale = await screen.findByLabelText("LORA / DORA SCALE");
    await fireEvent.input(scale, { target: { value: "0.4" } });
    expect(arrangement.lanes[0].chain.lora.strength).toBe(0.4);
  });
});

describe("BUNGEE", () => {
  it("SEMITONES drag-scales chain.semitones over its +/-24 range", async () => {
    render(LaneChain);
    const semis = await screen.findByLabelText("SEMITONES");
    await fireEvent.change(semis, { target: { value: "-7" } });
    expect(arrangement.lanes[0].chain.semitones).toBe(-7);
  });

  it("ships an undrawn module preset select for the bungee level (spec 9.3's fourth, undrawn, level)", async () => {
    render(LaneChain);
    expect(await screen.findByLabelText("BUNGEE preset")).toBeTruthy();
  });
});

describe("module presets — direct forgeApi calls, no intermediate client", () => {
  it("LATCH GUIDANCE's preset select lists forgeApi.presets('latch')", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "latch" ? { ok: true, names: ["dub"] } : { ok: true, names: [] });
    render(LaneChain);
    expect(await screen.findByText("dub")).toBeTruthy();
  });

  it("choosing a saved latch preset applies it to the active lane via forgeApi.preset('latch', name)", async () => {
    // Only the latch level lists "dub": mocked for all four levels it would be four options.
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "latch" ? { ok: true, names: ["dub"] } : { ok: true, names: [] });
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ latch_on: true, slots: CHAIN_DEFAULTS.slots, hparams: CHAIN_DEFAULTS.hparams });
    render(LaneChain);
    const select = await screen.findByLabelText("LATCH GUIDANCE preset");
    await screen.findByRole("option", { name: "dub" }); // wait for the option, not just the select
    await fireEvent.change(select, { target: { value: "dub" } });
    expect(forgeApi.preset).toHaveBeenCalledWith("latch", "dub");
    await waitFor(() => expect(arrangement.lanes[0].chain.latch_on).toBe(true));
    expect(arrangement.lanes[1].chain.latch_on).toBe(false); // spec 9.3: recall applies to the active lane only
  });

  it("SAVE writes the active lane's latch slice -- including latch_on -- through forgeApi.savePreset", async () => {
    const save = vi.spyOn(forgeApi, "savePreset").mockResolvedValue({ ok: true });
    vi.spyOn(window, "prompt").mockReturnValue("my-latch");
    arrangement.lanes[0].chain.latch_on = true;
    arrangement.lanes[0].chain.hparams.rho = 7;
    render(LaneChain);
    await fireEvent.click(await screen.findByTestId("latch-preset-save"));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    const [level, name, payload] = save.mock.calls[0];
    expect(level).toBe("latch");
    expect(name).toBe("my-latch");
    expect(payload).toEqual({
      latch_on: true,
      slots: JSON.parse(JSON.stringify(arrangement.lanes[0].chain.slots)),
      hparams: { ...CHAIN_DEFAULTS.hparams, rho: 7 },
    });
  });

  it("DEL deletes the selected module preset through forgeApi.deletePreset and drops it from the list", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "film" ? { ok: true, names: ["tight"] } : { ok: true, names: [] });
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ film_on: true, film: CHAIN_DEFAULTS.film });
    const del = vi.spyOn(forgeApi, "deletePreset").mockResolvedValue({ ok: true });
    render(LaneChain);
    const select = await screen.findByLabelText("FILM preset");
    await screen.findByRole("option", { name: "tight" });
    await fireEvent.change(select, { target: { value: "tight" } });
    await fireEvent.click(await screen.findByTestId("film-preset-delete"));
    await waitFor(() => expect(del).toHaveBeenCalledWith("film", "tight"));
    await waitFor(() => expect(screen.queryByRole("option", { name: "tight" })).toBeNull());
  });

  it("the picked preset belongs to the lane it was picked on: another lane shows none, and SAVE there asks for a new name", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "latch" ? { ok: true, names: ["dub"] } : { ok: true, names: [] });
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ latch_on: true, slots: CHAIN_DEFAULTS.slots, hparams: CHAIN_DEFAULTS.hparams });
    const save = vi.spyOn(forgeApi, "savePreset").mockResolvedValue({ ok: true });
    const prompt = vi.spyOn(window, "prompt").mockReturnValue(null);   // the user cancels the name prompt
    render(LaneChain);
    const select = await screen.findByLabelText("LATCH GUIDANCE preset");
    await screen.findByRole("option", { name: "dub" });
    await fireEvent.change(select, { target: { value: "dub" } });
    await waitFor(() => expect(arrangement.lanes[0].chain.latch_on).toBe(true));
    view.setActiveLane(1);
    await waitFor(() => expect(select).toHaveValue(""));
    expect(screen.getByTestId("latch-preset-delete")).toBeDisabled();   // DEL cannot delete lane 1's non-pick
    await fireEvent.click(screen.getByTestId("latch-preset-save"));
    expect(prompt).toHaveBeenCalledTimes(1);   // a NEW name for lane 2 -- "dub" is never overwritten
    expect(save).not.toHaveBeenCalled();
    view.setActiveLane(0);
    await waitFor(() => expect(select).toHaveValue("dub"));
  });

  it("a recall still in flight when the active lane changes lands in the lane it was picked on", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "latch" ? { ok: true, names: ["dub"] } : { ok: true, names: [] });
    let answer!: (payload: Record<string, unknown>) => void;
    vi.spyOn(forgeApi, "preset").mockImplementation(() => new Promise((resolve) => (answer = resolve)));
    render(LaneChain);
    const select = await screen.findByLabelText("LATCH GUIDANCE preset");
    await screen.findByRole("option", { name: "dub" });
    await fireEvent.change(select, { target: { value: "dub" } });
    view.setActiveLane(1);   // switch lanes BEFORE the preset arrives
    answer({ latch_on: true, slots: CHAIN_DEFAULTS.slots, hparams: CHAIN_DEFAULTS.hparams });
    await waitFor(() => expect(arrangement.lanes[0].chain.latch_on).toBe(true));
    expect(arrangement.lanes[1].chain.latch_on).toBe(false);
  });
});

describe("following the active lane", () => {
  it("switching view.activeLane switches which lane's chain the module edits", async () => {
    arrangement.lanes[1].chain.latch_on = true;
    render(LaneChain);
    view.setActiveLane(1);
    const toggle = await screen.findByTestId("latch-toggle");
    expect(toggle).toHaveClass("on");
  });
});

describe("HELP ids on the controls this task adds (docs/latent-forge/extract_help.mjs NEW_STRINGS)", () => {
  it("attaches HELP.filmScale, .filmCkpt, .loraScale, .bungeePreset, .modulePresetSave and .modulePresetDelete", async () => {
    render(LaneChain);
    const { HELP } = await import("../../../lib/help/strings");
    expect((await screen.findByLabelText("FILM SCALE")).getAttribute("data-help")).toBe(HELP.filmScale);
    expect((await screen.findByLabelText("FILM CKPT")).getAttribute("data-help")).toBe(HELP.filmCkpt);
    expect((await screen.findByLabelText("LORA / DORA SCALE")).getAttribute("data-help")).toBe(HELP.loraScale);
    expect((await screen.findByLabelText("BUNGEE preset")).getAttribute("data-help")).toBe(HELP.bungeePreset);
    expect((await screen.findByTestId("bungee-preset-save")).getAttribute("data-help")).toBe(HELP.modulePresetSave);
    expect((await screen.findByTestId("bungee-preset-delete")).getAttribute("data-help")).toBe(HELP.modulePresetDelete);
  });
});
