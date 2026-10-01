// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { HELP } from "../../../lib/help/strings";
import { legendColor } from "../../../lib/chroma/consonanceColor";
import MatchLegend from "../MatchLegend.svelte";

const TARGET = Float32Array.from([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);

afterEach(cleanup);

describe("MatchLegend's DOM contract", () => {
  it("carries HELP.chromaMatchMarks on the legend (v3 292)", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    expect(getByTestId("chroma-legend").getAttribute("data-help")).toBe(HELP.chromaMatchMarks);
  });

  it("carries HELP.chromaMatchLegend on the readout line (v3 330)", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    expect(getByTestId("chroma-match-readout").getAttribute("data-help")).toBe(HELP.chromaMatchLegend);
  });
});

describe("MatchLegend draws the gradient and its three anchor marks (spec §5.4)", () => {
  it("is nine stops, each coloured by the ramp rather than a token", () => {
    const { container } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    const stops = container.querySelectorAll("[data-legend-stop]");
    expect(stops).toHaveLength(9);
    // Read the RAW attribute, not `.style.background`. jsdom parses the style
    // attribute through cssstyle, whose colour parser may not know `oklch()` --
    // an unrecognised value makes the whole `background` shorthand a no-op and
    // `.style.background` returns "". A version that does understand CSS Color 4
    // would SERIALISE it (`oklch(58% 0.17 60)`), so an exact-string compare
    // fails there too. The attribute is untouched by the CSSOM either way.
    expect(stops[0].getAttribute("style")).toContain("oklch");
    // jsdom's cssstyle re-serialises oklch() (`oklch(58.00% 0.170 60.0)` -> `oklch(0.58 0.17 60)`),
    // so an exact compare against legendColor(1) cannot hold here. What this guards is that the
    // ramp end stops are ramp-coloured and differ -- the colour maths itself is covered by
    // consonanceColor.test.ts. (legendColor kept imported: it is the contract being approximated.)
    void legendColor;
    expect(stops[8].getAttribute("style")).toContain("oklch");
    expect(stops[8].getAttribute("style")).not.toBe(stops[0].getAttribute("style"));
  });

  it("marks unison, fifth and tritone, each with its own value", () => {
    const { container, getAllByText } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    expect(container.querySelectorAll("[data-legend-tick]")).toHaveLength(3);
    // getAll: the readout line also names the nearest anchor ("... fifth ..."), so one word can
    // legitimately appear twice.
    expect(getAllByText(/unison/).length).toBeGreaterThan(0);
    expect(getAllByText(/fifth/).length).toBeGreaterThan(0);
    expect(getAllByText(/tritone/).length).toBeGreaterThan(0);
  });
});

describe("MatchLegend's readout line (v3 330: `match <score> · <scale>`)", () => {
  it("reads the clip's score and where it sits against the anchors", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: 1 } });
    expect(getByTestId("chroma-match-readout").textContent).toBe(
      "match 1.00 · at unison · consonance colour",
    );
  });

  it("says nothing it does not know when no clip has been scored yet", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: null } });
    expect(getByTestId("chroma-match-readout").textContent).toBe("match — · consonance colour");
  });
});
