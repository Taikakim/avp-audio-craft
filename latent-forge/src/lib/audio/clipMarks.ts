// Where the master strip draws its red 2px clipping marks (spec §4.3): any
// peak column whose min or max sample left [-1, 1].
import type { Peaks } from "./waveform";

export function clipMarkColumns(peaks: Peaks): number[] {
  const out: number[] = [];
  for (let i = 0; i < peaks.columns; i++) {
    const lo = peaks.data[i * 2];
    const hi = peaks.data[i * 2 + 1];
    if (lo < -1 || hi > 1) out.push(i);
  }
  return out;
}
