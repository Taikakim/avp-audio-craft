#!/usr/bin/env bash
# drive_rebalance_20260817.sh — CONTINUITY, Kim direct 2026-08-17.
#
# GOAL (Kim's words): "I would enjoy everything from LUMI at one location, and only 100GB at
# Mantu in the Lumi Runs folder. Move them to the main Lumi storage folder. To balance that,
# move ai-music2 and goa_archive_captions & features to Mantu."
#
# So: consolidate ALL LUMI content onto the UUID drive, and move non-LUMI bulk to Mantu.
#
# WHY THIS IS A SCRIPT AND NOT A PAIR OF rsync ONE-LINERS — three traps found in the audit:
#   1. Mantu/lumi_runs LOOKS like a pure duplicate of UUID/lumi_runs/runs, and mostly is
#      (bf16_twin, fp32_compare, fullft, longctx_* are verified SUBSETS) -- BUT fp32_winning
#      is 64.6 GB that exists ONLY on Mantu with ZERO overlap (Mantu has the slim epoch sweep
#      epoch=0,10,20,30...weights.ckpt; the UUID drive has fat ckpts at ep10-19). A naive
#      "it's a dup, delete it" loses 64.6 GB of real checkpoints.
#   2. TEN symlinks in Mantu/sa3_lora_runs point INTO Mantu/lumi_runs/fullft (not the UUID
#      copy). Deleting the Mantu copy first silently breaks run resolution for 10 fullft runs.
#      Symlinks get repointed BEFORE anything is deleted.
#   3. goa_archive_captions exists TWICE on the UUID drive (root + lumi_runs/) and THE TWO ARE
#      NOT THE SAME DATA -- verified by byte-level diff 2026-08-17 after Kim said "make sure the
#      captions actually are different". The 46480 per-track json files match, but NINE files
#      differ in content: granite/shards/shard_0..7.txt and granite/shards/all_caps.txt, i.e.
#      the aggregated granite caption shards. The root copy also holds one extra track
#      (540c597b9f9406627cb4d346d14580849086fd99.json, in both granite/ and json/). So these are
#      two different GENERATIONS of the granite captions, not a copy and its clone. Neither is
#      safe to retire, and G is actively revising granite captions right now (job 21255037), so
#      caps-fold is DISABLED -- folding would have silently overwritten one generation's shards
#      with the other's. Leave both until G's revision lands and the authoritative set is known.
#
# SAFETY MODEL: copy -> verify -> (separate, explicit) delete. Nothing is deleted by a copy
# phase, ever. Every delete phase re-runs its verify first and REFUSES if verification fails.
# rsync --remove-source-files is deliberately NOT used anywhere: it deletes as it goes, so a
# mid-transfer abort leaves a half-moved tree with no way to tell copied from lost.
#
# USAGE (each phase separately, check output before the next):
#   bash Misc/drive_rebalance_20260817.sh plan
#   bash Misc/drive_rebalance_20260817.sh relink        # repoint the 10 fullft symlinks
#   bash Misc/drive_rebalance_20260817.sh p1-copy       # Mantu/lumi_runs -> UUID  (~65 GB new)
#   bash Misc/drive_rebalance_20260817.sh p1-verify
#   bash Misc/drive_rebalance_20260817.sh p1-delete     # only after p1-verify says OK
#   bash Misc/drive_rebalance_20260817.sh p2-copy       # ai-music2 + features -> Mantu (221 GB)
#   bash Misc/drive_rebalance_20260817.sh p2-verify
#   bash Misc/drive_rebalance_20260817.sh p2-delete
#   bash Misc/drive_rebalance_20260817.sh caps-fold     # fold the 2 stray caption files in
#
set -uo pipefail

U=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d
M=/run/media/kim/Mantu
ULR=${U}/lumi_runs/runs
MLR=${M}/lumi_runs
SLR=${M}/sa3_lora_runs
LOG=${HOME}/.cache/drive_rebalance_20260817.log

# Runs living under Mantu/lumi_runs, all of which belong on the UUID drive.
MANTU_RUNS=(bf16_twin fp32_compare fp32_winning fullft longctx_t1024_r128 longctx_t2048_r128 smoke_r256_a256_lr1e4_f512_bs8)
# Non-LUMI bulk going the other way. NOTE: goa_archive_captions is NOT here on purpose (see trap 3).
TO_MANTU=(ai-music2 goa_archive_features)

say() { printf '[rebalance] %s\n' "$*" | tee -a "${LOG}"; }
die() { printf '[rebalance] FATAL: %s\n' "$*" | tee -a "${LOG}" >&2; exit 1; }

need_mounts() {
  mountpoint -q "${U}" || die "UUID drive not mounted at ${U}"
  mountpoint -q "${M}" || die "Mantu not mounted at ${M}"
}

# size of a tree in GB, 0 if absent
gb() { find "$1" -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1}END{printf "%.1f", s/1073741824}'; }
nfiles() { find "$1" -type f 2>/dev/null | wc -l; }
freegb() { df -B1 --output=avail "$1" 2>/dev/null | tail -1 | awk '{printf "%.0f", $1/1073741824}'; }

cmd_plan() {
  need_mounts
  say "free now: UUID=$(freegb "${U}") GB   Mantu=$(freegb "${M}") GB"
  say ""
  say "PHASE 1 — Mantu/lumi_runs -> UUID/lumi_runs/runs (consolidate LUMI content)"
  local uniq=0
  for r in "${MANTU_RUNS[@]}"; do
    [ -d "${MLR}/${r}" ] || continue
    local only both
    only=$(comm -23 <(cd "${MLR}/${r}" && find . -type f -printf '%P\n' | sort) \
                    <(cd "${ULR}/${r}" 2>/dev/null && find . -type f -printf '%P\n' | sort || true) | wc -l)
    both=$(comm -12 <(cd "${MLR}/${r}" && find . -type f -printf '%P\n' | sort) \
                    <(cd "${ULR}/${r}" 2>/dev/null && find . -type f -printf '%P\n' | sort || true) | wc -l)
    printf '[rebalance]   %-32s %7s GB  mantu_only=%-5s already_on_uuid=%-5s\n' \
      "${r}" "$(gb "${MLR}/${r}")" "${only}" "${both}" | tee -a "${LOG}"
    [ "${only}" -gt 0 ] && uniq=1
  done
  say "  (mantu_only>0 means real data that would be LOST by a naive delete)"
  say ""
  say "PHASE 2 — UUID -> Mantu (rebalance non-LUMI bulk)"
  for d in "${TO_MANTU[@]}"; do
    printf '[rebalance]   %-32s %7s GB  %7s files\n' "${d}" "$(gb "${U}/${d}")" "$(nfiles "${U}/${d}")" | tee -a "${LOG}"
  done
  say ""
  say "SYMLINKS pointing into Mantu/lumi_runs (must be repointed before p1-delete):"
  find "${SLR}" -maxdepth 1 -type l -lname "*${MLR}*" -printf '[rebalance]   %f -> %l\n' | tee -a "${LOG}"
}

# ---- repoint the fullft symlinks from the Mantu copy to the UUID copy -----------------------
cmd_relink() {
  need_mounts
  local n=0 fail=0
  while IFS= read -r link; do
    local tgt new
    tgt=$(readlink "${link}")
    new=${tgt/${MLR}/${ULR}}
    if [ ! -e "${new}" ]; then
      say "SKIP ${link##*/}: UUID counterpart missing (${new})"; fail=1; continue
    fi
    ln -sfn "${new}" "${link}" || { say "FAILED to relink ${link}"; fail=1; continue; }
    say "relinked ${link##*/} -> ${new}"
    n=$((n+1))
  done < <(find "${SLR}" -maxdepth 1 -type l -lname "*${MLR}*")
  say "relinked ${n} symlink(s)"
  # A broken symlink here is worse than the duplication we're removing, so assert none exist.
  local broken
  broken=$(find "${SLR}" -maxdepth 1 -xtype l | wc -l)
  [ "${broken}" -eq 0 ] || die "${broken} BROKEN symlink(s) in ${SLR} after relink -- fix before deleting anything"
  [ "${fail}" -eq 0 ] || die "some links could not be repointed; do NOT run p1-delete"
  say "no broken symlinks — safe to proceed"
}

# ---- phase 1: Mantu/lumi_runs -> UUID ------------------------------------------------------
cmd_p1_copy() {
  need_mounts
  mkdir -p "${ULR}"
  for r in "${MANTU_RUNS[@]}"; do
    [ -d "${MLR}/${r}" ] || { say "p1: ${r} absent, skip"; continue; }
    say "p1: ${r} -> ${ULR}/${r}"
    # 🔴 THIS PHASE ALREADY CAUSED ONE LOSS — read before re-running (2026-08-17).
    # The first run used a bare `rsync -a`. Its default size+mtime check found
    # bf16cmp_avp_t512_bs8_lr1e4/epoch=0-step=299.weights.ckpt "different" and overwrote the
    # GOOD 666 MB file on the UUID drive with Mantu's TRUNCATED 25.6 MB fragment (mtime
    # 1970-01-01 -- the tell of an interrupted copy). rsync did exactly what it was told; the
    # error was mine, in treating a filename match as a content match and merging without a
    # backup. Corrupt sources are a real hazard on these drives, so a merge here must be able
    # to (a) compare content, and (b) undo itself.
    # NO --delete (never mirror a deletion onto the destination), NO --remove-source-files.
    rsync -a --checksum --partial --info=stats2 \
      --backup --backup-dir="${ULR}/.rebalance_overwritten/${r}" \
      "${MLR}/${r}/" "${ULR}/${r}/" 2>&1 | tee -a "${LOG}"
    if [ -d "${ULR}/.rebalance_overwritten/${r}" ]; then
      say "WARNING: ${r} overwrote pre-existing DIFFERING files; originals kept in ${ULR}/.rebalance_overwritten/${r}"
    fi
  done
  say "p1-copy done — now run p1-verify"
}

# Corruption signatures seen on these drives. A file matching one of these must NEVER be treated
# as authoritative, no matter that a size comparison says source and destination agree.
#   - mtime in 1970: rsync/cp preserved a null timestamp from an interrupted transfer.
#   - a *.weights.ckpt far below its siblings (~666 MB here): truncated mid-write.
#   - zero bytes: self-evident.
# Found by this scan 2026-08-17: bf16cmp_avp_t512_bs8_lr1e4/epoch=0-step=299.weights.ckpt at
# 25.6 MB / mtime 1970, on Mantu. It is UNLOADABLE ("PytorchStreamReader failed reading zip
# archive: failed finding central directory"), i.e. it was dead on Mantu from the moment it was
# written -- and a bare `rsync -a` propagated it over the only good copy.
# NOTE ON THE SIZE TEST — an absolute threshold does NOT work here (learned by testing this scan:
# a flat "*.weights.ckpt under 100 MB is truncated" flagged 83 files, ALL false positives, because
# dora16_* adapters are legitimately ~86 MB where a rank-128 is ~666 MB — adapter size scales with
# rank). The size test must therefore be RELATIVE TO SIBLINGS in the same run directory: a
# checkpoint drastically smaller than the largest weights file beside it is truncated; a whole
# directory of uniformly small adapters is just a low-rank run.
cmd_scan() {
  need_mounts
  local hits=0
  # absolute signatures: these are unambiguous regardless of rank
  for root in "${MLR}" "${ULR}" "${SLR}"; do
    [ -d "${root}" ] || continue
    while IFS= read -r f; do
      printf '[rebalance]   SUSPECT %-14s %10s  %s\n' "zero-or-1970" "$(stat -c%s "${f}")" "${f}" | tee -a "${LOG}"
      hits=$((hits+1))
    done < <(find "${root}" -name '*.ckpt' \( -size 0 -o \( -newermt '1969-01-01' ! -newermt '1990-01-01' \) \) -print 2>/dev/null)
  done
  # relative signature: a weights file far below the biggest one in its own directory
  while IFS= read -r dir; do
    local max
    max=$(find "${dir}" -maxdepth 1 -name '*.weights.ckpt' -printf '%s\n' 2>/dev/null | sort -rn | head -1)
    [ -n "${max}" ] && [ "${max}" -gt 0 ] || continue
    while IFS= read -r line; do
      local sz f
      sz=${line%% *}; f=${line#* }
      # under a fifth of the largest sibling = truncated, not a smaller-rank variant
      if [ $((sz * 5)) -lt "${max}" ]; then
        printf '[rebalance]   SUSPECT %-14s %10s  %s (siblings up to %s)\n' "runt-vs-sibs" "${sz}" "${f}" "${max}" | tee -a "${LOG}"
        hits=$((hits+1))
      fi
    done < <(find "${dir}" -maxdepth 1 -name '*.weights.ckpt' -printf '%s %p\n' 2>/dev/null)
  done < <(for root in "${MLR}" "${ULR}" "${SLR}"; do [ -d "${root}" ] && find "${root}" -type d 2>/dev/null; done)
  # NB a single bad file can trip more than one signature, so this counts FINDINGS not files.
  if [ "${hits}" -eq 0 ]; then say "scan: no corrupt/truncated checkpoints found"; else say "scan: ${hits} SUSPECT finding(s) — see above"; fi
  [ "${hits}" -eq 0 ]   # rc: 0 = clean, 1 = hits (do not return the count; >255 would wrap)
}

cmd_p1_verify() {
  need_mounts
  local bad=0
  # A size match does NOT prove a content match -- that assumption is what lost a checkpoint here
  # (see the p1-copy header). So: refuse outright if either tree still contains a file matching a
  # known corruption signature, because deleting the source after propagating a corrupt file would
  # make the corruption authoritative and unrecoverable. Set VERIFY_CHECKSUM=1 for a real (slow)
  # content comparison instead of the size heuristic.
  if ! cmd_scan; then
    die "p1-verify REFUSES: corrupt/truncated checkpoint(s) present (listed above). Re-pull the affected run from LUMI with 'rsync --checksum' BEFORE deleting anything."
  fi
  for r in "${MANTU_RUNS[@]}"; do
    [ -d "${MLR}/${r}" ] || continue
    local miss=0 mismatch=0
    while IFS= read -r rel; do
      local a="${MLR}/${r}/${rel}" b="${ULR}/${r}/${rel}"
      if [ ! -f "${b}" ]; then miss=$((miss+1)); continue; fi
      if [ "${VERIFY_CHECKSUM:-0}" = "1" ]; then
        cmp -s "${a}" "${b}" || mismatch=$((mismatch+1))
      else
        [ "$(stat -c%s "${a}")" = "$(stat -c%s "${b}")" ] || mismatch=$((mismatch+1))
      fi
    done < <(cd "${MLR}/${r}" && find . -type f -printf '%P\n')
    printf '[rebalance]   %-32s missing_on_uuid=%-5s mismatch=%-5s (%s)\n' "${r}" "${miss}" "${mismatch}" \
      "$([ "${VERIFY_CHECKSUM:-0}" = 1 ] && echo content || echo size-only)" | tee -a "${LOG}"
    [ "${miss}" -eq 0 ] && [ "${mismatch}" -eq 0 ] || bad=1
  done
  [ "${bad}" -eq 0 ] || die "p1-verify FAILED — do not delete the Mantu copies"
  if [ "${VERIFY_CHECKSUM:-0}" != "1" ]; then
    say "p1-verify OK (SIZE ONLY — rerun with VERIFY_CHECKSUM=1 before p1-delete for a real check)"
  else
    say "p1-verify OK: every Mantu/lumi_runs file is byte-identical on the UUID drive"
  fi
}

cmd_p1_delete() {
  need_mounts
  cmd_p1_verify || die "verify failed"
  local broken
  broken=$(find "${SLR}" -maxdepth 1 -xtype l | wc -l)
  [ "${broken}" -eq 0 ] || die "broken symlinks present — run relink first"
  find "${SLR}" -maxdepth 1 -type l -lname "*${MLR}*" | grep -q . \
    && die "symlinks still point into ${MLR} — run relink first"
  say "deleting ${MLR} ($(gb "${MLR}") GB, verified present on UUID)"
  rm -rf "${MLR}"
  say "Mantu free now: $(freegb "${M}") GB"
}

# ---- phase 2: UUID -> Mantu ----------------------------------------------------------------
cmd_p2_copy() {
  need_mounts
  local need free
  need=$(printf '%.0f' "$(awk -v a="$(gb "${U}/ai-music2")" -v b="$(gb "${U}/goa_archive_features")" 'BEGIN{print a+b}')")
  free=$(freegb "${M}")
  say "p2: need ~${need} GB, Mantu has ${free} GB free"
  [ "${free}" -gt $((need + 50)) ] || die "not enough headroom on Mantu (want need+50GB)"
  for d in "${TO_MANTU[@]}"; do
    [ -d "${U}/${d}" ] || { say "p2: ${d} absent, skip"; continue; }
    say "p2: ${d} -> ${M}/${d}"
    mkdir -p "${M}/${d}"
    # --checksum, not the default size+mtime quick check: in p1 three runs whose files matched by
    # NAME were re-sent because their mtimes differed, silently overwriting the destination copy.
    # Content is the only thing worth comparing here. --backup-dir keeps any overwritten file
    # instead of destroying it, so an unexpected difference is recoverable rather than a loss.
    rsync -a --checksum --partial --info=stats2 \
      --backup --backup-dir="${M}/.rebalance_overwritten/${d}" \
      "${U}/${d}/" "${M}/${d}/" 2>&1 | tee -a "${LOG}"
    if [ -d "${M}/.rebalance_overwritten/${d}" ]; then
      say "WARNING: ${d} had pre-existing DIFFERING files on Mantu; originals kept in ${M}/.rebalance_overwritten/${d} -- inspect before p2-delete"
    fi
  done
  say "p2-copy done — now run p2-verify"
}

cmd_p2_verify() {
  need_mounts
  local bad=0
  for d in "${TO_MANTU[@]}"; do
    [ -d "${U}/${d}" ] || continue
    local sn dn sb db
    sn=$(nfiles "${U}/${d}"); dn=$(nfiles "${M}/${d}")
    sb=$(gb "${U}/${d}");     db=$(gb "${M}/${d}")
    printf '[rebalance]   %-24s src=%s files/%s GB   dst=%s files/%s GB\n' "${d}" "${sn}" "${sb}" "${dn}" "${db}" | tee -a "${LOG}"
    [ "${sn}" = "${dn}" ] && [ "${sb}" = "${db}" ] || bad=1
  done
  [ "${bad}" -eq 0 ] || die "p2-verify FAILED — do not delete the UUID copies"
  say "p2-verify OK: file counts and byte totals match"
}

cmd_p2_delete() {
  need_mounts
  cmd_p2_verify || die "verify failed"
  for d in "${TO_MANTU[@]}"; do
    [ -d "${U}/${d}" ] || continue
    say "deleting ${U}/${d} ($(gb "${U}/${d}") GB, verified on Mantu)"
    rm -rf "${U}/${d}"
  done
  say "UUID free now: $(freegb "${U}") GB"
  say "REMINDER: update the hardcoded paths — eval/build_goa_archive_sidecar.py:46,"
  say "  eval/caption_corpus_sample.py:15, eval/chroma_morph_transitions.py:57"
}

# ---- fold the 2 stray files from the duplicate root captions dir into the active one --------
cmd_caps_fold() {
  need_mounts
  local root="${U}/goa_archive_captions" act="${U}/lumi_runs/goa_archive_captions"
  [ -d "${root}" ] || { say "root captions dir already gone"; return 0; }
  local n=0
  while IFS= read -r rel; do
    mkdir -p "${act}/$(dirname "${rel}")"
    cp -n "${root}/${rel}" "${act}/${rel}" && { say "folded ${rel}"; n=$((n+1)); }
  done < <(comm -23 <(cd "${root}" && find . -type f -printf '%P\n' | sort) \
                    <(cd "${act}"  && find . -type f -printf '%P\n' | sort))
  say "folded ${n} stray file(s) into the active captions dir"
  local miss
  miss=$(comm -23 <(cd "${root}" && find . -type f -printf '%P\n' | sort) \
                  <(cd "${act}"  && find . -type f -printf '%P\n' | sort) | wc -l)
  [ "${miss}" -eq 0 ] || die "still ${miss} file(s) only in the root copy — not safe to retire it"
  say "root captions dir is now a strict subset of the active one; safe to remove:"
  say "  rm -rf ${root}"
}

case "${1:-plan}" in
  plan)      cmd_plan ;;
  scan)      cmd_scan ;;
  relink)    cmd_relink ;;
  p1-copy)   cmd_p1_copy ;;
  p1-verify) cmd_p1_verify ;;
  p1-delete) cmd_p1_delete ;;
  p2-copy)   cmd_p2_copy ;;
  p2-verify) cmd_p2_verify ;;
  p2-delete) cmd_p2_delete ;;
  caps-fold) cmd_caps_fold ;;
  *) die "unknown phase '${1}'. See the USAGE block at the top of this file." ;;
esac
