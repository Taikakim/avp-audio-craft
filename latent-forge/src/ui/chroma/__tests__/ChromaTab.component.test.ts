// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { chromaClient } from "../../../lib/chroma/chromaClient.svelte";
import { chromaLink } from "../../../lib/chroma/chromaLink.svelte";
import { meanMatchAtDetune } from "../../../lib/chroma/detuneScan";
import { chromaTarget } from "../../../lib/chroma/targetStore.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import ChromaTab from "../ChromaTab.svelte";

const scheduleStretch = vi.fn();
vi.mock("../../../lib/clips/lifecycle", () => ({
  scheduleStretch: (...args: unknown[]) => scheduleStretch(...args),
}));

// Waiting for Svelte is `await tick()`, never `await Promise.resolve()`.
// Svelte 5 flushes its scheduler in a microtask as well, so a bare resolved
// promise is not ORDERED after the re-render -- it happens to work today and
// is a flake tomorrow. `chromaClient.flush()` and timer advances stay where
// the test is genuinely waiting on a fetch or a debounce rather than the DOM.

/** /forge/chroma's own wire shape (spec §6.3), one frame of pure C. */
function chromaBody(T: number) {
  const bands = new Uint8Array(3 * 128 * T);
  const fold = new Uint8Array(12 * T);
  for (let t = 0; t < T; t++) {
    bands[(0 * 128 + 2) * T + t] = 255;
    fold[0 * T + t] = 255;
  }
  const b64 = (u: Uint8Array) => {
    let s = "";
    for (const b of u) s += String.fromCharCode(b);
    return btoa(s);
  };
  return {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: { shape: [3, 128, T], scale: [1, 1, 1], data_b64: b64(bands) },
    fold12: { shape: [12, T], scale: 1.0, data_b64: b64(fold) },
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

beforeEach(() => {
  scheduleStretch.mockClear();
  chromaClient.dispose();
  chromaTarget.dispose();
  chromaLink.reset();
  view.clearLog();
  view.clearSelection();
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 480 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 131 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  chromaClient.dispose();
  chromaTarget.dispose();
  chromaLink.reset();
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  cleanup();
});

function selectAClip(over: { detune?: number } = {}) {
  const clip = arrangement.addClip({
    lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "000412" },
  });
  if (over.detune !== undefined) arrangement.setDetune(clip.id, over.detune);
  view.select({ kind: "clip", id: clip.id });
  return arrangement.clips[0];
}

describe("the mode row (spec §5.4, v3 288 and 2011-2016)", () => {
  it("is the four views plus MATCH CURVE, none of them with a data-help M1 does not have", () => {
    const { container, getByTestId } = render(ChromaTab);
    const views = [...container.querySelectorAll("[data-chroma-view]")];
    expect(views.map((b) => b.getAttribute("data-chroma-view"))).toEqual(["global", "bass", "mid", "high"]);
    expect(views.map((b) => b.textContent)).toEqual(["GLOBAL", "BASS oct1", "MID oct5", "HIGH oct9"]);
    for (const b of views) expect(b.hasAttribute("data-help")).toBe(false);
    expect(getByTestId("chroma-curve-toggle").textContent).toBe("MATCH CURVE");
  });

  it("switches the active view, and MATCH CURVE mounts and unmounts the overlay", async () => {
    const { container, getByTestId, queryByTestId } = render(ChromaTab);
    expect(getByTestId("chroma-match-curve")).toBeTruthy();
    await fireEvent.click(getByTestId("chroma-curve-toggle"));
    expect(queryByTestId("chroma-match-curve")).toBeNull();
    await fireEvent.click(container.querySelector('[data-chroma-view="mid"]')!);
    expect(container.querySelector('[data-chroma-view="mid"]')!.classList.contains("on")).toBe(true);
  });
});

describe("honest empty states (spec §9.7 and §5.4)", () => {
  it("says no clip is selected rather than drawing an empty heatmap", () => {
    const { getByTestId } = render(ChromaTab);
    expect(getByTestId("chroma-empty").textContent).toBe("no clip selected");
  });

  it("says it is still computing while the request is in flight", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    selectAClip();
    const { getByTestId } = render(ChromaTab);
    await tick();
    expect(getByTestId("chroma-empty").textContent).toBe("computing chroma…");
  });

  it("shows a server error in one line AND as a red TERMINAL line (spec §9.7)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ ok: false, error: "no such crop" }, 404)));
    selectAClip();
    const { getByTestId } = render(ChromaTab);
    await chromaClient.flush();
    await tick();
    expect(getByTestId("chroma-error").textContent).toContain("no such crop");
    const last = view.logLines[view.logLines.length - 1];
    expect(last.level).toBe("error");
    expect(last.text).toContain("no such crop");
  });
});

describe("what the tab asks the server for (spec §5.4, §6.3)", () => {
  it("analyses the STRETCHED preview when the clip has one, not the source audio", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      seen.push(JSON.parse(String(init?.body ?? "{}")));
      return json(chromaBody(8));
    }));
    const clip = selectAClip();
    arrangement.setPreviewAudio(clip.id, { kind: "path", path: "/stretched.wav" });
    render(ChromaTab);
    await chromaClient.flush();
    expect(seen).toEqual([{ audio: { kind: "path", path: "/stretched.wav" } }]);
  });

  it("falls back to the source audio for an unstretched clip", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      seen.push(JSON.parse(String(init?.body ?? "{}")));
      return json(chromaBody(8));
    }));
    selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    expect(seen).toEqual([{ audio: { kind: "crop", crop_id: "000412" } }]);
  });
});

describe("detune: the stretch leads and the chroma follows (spec §5.4)", () => {
  it("arms M5 T10's debounced stretch once per detune change, and never its own", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    const clip = selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    scheduleStretch.mockClear();
    arrangement.setDetune(clip.id, 24);
    await tick();
    expect(scheduleStretch).toHaveBeenCalledTimes(1);
    expect(scheduleStretch).toHaveBeenCalledWith(clip.id, expect.any(Function));
  });

  it("re-requests chroma when the stretch lands a new previewAudio, not when detune changes", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      seen.push(JSON.parse(String(init?.body ?? "{}")));
      return json(chromaBody(8));
    }));
    const clip = selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    expect(seen).toHaveLength(1);

    arrangement.setDetune(clip.id, 24);
    await tick();
    expect(seen).toHaveLength(1); // the detune alone asks the server nothing

    arrangement.setPreviewAudio(clip.id, { kind: "path", path: "/stretched-24.wav" });
    await chromaClient.flush();
    expect(seen).toHaveLength(2);
    expect(seen[1]).toEqual({ audio: { kind: "path", path: "/stretched-24.wav" } });
  });
});

describe("the clip score label and the lane cross-link", () => {
  it("writes the clip's mean frame match into chromaLink once the analysis lands", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    chromaTarget.setChordText("C");
    const clip = selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    await tick();
    expect(chromaLink.scores[clip.id]).toBeGreaterThan(0);
  });

  it("does NOT rotate a STRETCHED clip's chroma by its detune -- the stretch already applied it", async () => {
    // The 2026-09-22 critic's blocking finding, pinned. M5 T10's runStretch
    // pitch-shifts previewAudio by clip.detune_cents / 100 (M5:5358) and this
    // tab analyses that preview, so result.fold12 is ALREADY detuned; rotating
    // it again by the clip's detune applied the detune twice. No test set BOTH
    // a previewAudio and a non-zero detune_cents, which is why nothing caught
    // it -- this one sets both, and asserts the UN-rotated score.
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    chromaTarget.setChordText("C");
    const clip = selectAClip({ detune: 50 });
    arrangement.setPreviewAudio(clip.id, { kind: "path", path: "/stretched-50.wav" });
    render(ChromaTab);
    await chromaClient.flush();
    await tick();
    const res = chromaClient.result!;
    const target = chromaTarget.profile;
    expect(chromaLink.scores[clip.id]).toBeCloseTo(meanMatchAtDetune(res.fold12, res.T, target, 0), 9);
    // and it is genuinely a different number, so the assertion above has teeth:
    // rotating [1,0,...] by half a class splits it across classes 0 and 1.
    expect(chromaLink.scores[clip.id]).not.toBeCloseTo(
      meanMatchAtDetune(res.fold12, res.T, target, 50),
      6,
    );
  });

  it("marks the hovered frame on the clip in its lane, and clears it on leave", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    const clip = selectAClip();
    const { container, getByTestId } = render(ChromaTab);
    await chromaClient.flush();
    await tick();
    const box = container.querySelector('[data-region="chroma-heatmap-box"]')! as HTMLElement;
    vi.spyOn(box, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 480, height: 131, right: 480, bottom: 131, x: 0, y: 0, toJSON: () => ({}),
    });
    await fireEvent.pointerMove(box, { clientX: 240, clientY: 120 });
    expect(chromaLink.hover?.clipId).toBe(clip.id);
    expect(getByTestId("chroma-hover-note")).toBeTruthy();
    await fireEvent.pointerLeave(box);
    expect(chromaLink.hover).toBe(null);
  });
});
