// Turns an overlap's two clips into the info line spec §4.6.1 asks for ("which
// overlap, its two clip names"). ForgeClip has no `name` field -- only an
// AudioRef -- so "name" means whatever's most readable per ref kind, the same
// idea as v3's own `{{overlapInfo}}` (design_handoff/SA3 Studio v3.dc.html:2078),
// which showed `a.file -> b.file`.

import type { ForgeClip } from "./types";

const PLACEHOLDER = "?";

export function clipLabel(clip: ForgeClip | undefined): string {
  if (!clip) return PLACEHOLDER;
  const ref = clip.audio;
  switch (ref.kind) {
    case "crop": return ref.crop_id;
    case "render": return ref.file;
    case "file": return ref.rel.split(/[\\/]/).pop() ?? ref.rel;
    case "path": return ref.path.split(/[\\/]/).pop() ?? ref.path;
    case "upload": return ref.sha256.slice(0, 8);
  }
}

export function overlapInfoLine(
  overlap: { lane: 0 | 1 | 2 | 3; start_sec: number; end_sec: number },
  a: ForgeClip | undefined,
  b: ForgeClip | undefined,
): string {
  return (
    `lane ${overlap.lane + 1} · ${clipLabel(a)} → ${clipLabel(b)} · ` +
    `mask ${overlap.start_sec.toFixed(2)}–${overlap.end_sec.toFixed(2)} s`
  );
}
