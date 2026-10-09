import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAdapters } from "../../../lib/forge/models";
import { BACKBONE_IDS, buildModelOptions, epochLabel, modelMenu } from "../modelOptions";

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

describe("the MODEL select lists a run once and its epochs beside it", () => {
  const RUN_A = "/SERVER/runs/winning_goa_t512_a128_fp32";
  const RUN_B = "/SERVER/runs/other_arm";
  const rows = [
    { path: `${RUN_A}/epoch=19-step=13500.weights.ckpt`, label: "winning_goa", epoch: 19, step: 13500 },
    { path: `${RUN_A}/epoch=67-step=45900.weights.ckpt`, label: "winning_goa", epoch: 67, step: 45900 },
    { path: `${RUN_B}/epoch=3-step=900.weights.ckpt`, label: "other_arm", epoch: 3, step: 900 },
    { path: `${RUN_A}/epoch=45-step=30600.weights.ckpt`, label: "winning_goa", epoch: 45, step: 30600 },
    { path: "/SERVER/ckpts/loose.ckpt", name: "loose.ckpt" },
  ];
  const options = buildModelOptions(rows);

  it("carries epoch and step through when the server recorded them, and leaves them off when it did not", () => {
    expect(options[4]).toMatchObject({ epoch: 19, step: 13500 });
    expect("epoch" in options[8]).toBe(false);
  });

  it("gives one primary entry per run, in the order the runs first appear, with the epoch count", () => {
    const { primary } = modelMenu(options, "medium");
    expect(primary.map((o) => o.label)).toEqual([
      "medium", "medium-base", "small-music", "small-music-base",
      "winning_goa (3 ep)", "other_arm", "loose.ckpt",
    ]);
  });

  it("an unselected run stands for its newest epoch", () => {
    const { primary } = modelMenu(options, "medium");
    expect(primary[4].value).toBe(`${RUN_A}/epoch=67-step=45900.weights.ckpt`);
    expect(modelMenu(options, "medium").epochs).toEqual([]);          // a backbone has no epochs
  });

  it("the run holding the selection stands for the selected epoch, and its epochs list newest first", () => {
    const picked = `${RUN_A}/epoch=45-step=30600.weights.ckpt`;
    const { primary, epochs } = modelMenu(options, picked);
    expect(primary[4].value).toBe(picked);                              // so the primary select still shows it
    expect(epochs.map((o) => o.epoch)).toEqual([67, 45, 19]);
    expect(epochs.map((o) => epochLabel(o))).toEqual(["ep 67 · 45900", "ep 45 · 30600", "ep 19 · 13500"]);
  });

  it("a run with one epoch still shows it; a checkpoint with none shows no epoch select", () => {
    expect(modelMenu(options, `${RUN_B}/epoch=3-step=900.weights.ckpt`).epochs.map((o) => o.epoch)).toEqual([3]);
    expect(modelMenu(options, "/SERVER/ckpts/loose.ckpt").epochs).toEqual([]);
    expect(epochLabel(options[8])).toBe("loose.ckpt");
  });

  it("groups Windows-style paths by folder too", () => {
    const win = buildModelOptions([
      { path: "D:\runs\a\e1.ckpt", label: "a", epoch: 1 },
      { path: "D:\runs\a\e2.ckpt", label: "a", epoch: 2 },
    ]);
    expect(modelMenu(win, "medium").primary.filter((o) => o.group === "adapter")).toHaveLength(1);
  });

  it("every option the primary select offers is a real checkpoint path, so onmodel() needs no translation", () => {
    const values = new Set(options.map((o) => o.value));
    for (const o of modelMenu(options, "medium").primary) expect(values.has(o.value)).toBe(true);
  });
});
