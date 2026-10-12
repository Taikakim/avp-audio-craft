// Canvas plumbing shared by every canvas in the CHROMA tab.
//
// chromaColour() is the FLAT-colour path: borders, separators, tick labels,
// the red detune mark. Those come from getComputedStyle, per the project's
// canvas rule -- it is only a RAMP that must build its own oklch() string
// (see consonanceColor.ts).
//
// The per-token fallback is not defensive padding. HANDOUT.md measured it: an
// undefined custom property returns "", and `ctx.fillStyle = ""` is a SILENT
// NO-OP that leaves the previous colour on the context. In the app tokens.css
// is loaded and the fallback never fires; in a bare component render, or a
// test that forgot to seed a token, it is the difference between a readable
// canvas and garbage. (M1 T13's panelColour has no fallback, which is why this
// milestone does not reuse it -- see the plan's open questions.)

// COPIED VERBATIM from M1 T12's tokens.css :root block (M1:2925-2937) -- NOT
// from v3's canvas literals, which is where an earlier draft of this table
// came from and where every one of these eight values was subtly wrong:
// --panel carried --bg's 96%, --red was 58%/0.170 rather than 55%/0.20,
// --purple-strong was hue 285 rather than 300. A fallback that does not match
// the real token is worse than no fallback at all -- it silently renders a
// DIFFERENT canvas in exactly the situation it exists for. If tokens.css
// changes, this table changes in the same commit.
const FALLBACK: Record<string, string> = {
  "--panel": "oklch(93% 0.008 240)",
  "--panel2": "oklch(90% 0.012 240)",
  "--border": "oklch(80% 0.014 240)",
  "--text": "oklch(27% 0.02 250)",
  "--text-dim": "oklch(52% 0.016 250)",
  "--red": "oklch(55% 0.20 25)",
  "--turq-strong": "oklch(55% 0.11 195)",
  "--purple-strong": "oklch(54% 0.10 300)",
};

const LAST_RESORT = "oklch(58% 0.014 240)";

export const CHROMA_TOKEN_FALLBACK: Readonly<Record<string, string>> = FALLBACK;

export function chromaColour(el: Element, token: string): string {
  const raw = getComputedStyle(el).getPropertyValue(token).trim();
  if (raw) return raw;
  return FALLBACK[token] ?? LAST_RESORT;
}

export function fitChromaCanvas(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
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
