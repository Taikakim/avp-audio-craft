# Long-form block composition — idea note (not designed, not built)

Captured verbatim from Kim, 2026-08-13. Parked: shipping schedule is the three
deliverables; this is a future direction, not scoped or estimated.

## The idea

Revisit the long-form experiments — some of the last ones used the chroma
control to crossfade latents in tune. Also look at the **lsdj method** (in
`/project`) of building music in blocks.

Kim is "almost inclined to": generate one basic seed, then mix that into each
section's individual seed at ~50%, and build a track from a fixed-frame-size
(T=1024) block schedule, each block carrying its own prompt describing that
point in the track's arc:

```
intro
section1 w1
section2 w1
section1 w2
section3 w2
breakdown
section1 w0.6
section1 variation w2
section3 w1.5
section4 w1.5
outro
```

Overlap/crossfade at least the intro and outro joins.

## Open questions (unresolved — surface these before designing)

- What "mix that seed in at 50%" means mechanically: latent interpolation of
  two seeds' noise, a blend at a specific diffusion timestep, or something
  else.
- Whether "w" is a CFG/guidance weight per section, a mix ratio, or a distinct
  per-section control the chroma-crossfade work already defines.
- Overlap length and crossfade shape at the section joins.
- How per-section prompts are authored — free text per block, or templated
  from a shared track-arc description.

## Prior art to read before scoping

- The chroma-control crossfade-latents-in-tune experiment (last long-form
  round) — locate and read before designing anything new.
- The **lsdj method** referenced as living in `/project` (LUMI project dir) —
  not yet located or read.

## Status

Idea only. No design doc, no code. Revisit after the two-week deliverable
window (great-sounding AVP model / density adapter / melody head) closes.
