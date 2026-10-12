import { describe, expect, it, vi } from "vitest";
import { LOG_RING, THEME_KEY, ViewStore } from "../view.svelte";

// NOTE: pxPerSec / scrollSec (timeline viewport zoom+scroll) are NOT tested here.
// Ruled out of this store (WINTERMUTE, 2026-09-16): they belong to the
// pre-existing `arrangement` store, which M5 takes over. An earlier draft of
// this task's brief put them on ViewStore; that draft is stale.

/** Map-backed localStorage: the store must never require a real browser. */
function fakeStorage(seed: Record<string, string> = {}) {
  const m = new Map(Object.entries(seed));
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    dump: () => Object.fromEntries(m),
  };
}

describe("theme (spec §9.1)", () => {
  it("starts light", () => {
    expect(new ViewStore(fakeStorage()).theme).toBe("light");
  });

  it("persists to localStorage['latentforge.theme']", () => {
    const s = fakeStorage();
    const v = new ViewStore(s);
    v.setTheme("dark");
    expect(THEME_KEY).toBe("latentforge.theme");
    expect(s.dump()).toEqual({ "latentforge.theme": "dark" });
  });

  it("restores a stored theme", () => {
    expect(new ViewStore(fakeStorage({ "latentforge.theme": "dark" })).theme).toBe("dark");
  });

  it("falls back to light on a junk stored value", () => {
    expect(new ViewStore(fakeStorage({ "latentforge.theme": "solarized" })).theme).toBe("light");
  });

  it("never consults prefers-color-scheme -- the toggle is the only switch", () => {
    const matchMedia = vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
    vi.stubGlobal("matchMedia", matchMedia);
    const v = new ViewStore(fakeStorage());
    v.toggleTheme();
    v.toggleTheme();
    expect(matchMedia).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("toggles both ways", () => {
    const v = new ViewStore(fakeStorage());
    v.toggleTheme();
    expect(v.theme).toBe("dark");
    v.toggleTheme();
    expect(v.theme).toBe("light");
  });
});

describe("shell state", () => {
  it("toggles help mode", () => {
    const v = new ViewStore(fakeStorage());
    expect(v.helpOn).toBe(false);
    v.toggleHelp();
    expect(v.helpOn).toBe(true);
  });

  it("switches between workspace and statistics", () => {
    const v = new ViewStore(fakeStorage());
    expect(v.screen).toBe("workspace");
    v.setView("statistics");
    expect(v.screen).toBe("statistics");
  });

  it("selects a bottom tab (spec §4.5)", () => {
    const v = new ViewStore(fakeStorage());
    expect(v.bottomTab).toBe("prompt");
    v.setBottomTab("terminal");
    expect(v.bottomTab).toBe("terminal");
  });

  it("opens and closes right-pane modules without reordering them (spec §4.6)", () => {
    const v = new ViewStore(fakeStorage());
    v.openModule("master-chain");
    v.openModule("overlap");
    v.openModule("master-chain"); // idempotent
    expect(v.openModules).toEqual(["files", "lane-chain", "master-chain", "overlap"]);
    expect(v.isModuleOpen("overlap")).toBe(true);
    v.toggleModule("overlap");
    expect(v.isModuleOpen("overlap")).toBe(false);
    v.closeModule("files");
    expect(v.openModules).toEqual(["lane-chain", "master-chain"]);
  });

  it("collapses the side pane", () => {
    const v = new ViewStore(fakeStorage());
    expect(v.sideOpen).toBe(true);
    v.toggleSide();
    expect(v.sideOpen).toBe(false);
  });

  it("has the three terminal modes", () => {
    const v = new ViewStore(fakeStorage());
    expect(v.terminal).toBe("pane");
    v.setTerminal("full");
    expect(v.terminal).toBe("full");
    v.setTerminal("collapsed");
    expect(v.terminal).toBe("collapsed");
  });
});

describe("selection", () => {
  it("carries a Target and exposes its stable key", () => {
    const v = new ViewStore(fakeStorage());
    expect(v.selection).toEqual({ kind: "none" });
    expect(v.selectionKey).toBe("session");
    v.select({ kind: "clip", id: "clip_a" });
    expect(v.selectionKey).toBe("clip:clip_a");
    v.select({ kind: "overlap", key: "clip_a-clip_b" });
    expect(v.selectionKey).toBe("overlap:clip_a-clip_b");
    v.clearSelection();
    expect(v.selection).toEqual({ kind: "none" });
  });
});

describe("project ui slice (spec §9.2)", () => {
  it("round-trips through snapshotUi / restoreUi", () => {
    const v = new ViewStore(fakeStorage());
    v.setBottomTab("mix");
    v.openModule("advanced-sampling");
    v.toggleSide();
    v.setTerminal("full");
    const snap = v.snapshotUi();
    expect(snap).toEqual({
      bottomTab: "mix",
      modules: ["files", "lane-chain", "advanced-sampling"],
      sideOpen: false,
      terminal: "full",
    });

    const w = new ViewStore(fakeStorage());
    w.restoreUi(snap);
    expect(w.snapshotUi()).toEqual(snap);
  });

  it("ignores unknown tabs, modules and terminal modes in a stored project", () => {
    const v = new ViewStore(fakeStorage());
    v.restoreUi({ bottomTab: "nope", modules: ["files", "nope"], sideOpen: true, terminal: "nope" });
    expect(v.bottomTab).toBe("prompt");
    expect(v.openModules).toEqual(["files"]);
    expect(v.terminal).toBe("pane");
  });
});

describe("the $state proxy rule (global constraint; the bug faedf55 fixed)", () => {
  it("appendLog hands back the array's LIVE element, not the object it built", () => {
    const v = new ViewStore(fakeStorage());
    const line = v.appendLog("[forge] job forge-1 running");

    // Mutating the returned handle must reach the store. If appendLog returned the
    // local object it pushed, $state's deep proxy would make this a dead handle and
    // the assertion would fail -- which is exactly the shipped bug this guards.
    line.text = "[forge] job forge-1 done";
    expect(v.logLines[v.logLines.length - 1].text).toBe("[forge] job forge-1 done");

    // ...and it is the same object identity the array yields.
    expect(line).toBe(v.logLines[v.logLines.length - 1]);
  });

  it("caps the log at the server's 400-line ring (spec §6.4)", () => {
    const v = new ViewStore(fakeStorage());
    for (let i = 0; i < LOG_RING + 25; i++) v.appendLog(`line ${i}`);
    expect(v.logLines).toHaveLength(LOG_RING);
    expect(v.logLines[0].text).toBe("line 25");
    expect(v.logLines[LOG_RING - 1].seq).toBe(LOG_RING + 25);
    v.clearLog();
    expect(v.logLines).toHaveLength(0);
  });
});
