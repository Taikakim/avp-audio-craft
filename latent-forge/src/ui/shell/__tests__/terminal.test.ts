// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Terminal from "../Terminal.svelte";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const lines = [
  { key: 0, seq: 1, text: "$ player /status → ok", tone: "dim" },
  { key: 1, seq: 2, text: "lane 2  decode 000412.npy", tone: "text" },
];

function manyLines(n: number) {
  return Array.from({ length: n }, (_, i) => ({ key: i, seq: i, text: `line ${i}`, tone: "text" }));
}

/** jsdom does no real layout -- scrollHeight/clientHeight always read 0 -- so every autoscroll
 *  test stubs them at the prototype level. scrollHeight tracks the number of `.line` rows
 *  actually IN THE DOM at the moment it's read, so it naturally reports the pre-update count
 *  while `$effect.pre` runs (before Svelte patches the DOM for that update) and the post-update
 *  count while the plain `$effect` runs (after) -- exactly the distinction finding #5 is about. */
function stubScrollGeometry(pxPerLine: number, clientHeightPx: number) {
  vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(function (this: HTMLElement) {
    return this.querySelectorAll(".line").length * pxPerLine;
  });
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(clientHeightPx);
}

describe("the TERMINAL tab (spec §4.5)", () => {
  it("shows its lines in PANE mode and lights the dot while the server is busy", () => {
    const { getByTestId } = render(Terminal, {
      props: { mode: "pane" as const, busy: true, lines, onmode: () => {} },
    });
    expect(getByTestId("terminal-body").textContent).toContain("lane 2  decode 000412.npy");
    expect(getByTestId("terminal-dot").getAttribute("data-busy")).toBe("true");
  });

  it("hides the body in COLLAPSE mode but keeps the header", () => {
    const { queryByTestId, getByTestId } = render(Terminal, {
      props: { mode: "collapsed" as const, busy: false, lines, onmode: () => {} },
    });
    expect(queryByTestId("terminal-body")).toBeNull();
    expect(getByTestId("terminal-dot").getAttribute("data-busy")).toBe("false");
  });

  it("marks FULL SCREEN mode on the region so it can cover the centre column", () => {
    const { container } = render(Terminal, {
      props: { mode: "full" as const, busy: false, lines, onmode: () => {} },
    });
    expect(container.querySelector('[data-region="terminal"]')?.getAttribute("data-mode")).toBe("full");
  });
});

describe("TERMINAL keys rows by a unique key, not by seq (review 2026-10-01)", () => {
  it("renders every row when client lines share the server's seq", () => {
    // appendLocal stamps client lines with the current server cursor, so several rows can carry
    // the same seq. Keying {#each} by seq threw each_key_duplicate here.
    const dup = [
      { key: 0, seq: 41, text: "server line", tone: "text" },
      { key: 1, seq: 41, text: "[stats] analysed", tone: "text" },
      { key: 2, seq: 41, text: "[forge] autosave failed", tone: "error" },
    ];
    const { container } = render(Terminal, {
      props: { mode: "pane" as const, busy: false, lines: dup, onmode: () => {} },
    });
    expect([...container.querySelectorAll(".line")].map((e) => e.textContent)).toEqual(
      ["server line", "[stats] analysed", "[forge] autosave failed"]);
  });
});

describe("TERMINAL follows the newest lines (fix wave 2026-09-29, finding #5)", () => {
  it("mounts with a full batch of lines already scrolled to the bottom, not the top", () => {
    stubScrollGeometry(20, 200);
    const { getByTestId } = render(Terminal, {
      props: { mode: "pane" as const, busy: false, lines: manyLines(400), onmode: () => {} },
    });
    const body = getByTestId("terminal-body") as HTMLDivElement;
    // 400 lines * 20px is far taller than the 200px viewport -- scrollTop defaults to 0 (the
    // oldest lines) unless the mount effect explicitly forces it to the bottom.
    expect(body.scrollTop).toBeGreaterThan(0);
    expect(body.scrollTop).toBe(body.scrollHeight);
  });

  it("stays scrolled to the bottom when a poll adds more than a couple of lines while already there", () => {
    stubScrollGeometry(20, 50);
    const { getByTestId, rerender } = render(Terminal, {
      props: { mode: "pane" as const, busy: false, lines: manyLines(5), onmode: () => {} },
    });
    const body = getByTestId("terminal-body") as HTMLDivElement;
    expect(body.scrollTop).toBe(body.scrollHeight); // starts stuck to the bottom (5 * 20 = 100)

    // A poll that adds 15 lines (300px) -- well over the "~2-3 lines / ~40px" symptom threshold.
    rerender({ lines: manyLines(20) });
    expect(body.scrollTop).toBe(body.scrollHeight); // 20 * 20 = 400
    expect(body.scrollTop).toBeGreaterThan(100);
  });
});
