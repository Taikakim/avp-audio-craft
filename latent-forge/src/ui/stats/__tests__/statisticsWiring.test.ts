import { describe, expect, it } from "vitest";
import { indexLabelsFor, laneCropIdSet } from "../statisticsWiring";

describe("laneCropIdSet keeps only crop-kind latents (spec §4.4 highlighting)", () => {
  it("collects crop_ids and drops other kinds", () => {
    const set = laneCropIdSet([
      { kind: "crop", crop_id: "a" },
      { kind: "path", path: "/x.npy" },
      { kind: "audio", audio: { kind: "crop", crop_id: "b" } },
      { kind: "crop", crop_id: "c" },
    ]);
    expect(set).toEqual(new Set(["a", "c"]));
  });

  it("is empty for an empty latents array -- 'nothing selected', never 'highlight everything'", () => {
    expect(laneCropIdSet([])).toEqual(new Set());
  });
});

describe("indexLabelsFor names each position matching timeseries[].index (spec §6.5)", () => {
  it("labels a crop latent by its crop_id", () => {
    expect(indexLabelsFor([{ kind: "crop", crop_id: "000412" }])).toEqual(["000412"]);
  });

  it("labels a path latent by its path", () => {
    expect(indexLabelsFor([{ kind: "path", path: "/SERVER/out/x.z0.npy" }])).toEqual(["/SERVER/out/x.z0.npy"]);
  });

  it("falls back to 'audio <i>' for a bare AudioRef latent, at its own index", () => {
    expect(
      indexLabelsFor([
        { kind: "crop", crop_id: "a" },
        { kind: "audio", audio: { kind: "upload", sha256: "f".repeat(64) } },
      ]),
    ).toEqual(["a", "audio 1"]);
  });
});
