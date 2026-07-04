# Mood tag vocabulary — APPROVED (goa corpus, 2676 tracks)

*Kim delegated the veto 2026-07-05 ("i trust your opinion here") — vocabulary as proposed. His steering hypothesis, folded into the plan: within goa, RELEASE YEAR will steer strongest.*

*2026-07-05, CONTINUITY. From W's feature table (adaptive per-tag P75 attach
threshold on nonzero probs). Goa-only numbers; bands recompute per training mix
when the 4 new corpora land. Genre vocab untouched (12-label style set + finer
discogs lane incoming from W).*

## Proposed vocabulary (9 tags)

| tag | tracks | prev% | action |
|---|---|---|---|
| space | 625 | 23.4 | keep |
| energetic | 610 | 22.8 | keep |
| melodic | 594 | 22.2 | keep |
| dark | 347 | 13.0 | keep |
| retro | 279 | 10.4 | keep |
| **meditative** | ~127 | ~4.7 | **merge**: relaxing (74) + meditative (52) + calm (1) — r=.73/.30 |
| dream | 111 | 4.1 | keep (r=.44 with space, .40 with relaxing — but distinct enough) |
| soundscape | 106 | 4.0 | keep (texture word; r=.68 with meditative but prompt-useful on its own) |
| **cinematic** | ~85 | ~3.2 | **merge**: film (54) + epic (31) — r=.44, both sub-bar alone |

## Dormant (not deleted — may revive when chill/prog corpora land)

happy, uplifting, party, summer, positive, emotional, deep (46, sub-bar),
slow, background — all currently <75 tracks in goa. Recount per training mix.

## Dropped (functional/library tags, meaningless here)

corporate, advertising, commercial, motivational, inspiring, sport, game,
trailer, documentary, christmas, movie, drama/dramatic, action, fun/funny,
love, romantic, sad, powerful, heavy, adventure, upbeat.

## Findings worth knowing

1. **retro ~ energetic r=0.75** — in this corpus, old-school goa IS the
   high-energy goa. They are kept separate (not synonyms; the correlation is
   corpus structure), but note the confound: the model may partially learn
   "retro" from energy. The year lane carries era independently, which helps.
2. Nothing exceeds 50% prevalence (max 23.4%) — no ceiling violations; the
   goa corpus mood distribution is healthily contrastive.
3. Attach thresholds are per-tag P75 of nonzero probs (range 0.03-0.34) —
   a fixed global cutoff would have gutted dark (P75=0.036) or over-attached
   melodic (P75=0.337).
