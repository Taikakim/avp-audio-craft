import { describe, expect, it } from "vitest";
import { HELP } from "../strings";

describe("the top bar's three new HELP strings (v3 line 43's SAVE has none; IMPORT is not drawn at all)", () => {
  it("masterPresetSave exists and mentions saving", () => {
    expect(HELP.masterPresetSave.length).toBeGreaterThan(10);
    expect(HELP.masterPresetSave.toLowerCase()).toContain("save");
  });

  it("sessionSave mentions saving, and sessionImportV1 names the v1 files it converts", () => {
    expect(HELP.sessionSave.toLowerCase()).toContain("save");
    expect(HELP.sessionImportV1.toLowerCase()).toContain("v1");
  });
});
