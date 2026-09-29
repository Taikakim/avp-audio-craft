import { describe, expect, it } from "vitest";
import type { Peaks } from "../waveform";
import { clipMarkColumns } from "../clipMarks";

function peaks(pairs: [number, number][]): Peaks {
  const data = new Float32Array(pairs.length * 2);
  pairs.forEach(([lo, hi], i) => {
    data[i * 2] = lo;
    data[i * 2 + 1] = hi;
  });
  return { data, columns: pairs.length };
}

describe("clip marks (spec §4.3: red 2px marks where |x| > 1)", () => {
  it("flags a column whose peak exceeds full scale either way", () => {
    const p = peaks([[-0.5, 0.5], [-1.2, 0.9], [-0.3, 1.05], [-0.9, 0.9]]);
    expect(clipMarkColumns(p)).toEqual([1, 2]);
  });

  it("flags nothing when every column is within [-1, 1]", () => {
    const p = peaks([[-1, 1], [-0.999, 0.999]]);
    expect(clipMarkColumns(p)).toEqual([]);
  });
});
