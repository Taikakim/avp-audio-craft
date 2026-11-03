---
name: Key data paths
description: Locations of crops, latents, stems, and other large data directories
type: project
---

Full-mix crops (with .INFO sidecars): `/home/kim/Projects/goa_crops`
Full-mix latents (.npy): `/run/media/kim/Lehto/latents` (also `goa-small` alias)
Stem latents (.npy): `/run/media/kim/Lehto/latents_stems`
Separated source audio: `/run/media/kim/Mantu/ai-music/Goa_Separated`
Separated crops (old path, may still be referenced in config): `/run/media/kim/Mantu/ai-music/Goa_Separated_crops`

tracks.csv (Shape Explorer Beat Match): `plots/tracks.csv`
— generated from .INFO files in the crops dir via DataStore.bootstrap() + to_csv()
— stems have no .INFO files; running bootstrap on stem dirs produces empty output
— only consumed by Latent Shape Explorer (Beat Match feature)
