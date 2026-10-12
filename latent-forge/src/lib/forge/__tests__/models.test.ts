import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchFilmCkpts, fetchSlots } from "../models";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

afterEach(() => vi.unstubAllGlobals());

describe("fetchFilmCkpts", () => {
  // WINTERMUTE 2026-09-25 (critic follow-up #1): there is no "film" family. FiLM checkpoints are
  // family "control_adapter" with control_mode "scalar" -- the only mode _install_film's
  // ScalarAttributeEncoder can load.
  it("asks /models for the control_adapter family", async () => {
    const fetchMock = vi.fn(async (_url: string) => jsonResponse({ ok: true, models: [{ path: "/SERVER/f.pt", label: "f", control_mode: "scalar" }] }));
    vi.stubGlobal("fetch", fetchMock);
    const out = await fetchFilmCkpts();
    expect(fetchMock.mock.calls[0][0]).toBe("/models?family=control_adapter");
    expect(out.map((m) => m.path)).toEqual(["/SERVER/f.pt"]);
  });

  it("keeps only control_mode 'scalar' rows -- any other mode would load the wrong encoder", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: true, models: [
      { path: "/SERVER/film.pt", label: "film", control_mode: "scalar" },
      { path: "/SERVER/melody.pt", label: "melody", control_mode: "melody_contour" },
      { path: "/SERVER/dual.pt", label: "dual", control_mode: "dual_scalar" },   // not "scalar"
      { path: "/SERVER/attr.pt", label: "attr", control_mode: "attribute" },
      { path: "/SERVER/unprobed.pt", label: "unprobed", control_mode: null },
      { path: "/SERVER/missing.pt", label: "missing" },
    ] }));
    const out = await fetchFilmCkpts();
    expect(out.map((m) => m.path)).toEqual(["/SERVER/film.pt"]);
  });

  it("returns an empty list, not a throw, when the server refuses", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "no film root" }, 200));
    await expect(fetchFilmCkpts()).resolves.toEqual([]);
  });

  // Verified directly against eval/explorer_render_server.py:977-997 (the real /models route):
  // the response key is "models", not "ckpts". M1's fetchAdapters read body.ckpts until the
  // reconcile pass of 2026-09-25 fixed it at source; this function reads `models` too. Task 10's
  // recorded-response contract tests check both against the real server's recordings
  // (models_adapters and models_control_adapters, M2 T15).
  it("reads the 'models' key, not 'ckpts' (the real server's field name)", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: true, models: [{ path: "/SERVER/g.pt", label: "g", control_mode: "scalar" }] }));
    const out = await fetchFilmCkpts();
    expect(out).toHaveLength(1);
  });
});

describe("fetchSlots", () => {
  it("parses the real /slots shape (eval/adapter_slots.py Slot.as_dict + _slot_state)", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({
      ok: true, active: 0, backbone: "medium-base",
      slots: [{ index: 0, path: "/SERVER/a.safetensors", label: "a", family: "adapter", cost_gb: 1.2, strength: 1.0 }],
      max_slots: 4, vram_floor_gb: 6.0, free_gb: 9.4,
    }));
    const out = await fetchSlots();
    expect(out.slots).toHaveLength(1);
    expect(out.slots[0].label).toBe("a");
    expect(out.max_slots).toBe(4);
  });

  it("returns an empty slot table rather than throwing on a malformed body", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false }));
    const out = await fetchSlots();
    expect(out.slots).toEqual([]);
  });
});
