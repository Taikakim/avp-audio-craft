// Shared sizing for the timeline's left gutter. The ruler-transport cell
// (Ruler.svelte, M5 T3 -- was RulerTransport.svelte until this task deleted
// it) and every lane header (Timeline.svelte) sit in the same column and
// must be pixel-identical, or the ruler's ticks/bar numbers drift out of
// alignment with the lane grid, clips and playhead below them.
// One constant, read by both -- do not hardcode this width in either file.
export const RULER_GUTTER_PX = 250;
