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

  it("enables SAVE on the master preset now that M7 owns presets, and keeps the MIXDOWN frame", () => {
    const { getByTestId } = render(TopBar, {
      props: { ...base, masterPresets: ["live set A"], masterPreset: "live set A" },
    });
    expect((getByTestId("master-preset-save") as HTMLButtonElement).disabled).toBe(false);
    expect(getByTestId("mixdown-button").textContent?.trim()).toBe("▸ MIXDOWN");
  });
});
