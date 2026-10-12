import { describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../forge/defaults";
import { applyServerPreset } from "../renderPresets";

// Shape of eval/presets/v7-full-32clips-localtempo/skipped.json (GET /presets/{name}).
const V7 = {
  name: "v7-full-32clips-localtempo/skipped",
  notes: "...",
  schema: 1,
  payload: {
    cfg_scale: 6.0,
    dora: { ckpt_path: "/x/epoch=4-step=1495.weights.ckpt", strength: 1.0 },
    duration: 14.11,
    prompt: "goa trance, psytrance, rolling bassline",
    steps: 24,
  },
};

describe("applyServerPreset", () => {
  it("maps a /generate recipe onto RenderSettings and returns its adapter", () => {
    const s = cloneRenderSettings(BASE_DEFAULTS);
    const r = applyServerPreset(s, V7);
    expect(r.rejected).toEqual([]);
    expect(s.prompt).toBe("goa trance, psytrance, rolling bassline");
    expect(s.cfg_scale).toBe(6.0);
    expect(s.steps).toBe(24);
    expect(s.duration_sec).toBe(14.11);
    expect(r.ckptPath).toBe("/x/epoch=4-step=1495.weights.ckpt");
  });

  it("rejects a body without a payload and an out-of-range duration", () => {
    const s = cloneRenderSettings(BASE_DEFAULTS);
    expect(applyServerPreset(s, { name: "x" }).rejected).toEqual(["<body>"]);
    const r = applyServerPreset(s, { payload: { duration: 999 } });
    expect(r.rejected).toEqual(["duration"]);
    expect(r.ckptPath).toBeUndefined();
  });
});
