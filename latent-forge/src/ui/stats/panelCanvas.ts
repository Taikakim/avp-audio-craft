// devicePixelRatio fitting and token lookup for the statistics canvases.
//
// Global constraint (spec §9.1): canvas code never hardcodes a colour. Every
// colour is read from the live computed style, once per frame, so DARK works
// without the canvases knowing the theme exists.

export function fitPanelCanvas(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w <= 0 || h <= 0) return null;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return ctx;
}

/** `panelColour(canvas, "--border")` -> the resolved colour for the current theme. */
export function panelColour(canvas: HTMLCanvasElement, token: string): string {
  return getComputedStyle(canvas).getPropertyValue(token).trim();
}
