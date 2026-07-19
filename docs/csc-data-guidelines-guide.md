# CSC data-movement & dataset guidelines — context-relevant notes

*2026-07-15, THE-FINN, for CONTINUITY. Sourced from docs.csc.fi's
`data/moving/` (+ its `rsync`, `tar_ssh`, `scp` sub-pages), `data/datasets/dataset-sources/`,
`data/datasets/publishing-datasets/`, and `data/Allas/introduction/` — fetched directly, not
from memory. Companion to `docs/lumi-throughput-workflow-guide.md` (job launching); this one
is about getting DATA on and off the machine, and about the AVP open-dataset release's
publishing question. Assumes `docs/lumi-transition-plan.md` and `lumi/README.md` are already
read — doesn't re-explain what we already have right (containers, storage tiers), only what
these pages add, correct, or unblock.*

---

## 1. What tool for what data shape (the actual question we have)

CSC's own framing (`data/moving/tar_ssh/`, verbatim): *"scp and rsync are commonly used... however, these tools are not very practical for moving many small files."* That's exactly our `latents_sa3`/`timeseries` shape — thousands of small per-crop `.npy`/`.json` files, not a few big blobs. Three tools, three shapes:

| Our data | Right tool | Why |
|---|---|---|
| **`latents_sa3`/`latents_avp`/`timeseries` corpora** (thousands of small files) | **`tar` piped over `ssh`**, not rsync | CSC's exact use case. Command (adapted to our project): `ssh akekim@lumi.csc.fi 'tar c -C /scratch/project_465003186 latents_sa3' > /project/465003186/backup/latents_sa3.tar` — writes the archive directly at the destination (also saves source-side disk, useful given the single-copy-latents risk noted below). **Drop `-v`**: CSC's own tip — verbose per-file listing measurably slows the transfer at high file counts, exactly our count. This is what `pack_data.sh` already does (tarball-then-transfer) — confirms the existing approach is right, not a workaround.
| **Checkpoints, configs, one-off files** (few, larger) | **rsync** | `rsync -rP <local> akekim@lumi.csc.fi:/scratch/project_465003186/...` — the `-P` (`--partial --progress`) combo is what makes an interrupted upload resumable, which matters given the SSH-cert-expiry-mid-transfer issue already in `lumi/README.md`. **Add `--partial` explicitly if scripting** (some `-P` shorthand behavior varies by rsync version — safer to spell it out in `pack_data.sh` and any future transfer script).
| **LUMI-to-LUMI or cross-system** (e.g. staging Mantu-derived data via an intermediate CSC system, or a future Puhti/Mahti step) | **rsync, direct machine-to-machine** | `rsync -rP /scratch/project_A/myfiles user@othersystem.csc.fi:/scratch/project_B` — needs **SSH agent forwarding** for the auth chain (CSC's explicit note); this is a *different* CSC system class than our LUMI-only setup today, flag as future-relevant only.

**One correction worth a line in `lumi/README.md`'s SSH section:** the "SSH certs expire, ~10h validity" note there is about EFP's cert (`efp.lumi.csc.fi`, confirmed in our own README). CSC's rsync page separately mentions a **24-hour cert requirement for a system called "Roihu"** — that's a *different* CSC machine, not LUMI/EFP. Worth a one-line disambiguation in the README so nobody later conflates the two cert lifetimes when troubleshooting an expired-cert error.

---

## 2. Allas — a candidate fix for the standing cold-backup risk

The team has flagged, repeatedly, that `latents_sa3` is a "single copy." **Correction (Kim,
2026-07-19): it is NOT** — a second local copy exists at
`/run/media/kim/Mantu/sa3-latents_backup/latents_sa3/` (verified complete, 27003/27003, in
parity as of 07-12). So there is already local redundancy; the residual risk is only that the
Mantu sync is *manual* ("as long as it's kept up to date" — Kim), and an off-site copy would
add geographic redundancy. That off-site copy should go to **LUMI-O** (§4.1), not Allas. Allas
is only worth noting for completeness of the CSC picture:

- **What it is:** CSC's general-purpose object storage (CEPH-backed, S3/Swift-compatible),
  reachable from CSC systems *and* the open internet — not just from inside a job.
- **Fits our access pattern:** explicitly recommended for *"collecting and hosting cumulating
  or changing data"* — our corpora (goa/avp/genre-corpora timeseries) are exactly this: a
  growing, append-only collection, not a live-mutating database (which Allas explicitly says
  it's *not* suited for).
- **Quota headroom:** 10 TB default per project (expandable on request), individual objects
  ideally under 100 GB. Our latents-redundancy risk (`latents_sa3` ~13 GB + `timeseries`
  ~21 GB, growing with the expanded-Essentia sweep's `.TIMESERIES.npz` fields) fits inside the
  default quota with a lot of room to spare even after growth.
- **Billing:** 1.05 Storage Billing-Units per TiB-hour, no separate transfer/API fees — cheap
  relative to the GCD-hour budget concerns that dominate the compute side.

**RESOLVED 2026-07-19 (WINTERMUTE, checked LUMI's own docs):** Allas and LUMI-O are
**SEPARATE** services with separate identities — LUMI-O is the Ceph/S3 endpoint at
`lumidata.eu` (credentials from `auth.lumidata.eu` / the `lumio-conf` tool, project-scoped,
auto-creates `lumi-<proj>-private`/`-public` rclone remotes); CSC Allas is a different Ceph/S3
endpoint at `a3s.fi` with separate CSC-project auth. Both are Ceph/S3 under the hood but a
LUMI-O token does **not** authenticate to Allas — not interchangeable. **Conclusion for the
`latents_sa3` cold-backup: use LUMI-O, not Allas** — Kim already holds LUMI project
`465003186`, `pack_data.sh` already assumes LUMI-O, and no separate CSC/Allas allocation is
needed. Remaining step is Kim-only (an instance can't do it): generate the LUMI-O token at
`auth.lumidata.eu` (web login), after which `pack_data.sh` → `rclone copy` to the
`lumi-465003186-private` bucket is scriptable. So the earlier "consider Allas" framing in §2
above is superseded — the answer is LUMI-O.

---

## 3. Dataset publishing — directly relevant to the AVP open-dataset release

`data/datasets/publishing-datasets/` and `data/datasets/dataset-sources/` describe CSC's own
recommended practice for publishing a research dataset — and it lines up with, rather than
changes, the design already committed in
`mir/docs/superpowers/specs/2026-07-09-avp-dataset-release-design.md`:

- **Persistent identifiers (DOI/URN)** are CSC's recommended practice for anything published —
  our own release design doesn't yet name a specific PID scheme; worth adding one when the
  release firms up, and CSC's own **Fairdata/IDA** services (referenced on the dataset-sources
  page) are a plausible place to mint one without standing up separate infrastructure, *if* the
  team ever wants the release hosted through CSC rather than (or alongside) a lab's own site.
- **Licensing: CC BY is CSC's stated default recommendation** for open data — this **matches**
  the release design's own already-made decision (CC-BY 4.0, chosen specifically because it
  "keeps the dataset usable by labs" and permits ML training) — a confirmation, not a change.
- **Metadata should carry**: a persistent identifier, creator/contributor/publisher info, and
  explicit rights/restriction info per item — this maps directly onto the release design's
  per-layer `LICENSES.md` idea (§3, model-generated layers riding their upstream licenses,
  Kim's own creator-authored content under CC-BY) — CSC's guidance gives a concrete metadata
  shape to fill in, not a new requirement.
- **Preservation planning ("when the research project ends")** is flagged as a publishing
  consideration on the CSC page but isn't yet addressed anywhere in our own release design —
  a genuine gap worth a line in the design doc if CSC infrastructure (IDA/Fairdata) ends up
  hosting any part of the release.

**Not claiming this changes the release plan** — the team's own design already independently
arrived at the CC-BY / per-layer-licensing / provenance-first shape CSC recommends. The useful
part is confirmation plus a concrete PID/hosting option (Fairdata/IDA) if a CSC-hosted release
is ever preferred over (or alongside) a third-party host.

---

## 4. Open items — needs verification before relying on this in production

1. ~~**Allas vs. LUMI-O**: same service, sibling services, or unrelated?~~ **RESOLVED 2026-07-19 (W):** separate services (lumidata.eu vs a3s.fi), not interchangeable — use LUMI-O for our backup. See §2.
2. **Allas reachability from LUMI compute nodes** — moot for our purpose now that LUMI-O (not Allas) is the chosen backend; LUMI-O is reachable from anywhere over the internet, and backup runs from the login node / a local box anyway, not compute nodes.
3. **Roihu vs. LUMI/EFP SSH cert lifetimes** — confirmed as two different systems/cert schemes above; don't let a 24h-vs-10h discrepancy read as a bug in either.
4. **Whether Fairdata/IDA are viable for a CSC-hosted AVP release** — only referenced in passing on the dataset-sources page, not investigated in depth here; a genuine follow-up if a CSC-hosted release is ever preferred over a third-party host (e.g. Hugging Face, Zenodo).

## Sources
- https://docs.csc.fi/data/moving/
- https://docs.csc.fi/data/moving/rsync/
- https://docs.csc.fi/data/moving/tar_ssh/
- https://docs.csc.fi/data/datasets/dataset-sources/
- https://docs.csc.fi/data/datasets/publishing-datasets/
- https://docs.csc.fi/data/Allas/introduction/
