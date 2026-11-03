---
name: kaide-railing-designer
description: "Kim's wooden stair-railing design tool lives at /home/kim/Projects/kaide/ — self-contained HTML, opened directly, no server"
metadata: 
  node_type: memory
  type: project
  originSessionId: a98a12e5-7f24-41e2-a736-c20b3ea25e1a
  modified: 2026-08-22T21:36:52.335Z
---

Kaidesuunnittelija (puinen porraskaide) sijaitsee polussa `/home/kim/Projects/kaide/`: `kaide-suunnittelu.html`, käynnistysskripti `avaa-kaide.sh` ja `lib/` (three.js r128 + OrbitControls paikallisina). Siirretty sinne 2026-08-23 Stable Audio -projektin alta.

Kohde on Kimin oma porrasaukko: portaikon leveys 550 mm, joka **ei saa muuttua** — reitti määrittää aukon mitat ja "tolppalinjan etäisyys reunasta" siirtää tolppia, ei kutista aukkoa.

**Why:** Työkalu on tavallinen HTML-tiedosto ilman rakennusvaihetta tai palvelinta; `lib/` on paikallinen jotta se toimii ilman verkkoa. Ohjelman vakioasetukset on viritetty vastaamaan Kimin todellista rakennetta (tolppa 75×75, korkeus 1050, käsijohde 25×60, aukon siirtymä 37,5 mm).

**How to apply:** Avaa `xdg-open /home/kim/Projects/kaide/kaide-suunnittelu.html` tai aja `avaa-kaide.sh`. Älä riko `lib/`-kansion ja HTML:n suhdetta — ilman sitä työkalu putoaa CDN-varajärjestelmään ja vaatii verkon. Käyttäjän omat esiasetukset ovat selaimen localStoragessa, eivät tiedostossa. Liittyvä: [[standalone-tools-at-projects-root]]
