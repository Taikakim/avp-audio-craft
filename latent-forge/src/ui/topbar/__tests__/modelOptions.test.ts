import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAdapters } from "../../../lib/forge/models";
import { BACKBONE_IDS, buildModelOptions } from "../modelOptions";

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("the MODEL select lists backbones first, then adapters (spec §4.2)", () => {
  it("lists exactly the four backbones when no adapter is loadable", () => {
    const options = buildModelOptions([]);
    expect(options.map((o) => o.value)).toEqual([
      "medium", "medium-base", "small-music", "small-music-base",
    ]);
    expect(BACKBONE_IDS).toHaveLength(4);
    expect(options.every((o) => o.group === "backbone" && o.ckptPath === null)).toBe(true);
  });

  it("appends adapters after the backbones and carries their checkpoint path", () => {
    const options = buildModelOptions([
      { path: "/SERVER/ckpts/custom_v3.safetensors", name: "custom_v3.safetensors", label: "custom_v3 (LatCH medium)" },
      { path: "/SERVER/ckpts/custom_v2.ckpt", name: "custom_v2.ckpt" },
    ]);
    expect(options).toHaveLength(6);
    expect(options[4]).toEqual({
      value: "/SERVER/ckpts/custom_v3.safetensors",
      label: "custom_v3 (LatCH medium)",
      group: "adapter",
      ckptPath: "/SERVER/ckpts/custom_v3.safetensors",
    });
    expect(options[5].label).toBe("custom_v2.ckpt");
  });

  it("drops duplicates and entries with no path", () => {
    const options = buildModelOptions([
      { path: "/SERVER/ckpts/a.ckpt", name: "a" },
      { path: "/SERVER/ckpts/a.ckpt", name: "a again" },
      { path: "", name: "nameless" },
    ]);
    expect(options.filter((o) => o.group === "adapter")).toHaveLength(1);
  });
});

describe("fetchAdapters", () => {
  it("asks for loadable adapters only, and reads the array the real route returns under `models`", async () => {
    // The real /models answers {ok, count, models, stale_root_ids} (eval/explorer_render_server.py,
    // the /models route). This mock said `ckpts` until the reconcile pass of 2026-09-25, so it agreed
    // with a client that read the wrong key and resolved [] against the real server. M7 T10's
    // recorded-response contract test checks the same key against the RECORDED models_adapters.json.
    const fetchMock = vi.fn(async (_input?: RequestInfo | URL) => jsonResponse({
      ok: true, count: 1, models: [{ path: "/SERVER/x.ckpt", name: "x.ckpt" }], stale_root_ids: [],
    }));
    vi.stubGlobal("fetch", fetchMock);
    const out = await fetchAdapters();
    expect(fetchMock.mock.calls[0][0]).toBe("/models?family=adapter&loadable=1");
    expect(out).toEqual([{ path: "/SERVER/x.ckpt", name: "x.ckpt" }]);
  });

  it("returns an empty list rather than throwing when the server has no adapter index", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "no adapter root mounted" }, 200));
    await expect(fetchAdapters()).resolves.toEqual([]);
  });
});
