// Spec §4.5: the tab row and its right-aligned per-tab hint. The strings are the
// spec's verbatim (v3 line 1996-1998 carries the same four).
//
// BottomTabId is the view store's (Task 7) -- it is the type of `view.bottomTab`,
// so the store cannot import it from here without a cycle. Re-exported so a tab
// consumer has one import.
import type { BottomTabId } from "../../lib/stores/view.svelte";
export type { BottomTabId };

export const BOTTOM_TABS: { id: BottomTabId; label: string }[] = [
  { id: "chroma", label: "CHROMA" },
  { id: "prompt", label: "PROMPT + SIGMA" },
  { id: "mix", label: "MIX + SIGNAL PATH" },
  { id: "terminal", label: "TERMINAL" },
];

export function bottomHint(tab: BottomTabId): string {
  switch (tab) {
    case "chroma":
      return "hover the heatmap to read a frame";
    case "prompt":
      return "settings follow the selection";
    case "mix":
      return "lane order feeds the mix nodes";
    case "terminal":
      return "stdout of the running job";
  }
}
