// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../../lib/forge/defaults";
import type { RenderSettings, Target } from "../../../lib/forge/types";
import { settings } from "../../../lib/stores/settings.svelte";
import PromptColumn from "../PromptColumn.svelte";

const CLIP: Target = { kind: "clip", id: "c1" };

function fakeSource() {
  const clips: Record<string, RenderSettings> = { c1: cloneRenderSettings(BASE_DEFAULTS) };
  return { clips, clipSettings: (id: string) => clips[id] ?? null, overlapSettings: () => null };
}

let src: ReturnType<typeof fakeSource>;
beforeEach(() => {
  src = fakeSource();
  settings.attach(src);
});
afterEach(() => {
  settings.detach();
  cleanup();
});

describe("PromptColumn (spec 4.5 item 1)", () => {
  it("shows the target's current prompt and negative prompt", () => {
    src.clips.c1.prompt = "dub techno, tape hiss";
    src.clips.c1.negative_prompt = "vocals";
    const { getByTestId } = render(PromptColumn, { props: { target: CLIP } });
    expect((getByTestId("prompt-text") as HTMLTextAreaElement).value).toBe("dub techno, tape hiss");
    expect((getByTestId("prompt-negative") as HTMLTextAreaElement).value).toBe("vocals");
  });

  it("writes the prompt through settings.patch on input", async () => {
    const { getByTestId } = render(PromptColumn, { props: { target: CLIP } });
    await fireEvent.input(getByTestId("prompt-text"), { target: { value: "a slow marimba figure" } });
    expect(src.clips.c1.prompt).toBe("a slow marimba figure");
  });

  it("writes the negative prompt through settings.patch on input", async () => {
    const { getByTestId } = render(PromptColumn, { props: { target: CLIP } });
    await fireEvent.input(getByTestId("prompt-negative"), { target: { value: "drums" } });
    expect(src.clips.c1.negative_prompt).toBe("drums");
  });

  it("carries data-help on both fields", () => {
    const { getByTestId } = render(PromptColumn, { props: { target: CLIP } });
    expect(getByTestId("prompt-text").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("prompt-negative").getAttribute("data-help")).toBeTruthy();
  });
});
