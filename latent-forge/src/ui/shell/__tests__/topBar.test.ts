// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { buildModelOptions } from "../../topbar/modelOptions";
import TopBar from "../TopBar.svelte";

afterEach(() => cleanup());

const base = {
  view: "workspace" as const,
  onview: () => {},
  helpMode: false,
  onhelp: () => {},
  theme: "light" as const,
  ontheme: () => {},
};

describe("the top bar carries spec §4.2 left to right", () => {
  it("names the app and lists the sessions the server reported", () => {
    const { getByTestId, container } = render(TopBar, {
      props: {
        ...base,
        sessions: [
          { name: "session_2026-09-16_0912", updated: 1, n_clips: 4 },
          { name: "session_2026-09-16_2140", updated: 2, n_clips: 7 },
        ],
        session: "session_2026-09-16_2140",
      },
    });
    expect(container.querySelector(".wordmark")?.textContent).toBe("LATENT FORGE");
    const select = getByTestId("session-select") as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual([
      "session_2026-09-16_0912",
      "session_2026-09-16_2140",
    ]);
    expect(select.value).toBe("session_2026-09-16_2140");
  });

  it("puts the four backbones before the adapters in the MODEL select", () => {
    const { getByTestId } = render(TopBar, {
      props: {
        ...base,
        models: buildModelOptions([{ path: "/SERVER/ckpts/custom_v3.ckpt", name: "custom_v3.ckpt" }]),
        model: "medium",
      },
    });
    const select = getByTestId("model-select") as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual([
      "medium", "medium-base", "small-music", "small-music-base", "/SERVER/ckpts/custom_v3.ckpt",
    ]);
  });

  it("disables SAVE on the master preset until M7 owns presets, and keeps the MIXDOWN frame", () => {
    const { getByTestId } = render(TopBar, {
      props: { ...base, masterPresets: ["live set A"], masterPreset: "live set A" },
    });
    // True at M1's end state, so it lives here. M7 T9 owns the flip: when it wires master-preset
    // SAVE it retitles this test and changes this one assertion to `.toBe(false)` (M7 plan,
    // Task 9 Step 4) -- the test file stays M1's, the behaviour change is M7's.
    expect((getByTestId("master-preset-save") as HTMLButtonElement).disabled).toBe(true);
    expect(getByTestId("mixdown-button").textContent?.trim()).toBe("▸ MIXDOWN");
  });

  // C1 fix wave: SAVE used to serialize the v1 `project` store, which has held
  // zero clips since Task 5 -- clicking SAVE silently produced a file with no
  // clips in it. This exercises the real button, through the real component,
  // against the real `arrangement` singleton.
  it("SAVE serializes the arrangement's real clips, not the always-empty v1 project store", () => {
    const clip = arrangement.addClip({
      lane: 1, startSec: 2, durSec: 4, audio: { kind: "crop", crop_id: "topbar-save-test" },
    });
    // jsdom's Blob has no .text()/.arrayBuffer(), so capture what TopBar hands
    // the Blob constructor directly rather than reading the Blob back out.
    let capturedText: string | null = null;
    const RealBlob = globalThis.Blob;
    class SpyBlob extends RealBlob {
      constructor(parts: BlobPart[], options?: BlobPropertyBag) {
        super(parts, options);
        capturedText = String(parts[0]);
      }
    }
    globalThis.Blob = SpyBlob as unknown as typeof Blob;
    const realCreate = URL.createObjectURL;
    const realRevoke = URL.revokeObjectURL;
    URL.createObjectURL = (() => "blob:mock") as typeof URL.createObjectURL;
    URL.revokeObjectURL = () => {};
    try {
      const { getByTestId } = render(TopBar, { props: { ...base } });
      (getByTestId("save-project") as HTMLButtonElement).click();
      expect(capturedText).not.toBeNull();
      const data = JSON.parse(capturedText!);
      expect(data.kind).toBe("latent-forge-arrangement");
      expect(data.clips.some((c: { id: string }) => c.id === clip.id)).toBe(true);
    } finally {
      globalThis.Blob = RealBlob;
      URL.createObjectURL = realCreate;
      URL.revokeObjectURL = realRevoke;
      arrangement.removeClip(clip.id);
    }
  });
});
