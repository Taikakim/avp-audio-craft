// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HELP } from "../../../lib/help/strings";
import TopBar from "../TopBar.svelte";

afterEach(() => cleanup());

const base = {
  view: "workspace" as const, onview: () => {}, helpMode: false, onhelp: () => {},
  theme: "light" as const, ontheme: () => {},
};
const SESSIONS = [{ name: "take1", updated: 1, n_clips: 2 }];

describe("TopBar.svelte after M7 T9 (spec §9.2/§9.3)", () => {
  it("has no SAVE/LOAD project buttons left (M1 T15's temporary pair is removed)", () => {
    const { queryByTestId } = render(TopBar, { props: base });
    expect(queryByTestId("save-project")).toBeNull();
    expect(queryByTestId("load-project")).toBeNull();
  });

  it("the SESSION select shows `unsaved` until a session is named, then drops it", async () => {
    const { getByTestId, queryByRole, rerender } = render(TopBar, { props: { ...base, sessions: SESSIONS, session: "" } });
    const select = getByTestId("session-select") as HTMLSelectElement;
    expect(queryByRole("option", { name: "unsaved" })).not.toBeNull();
    expect(select.value).toBe("");
    await rerender({ ...base, sessions: SESSIONS, session: "take1" });
    expect(queryByRole("option", { name: "unsaved" })).toBeNull();
    expect(select.value).toBe("take1");
  });

  it("a pick leaves the select on the committed session (and master preset) until the parent changes it (a failed load never shows the picked name)", async () => {
    const onsession = vi.fn();
    const onmasterpreset = vi.fn();
    const two = [...SESSIONS, { name: "take2", updated: 2, n_clips: 1 }];
    const presets = { masterPresets: ["live A", "live B"], masterPreset: "live A", onmasterpreset };
    const { getByTestId, rerender } = render(TopBar, { props: { ...base, ...presets, sessions: two, session: "take1", onsession } });
    const select = getByTestId("session-select") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "take2" } });
    expect(onsession).toHaveBeenCalledWith("take2");
    expect(select.value).toBe("take1");   // take2 is not loaded yet -- maybe never
    await rerender({ ...base, ...presets, sessions: two, session: "take2", onsession });
    expect(select.value).toBe("take2");   // the controller committed it (step 9)
    // the MASTER PRESET select follows the same rule: highlighted only once the recall applied (critic pass 3 #2)
    const preset = getByTestId("master-preset-select") as HTMLSelectElement;
    await fireEvent.change(preset, { target: { value: "live B" } });
    expect(onmasterpreset).toHaveBeenCalledWith("live B");
    expect(preset.value).toBe("live A");
  });

  it("while a load is in flight it says which session is loading and disables SAVE; the select keeps the committed name (critic pass 3 #11)", async () => {
    const { getByTestId, queryByTestId, rerender } = render(TopBar, {
      props: { ...base, sessions: SESSIONS, session: "take1", loadingName: "take2" },
    });
    expect(getByTestId("session-loading").textContent).toContain("loading take2");
    expect((getByTestId("session-save") as HTMLButtonElement).disabled).toBe(true);
    expect((getByTestId("session-select") as HTMLSelectElement).value).toBe("take1");
    await rerender({ ...base, sessions: SESSIONS, session: "take1", loadingName: "" });
    expect(queryByTestId("session-loading")).toBeNull();
    expect((getByTestId("session-save") as HTMLButtonElement).disabled).toBe(false);
  });

  it("calls onsessionsave from the session SAVE button, which carries HELP.sessionSave", async () => {
    const onsessionsave = vi.fn();
    const { getByTestId } = render(TopBar, { props: { ...base, sessions: SESSIONS, session: "take1", onsessionsave } });
    const btn = getByTestId("session-save");
    expect(btn.getAttribute("data-help")).toBe(HELP.sessionSave);
    await fireEvent.click(btn);
    expect(onsessionsave).toHaveBeenCalledTimes(1);
  });

  it("enables the master preset SAVE button, with HELP.masterPresetSave, and calls onmasterpresetsave", async () => {
    const onmasterpresetsave = vi.fn();
    const { getByTestId } = render(TopBar, { props: { ...base, masterPresets: ["live A"], masterPreset: "live A", onmasterpresetsave } });
    const btn = getByTestId("master-preset-save") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    expect(btn.getAttribute("data-help")).toBe(HELP.masterPresetSave);
    await fireEvent.click(btn);
    expect(onmasterpresetsave).toHaveBeenCalledTimes(1);
  });

  it("IMPORT hands the picked project file to onimportv1 (spec §9.2's v1 converter needs a way in)", async () => {
    const onimportv1 = vi.fn();
    const { getByTestId } = render(TopBar, { props: { ...base, onimportv1 } });
    expect(getByTestId("session-import").getAttribute("data-help")).toBe(HELP.sessionImportV1);
    const file = new File(['{"version":1}'], "old-set.json", { type: "application/json" });
    await fireEvent.change(getByTestId("session-import-file"), { target: { files: [file] } });
    expect(onimportv1).toHaveBeenCalledWith(file);
  });
});
