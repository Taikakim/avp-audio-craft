---
name: standalone-tools-at-projects-root
description: "Kim wants standalone tools in their own directory at /home/kim/Projects/ root, never nested inside an unrelated project"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a98a12e5-7f24-41e2-a736-c20b3ea25e1a
  modified: 2026-08-22T21:36:32.909Z
---

Itsenäiset työkalut kuuluvat omaan hakemistoonsa `/home/kim/Projects/` juureen, ei toisen projektin sisään. Kim huomasi kaidesuunnittelijan päätyneen polkuun `/home/kim/Projects/latents_sa3_morphIOI3/kaide` (Stable Audio -projektin sisään) ja pyysi siirtämään sen polkuun `/home/kim/Projects/kaide`.

**Why:** Sekaannus projektien välillä — Stable Audio -projektin hakemistoon kuulumaton työkalu hankaloittaa varmuuskopiointia, versionhallintaa ja projektin hahmottamista.

**How to apply:** Kun luot uuden itsenäisen työkalun tai projektin, sijoita se hakemistoon `/home/kim/Projects/<nimi>/` vaikka istunnon työhakemisto olisi jokin toinen projekti. Jos istunto on käynnistetty toisen projektin sisällä eikä uusi työ liity siihen, kysy tai valitse Projects-juuri. Liittyvä: [[kaide-railing-designer]]
