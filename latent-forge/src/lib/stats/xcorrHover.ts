// Pure pixel -> (row, col) mapping for the xcorr canvas's hover readout
// (spec §4.4: "hovering a cell reads out its (row, col) and value"). Kept
// out of the component so the boundary maths -- which cell a pixel lands
// in, and which pixels land in no cell at all -- can be pinned exactly under
// vitest without a real canvas.

export interface XcorrCell {
  row: number;
  col: number;
}

/**
 * `offsetX`/`offsetY` are pixels from the canvas's own top-left. `cellPx` is
 * xcorrCellSize's result (M1 T13's lib/math/axis.ts); `n` is the matrix side
 * length. Returns null for a pixel outside the drawn n x n grid -- the panel
 * is a fixed 300px square (spec §4.4) but the grid itself can be smaller
 * when `n * cellPx < 300`.
 */
export function xcorrCellAt(offsetX: number, offsetY: number, cellPx: number, n: number): XcorrCell | null {
  if (!Number.isFinite(offsetX) || !Number.isFinite(offsetY) || offsetX < 0 || offsetY < 0) return null;
  if (!Number.isFinite(cellPx) || cellPx <= 0 || !Number.isFinite(n) || n <= 0) return null;
  const col = Math.floor(offsetX / cellPx);
  const row = Math.floor(offsetY / cellPx);
  if (row < 0 || row >= n || col < 0 || col >= n) return null;
  return { row, col };
}
