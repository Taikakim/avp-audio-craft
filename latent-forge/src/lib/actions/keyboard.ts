// The keyboard behaviour the existing app already has, kept verbatim through the
// re-home (spec §9.6): space play/pause, Home rewind, Delete removes the
// selected clip, +/- zoom.
//
// It lives here rather than in App.svelte so it survives the shell being
// rebuilt around it, and so it can be tested without mounting anything.

export const ZOOM_STEP = 1.4;

export interface KeyActions {
  togglePlay(): void;
  rewind(): void;
  deleteSelected(): void;
  zoomBy(factor: number): void;
}

/** True if the event came from somewhere the user is typing. */
function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || typeof el.tagName !== "string") return false;
  if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT") return true;
  return el.isContentEditable === true || el.getAttribute?.("contenteditable") === "true";
}

/** Handle one keydown. Returns true if it was ours. */
export function handleKey(e: KeyboardEvent, a: KeyActions): boolean {
  if (isTypingTarget(e.target)) return false;
  switch (e.key) {
    case " ":
      e.preventDefault();
      a.togglePlay();
      return true;
    case "Home":
      e.preventDefault();
      a.rewind();
      return true;
    case "Delete":
    case "Backspace":
      e.preventDefault();
      a.deleteSelected();
      return true;
    case "+":
    case "=":
      a.zoomBy(ZOOM_STEP);
      return true;
    case "-":
      a.zoomBy(1 / ZOOM_STEP);
      return true;
    default:
      return false;
  }
}

/** Bind to the window; the returned function unbinds. */
export function installGlobalKeys(a: KeyActions): () => void {
  const onKeydown = (e: KeyboardEvent) => {
    handleKey(e, a);
  };
  window.addEventListener("keydown", onKeydown);
  return () => window.removeEventListener("keydown", onKeydown);
}
