// @vitest-environment jsdom
//
// Shell components are props-driven, so they are testable without the view store --
// except ModuleShell, whose open state IS the view store's (Normative names).
// Geometry (42 / 248 / 296 / 24 / 162 / 44 px) is asserted by the Playwright spec;
// what is asserted here is the behaviour those boxes carry: the accordion opens and
// closes, the lit dot follows `lit`, the side pane collapses to its strip, and help
// mode reads the nearest `data-help` the way v3's `onRootMove` (line 1619) does.

import { createRawSnippet } from "svelte";
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { view } from "../../../lib/stores/view.svelte";
import { helpTextAt } from "../helpLookup";
import ModuleShell from "../ModuleShell.svelte";
import RightPane from "../RightPane.svelte";

afterEach(() => cleanup());

const body = createRawSnippet(() => ({
  render: () => `<p data-testid="body">module body</p>`,
}));

describe("helpTextAt finds the nearest data-help ancestor", () => {
  it("reads the string off the hovered element itself", () => {
    document.body.innerHTML = `<button id="b" data-help="Runs the current target."></button>`;
    expect(helpTextAt(document.getElementById("b"))).toBe("Runs the current target.");
  });

  it("walks up to the nearest ancestor that has one", () => {
    document.body.innerHTML =
      `<div data-help="outer"><div data-help="inner"><span id="s"></span></div></div>`;
    expect(helpTextAt(document.getElementById("s"))).toBe("inner");
  });

  it("returns null when nothing on the path carries one, and for an empty string", () => {
    document.body.innerHTML = `<div><span id="s"></span></div><b id="e" data-help=""></b>`;
    expect(helpTextAt(document.getElementById("s"))).toBeNull();
    expect(helpTextAt(document.getElementById("e"))).toBeNull();
    expect(helpTextAt(null)).toBeNull();
  });

  it("ignores a hit outside the given root", () => {
    document.body.innerHTML =
      `<div id="root"></div><div data-help="elsewhere"><span id="s"></span></div>`;
    const root = document.getElementById("root");
    expect(helpTextAt(document.getElementById("s"), root)).toBeNull();
  });
});

// ModuleShell's Normative props are {id, title, lit, children}; its open state is the view
// store's, so these tests drive `view` directly and put it back afterwards.
describe("ModuleShell is a collapsible accordion with a lit dot", () => {
  afterEach(() => {
    view.closeModule("master-chain");
    view.openModule("files");   // the view store's own default (Task 7)
  });

  it("shows ▸ and hides its body while the view store has it closed", () => {
    view.closeModule("master-chain");
    const { getByTestId, queryByTestId, container } = render(ModuleShell, {
      props: { id: "master-chain", title: "MASTER CHAIN", lit: false, children: body },
    });
    expect(getByTestId("module-head").textContent).toContain("▸ MASTER CHAIN");
    expect(container.querySelector('[data-module="master-chain"] [data-module-toggle="master-chain"]')).not.toBeNull();
    expect(queryByTestId("body")).toBeNull();
    expect(container.querySelector('[data-module-body="master-chain"]')).toBeNull();
  });

  it("shows ▾ and renders its body while the view store has it open", () => {
    view.openModule("master-chain");
    const { getByTestId, container } = render(ModuleShell, {
      props: { id: "master-chain", title: "MASTER CHAIN", lit: false, children: body },
    });
    expect(getByTestId("module-head").textContent).toContain("▾ MASTER CHAIN");
    expect(getByTestId("body").textContent).toBe("module body");
    expect(container.querySelector('[data-module-body="master-chain"]')).not.toBeNull();
  });

  it("lights the dot only when `lit` is true, on the pinned [data-module-dot] hook", () => {
    const off = render(ModuleShell, {
      props: { id: "files", title: "FILES", lit: false, children: body },
    });
    expect(off.container.querySelector('[data-module-dot="files"]')!.getAttribute("data-lit")).toBe("false");
    cleanup();
    const on = render(ModuleShell, {
      props: { id: "files", title: "FILES", lit: true, children: body },
    });
    expect(on.container.querySelector('[data-module-dot="files"]')!.getAttribute("data-lit")).toBe("true");
  });

  it("toggles the view store's open state when the header is clicked", async () => {
    view.closeModule("files");
    const { getByTestId, findByTestId } = render(ModuleShell, {
      props: { id: "files", title: "FILES", lit: false, children: body },
    });
    getByTestId("module-head").click();
    expect(view.isModuleOpen("files")).toBe(true);
    expect((await findByTestId("body")).textContent).toBe("module body");
  });
});

describe("RightPane collapses to its 24 px strip", () => {
  it("is 296 px wide, labelled ◂ CONTEXT, and renders its modules when open", () => {
    const { getByTestId } = render(RightPane, {
      props: { open: true, ontoggle: () => {}, children: body },
    });
    const pane = getByTestId("right-pane");
    expect(pane.style.width).toBe("296px");
    expect(getByTestId("side-toggle").textContent?.trim()).toBe("◂ CONTEXT");
    expect(getByTestId("body")).not.toBeNull();
  });

  it("is 24 px wide, labelled ▸, and drops its modules when collapsed", () => {
    const { getByTestId, queryByTestId } = render(RightPane, {
      props: { open: false, ontoggle: () => {}, children: body },
    });
    expect(getByTestId("right-pane").style.width).toBe("24px");
    expect(getByTestId("side-toggle").textContent?.trim()).toBe("▸");
    expect(queryByTestId("body")).toBeNull();
  });
});
