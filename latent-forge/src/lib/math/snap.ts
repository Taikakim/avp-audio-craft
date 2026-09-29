// PROVISIONAL — Task 1 (arrangement store) needs the `SnapMode` type to exist
// before Task 2 (snapping and downbeat coincidence) is dispatched. This file
// carries ONLY that type, exactly as Task 2's own brief specifies it (spec
// §4.3's eight modes, "lane" = downbeats/magnetic, in menu order). Task 2
// owns this file for real: it adds `SNAP_MODES`, `MAGNET_PX`,
// `gridIntervalSec`, `SnapContext`, `SnapResult`, `snapDelta`, `snapSec` and
// their vitest coverage. A type alone needs no test (no runtime behaviour) —
// the "every pure function in lib/math/ is covered by vitest" constraint
// does not apply until Task 2 adds functions here.
export type SnapMode = "bar" | "beat" | "1/8" | "1/16" | "1/32" | "lane" | "edge" | "free";
