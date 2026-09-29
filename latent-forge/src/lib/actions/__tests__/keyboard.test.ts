// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { handleKey, installGlobalKeys, ZOOM_STEP, type KeyActions } from "../keyboard";

function actions(): KeyActions & { calls: string[] } {
  const calls: string[] = [];
  return {
    calls,
    togglePlay: () => calls.push("play"),
    rewind: () => calls.push("rewind"),
    deleteSelected: () => calls.push("delete"),
    zoomBy: (f: number) => calls.push(`zoom:${f.toFixed(4)}`),
  };
}

function key(k: string, target?: Element): KeyboardEvent {
  const e = new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true });
  if (target) Object.defineProperty(e, "target", { value: target });
  return e;
}

beforeEach(() => {
  document.body.innerHTML = "";
});

describe("the keyboard behaviour the existing app has and must keep (spec §9.6)", () => {
  it("space toggles play and swallows the event so the page does not scroll", () => {
    const a = actions();
    const e = key(" ");
    expect(handleKey(e, a)).toBe(true);
    expect(a.calls).toEqual(["play"]);
    expect(e.defaultPrevented).toBe(true);
  });

  it("Home rewinds to zero", () => {
    const a = actions();
    expect(handleKey(key("Home"), a)).toBe(true);
    expect(a.calls).toEqual(["rewind"]);
  });

  it("Delete and Backspace remove the selected clip", () => {
    const a = actions();
    handleKey(key("Delete"), a);
    handleKey(key("Backspace"), a);
    expect(a.calls).toEqual(["delete", "delete"]);
  });

  it("+ and = zoom in, - zooms out, by the same factor the existing app used", () => {
    const a = actions();
    handleKey(key("+"), a);
    handleKey(key("="), a);
    handleKey(key("-"), a);
    expect(ZOOM_STEP).toBeCloseTo(1.4, 10);
    expect(a.calls).toEqual([
      `zoom:${ZOOM_STEP.toFixed(4)}`,
      `zoom:${ZOOM_STEP.toFixed(4)}`,
      `zoom:${(1 / ZOOM_STEP).toFixed(4)}`,
    ]);
  });

  it("ignores keys it does not own", () => {
    const a = actions();
    expect(handleKey(key("k"), a)).toBe(false);
    expect(a.calls).toEqual([]);
  });
});

describe("it never steals a key from a field being typed in", () => {
  for (const tag of ["INPUT", "TEXTAREA", "SELECT"]) {
    it(`ignores keys inside a ${tag}`, () => {
      const a = actions();
      const el = document.createElement(tag.toLowerCase());
      document.body.appendChild(el);
      expect(handleKey(key(" ", el), a)).toBe(false);
      expect(handleKey(key("Backspace", el), a)).toBe(false);
      expect(a.calls).toEqual([]);
    });
  }

  it("ignores keys inside a contenteditable prompt box", () => {
    const a = actions();
    const el = document.createElement("div");
    el.setAttribute("contenteditable", "true");
    document.body.appendChild(el);
    expect(handleKey(key(" ", el), a)).toBe(false);
    expect(a.calls).toEqual([]);
  });
});

describe("installGlobalKeys", () => {
  it("listens on the window and its disposer removes the listener", () => {
    const a = actions();
    const dispose = installGlobalKeys(a);
    window.dispatchEvent(key(" "));
    expect(a.calls).toEqual(["play"]);
    dispose();
    window.dispatchEvent(key(" "));
    expect(a.calls).toEqual(["play"]);
  });

  it("is idempotent: installing twice and disposing both leaves nothing behind", () => {
    const a = actions();
    const d1 = installGlobalKeys(a);
    const d2 = installGlobalKeys(a);
    d1();
    d2();
    window.dispatchEvent(key("Home"));
    expect(a.calls).toEqual([]);
    expect(vi.isMockFunction(() => {})).toBe(false);
  });
});
