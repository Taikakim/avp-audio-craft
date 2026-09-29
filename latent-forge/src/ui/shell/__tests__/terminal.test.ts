// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import Terminal from "../Terminal.svelte";

afterEach(() => cleanup());

const lines = [
  { seq: 1, text: "$ player /status → ok", tone: "dim" },
  { seq: 2, text: "lane 2  decode 000412.npy", tone: "text" },
];

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
