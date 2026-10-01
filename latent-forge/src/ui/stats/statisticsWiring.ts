// Pure request/label wiring for StatisticsView (spec §4.4, §6.5), split out
// so the crop_id highlight set and the per-index legend labels can be pinned
// under vitest without mounting the three panel components.
import type { LatentRef } from "../../lib/forge/types";

/** Only "crop" latents carry a crop_id XYPanel can match against
 *  /forge/dataset_scalars's own crop_id points; other kinds contribute
 *  nothing to the highlight set rather than being coerced into one. */
export function laneCropIdSet(latents: readonly LatentRef[]): Set<string> {
  return new Set(latents.flatMap((l) => (l.kind === "crop" ? [l.crop_id] : [])));
}

/** One label per position in `latents`, matching timeseries[].index (spec
 *  §6.5): the crop_id or path it names, or "audio <i>" for a bare AudioRef
 *  latent, which carries no name of its own at this layer. */
export function indexLabelsFor(latents: readonly LatentRef[]): string[] {
  return latents.map((l, i) => {
    if (l.kind === "crop") return l.crop_id;
    if (l.kind === "path") return l.path;
    return `audio ${i}`;
  });
}
