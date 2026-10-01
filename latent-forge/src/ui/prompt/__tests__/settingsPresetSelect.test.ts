// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { forgeApi } from "../../../lib/forge/api";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../../lib/forge/defaults";
import { settings } from "../../../lib/stores/settings.svelte";
import type { Target } from "../../../lib/forge/types";
import SettingsPresetSelect from "../SettingsPresetSelect.svelte";

const NONE: Target = { kind: "none" };

beforeEach(() => {
  // `settings` is a singleton shared by every suite in the run, and with no source
  // attached `{kind:"none"}` resolves to `session.defaults` -- so without this, one test's
  // applied preset is the next test's "before" value.
  settings.detach();
  settings.defaults = cloneRenderSettings(BASE_DEFAULTS);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SettingsPresetSelect", () => {
  it("lists both levels, prompt presets in their own group", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level: string) =>
      level === "render"
        ? { ok: true as const, names: ["warm pad"] }
        : { ok: true as const, names: ["bright"] },
    );
    render(SettingsPresetSelect, { props: { target: NONE } });
    expect(await screen.findByRole("option", { name: "warm pad" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "bright" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "prompt only" })).toBeTruthy();
  });

  it("applies the chosen render preset to the target's settings", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level: string) =>
      level === "render"
        ? { ok: true as const, names: ["warm pad"] }
        : { ok: true as const, names: [] },
    );
    // The payload itself -- `forgeApi.preset` returns Record<string, unknown> (M1 T5).
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ steps: 40, prompt: "from the preset" });
    render(SettingsPresetSelect, { props: { target: NONE } });
    const sel = await screen.findByLabelText("SETTINGS PRESET");
    // The options arrive asynchronously; a change to a value that is not an option yet is a no-op.
    await screen.findByRole("option", { name: "warm pad" });
    await fireEvent.change(sel, { target: { value: "render:warm pad" } });
    await vi.waitFor(() => expect(settings.current(NONE).steps).toBe(40));
    expect(settings.current(NONE).prompt).toBe("from the preset");
  });

  it("reports the fields a malformed preset could not supply, and changes nothing else", async () => {
    vi.spyOn(forgeApi, "presets").mockResolvedValue({ ok: true as const, names: ["bad"] });
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ steps: 9000 });
    const before = settings.current(NONE).steps;
    render(SettingsPresetSelect, { props: { target: NONE } });
    const sel = await screen.findByLabelText("SETTINGS PRESET");
    await screen.findAllByRole("option", { name: "bad" }); // mocked for both levels, so two
    await fireEvent.change(sel, { target: { value: "render:bad" } });
    expect(await screen.findByText(/ignored: steps/)).toBeTruthy();
    expect(settings.current(NONE).steps).toBe(before);
  });

  it("shows the server's message when the list cannot be read, and stays usable", async () => {
    vi.spyOn(forgeApi, "presets").mockRejectedValue(
      Object.assign(new Error("no presets dir"), { status: 404, message: "no presets dir" }),
    );
    render(SettingsPresetSelect, { props: { target: NONE } });
    expect(await screen.findByText(/no presets dir/)).toBeTruthy();
    expect(screen.getByLabelText("SETTINGS PRESET")).toBeTruthy();
  });
});
