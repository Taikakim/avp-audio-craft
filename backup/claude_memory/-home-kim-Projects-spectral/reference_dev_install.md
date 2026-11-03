---
name: Spectral Forge dev install workflow
description: How to build and install the dev-identity plugin for testing in Bitwig
type: reference
originSessionId: cd4df882-0456-4abe-ad52-476a875f03c6
---
The dev plugin must have a different CLAP ID than the release version, otherwise Bitwig confuses them and may load the wrong one silently.

**Build:** `cargo build --release --features dev-build`
- The `dev-build` Cargo feature (in `Cargo.toml:35`) cfg-gates `CLAP_ID`/`VST3_CLASS_ID`/`NAME` overrides in `src/lib.rs`.

**Install:** `cp target/release/libspectral_forge.so ~/.clap/spectral/dev/spectral_dev.clap`
- The .so is just a Linux .clap with the wrong extension; rename when installing.
- Note the path: `~/.clap/spectral/dev/spectral_dev.clap` — NOT `~/.clap/spectral_forge.clap`.

**Why this matters:** until 2026-05-05, dispatched implementers were installing to `~/.clap/spectral_forge.clap` which Bitwig was ignoring. All "fix didn't work" reports against post-fix builds were actually testing pre-fix code at the dev path. Don't make this mistake again.
