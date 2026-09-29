/**
 * HELP mode reads the `data-help` string of the nearest ancestor of whatever the
 * cursor is over — the port of v3's `onRootMove` (SA3 Studio v3.dc.html line 1619).
 * Kept out of the component so it is testable without mounting the shell.
 *
 * `root` guards the overlay case: the help tooltip is itself a root-level element,
 * and a stray hit outside the app must not freeze the last string on screen.
 */
export function helpTextAt(node: EventTarget | null, root?: Element | null): string | null {
  const el =
    node instanceof Element ? node : node instanceof Node ? node.parentElement : null;
  if (!el) return null;
  const hit = el.closest("[data-help]");
  if (!hit) return null;
  if (root && !root.contains(hit)) return null;
  const text = hit.getAttribute("data-help");
  return text && text.length > 0 ? text : null;
}
