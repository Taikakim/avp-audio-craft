// Spec §4.2: while a commit runs, the MIXDOWN button reads the remaining step
// count and is non-interactive. M1 only ever calls this with busy = false; the
// copy is fixed and tested here so M9 wires progress to it without re-deciding it.

export const MIXDOWN_IDLE_LABEL = "▸ MIXDOWN";

export function mixdownLabel(busy: boolean, stepsLeft: number | null): string {
  if (!busy) return MIXDOWN_IDLE_LABEL;
  return `SAMPLING · ${stepsLeft ?? 0} steps left`;
}
