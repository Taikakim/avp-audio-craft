#!/usr/bin/env bash
# install.sh — clone the three forks declared in projects.toml and (optionally)
# run each one's own install.sh. Re-running picks up new commits via
# `git pull --ff-only`.
#
# Usage:
#   ./install.sh                       clone (or pull) all repos and set up venvs
#   ./install.sh --clone-only          stop after cloning; skip per-repo setup
#   ./install.sh --only NAME [NAME...] do only the named repo(s)
#   ./install.sh --skip NAME [NAME...] skip the named repo(s)
#   ./install.sh --no-pull             don't `git pull` if the repo already exists
#   ./install.sh --help                this text
#
# Per-repo install.sh scripts own all the actual setup logic — venv creation,
# pinned dependency installs, ROCm wheel selection, etc. This orchestrator is
# intentionally thin so the per-repo recipes stay authoritative.

set -euo pipefail

SAO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &>/dev/null && pwd )"
TOML="$SAO_DIR/projects.toml"

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
CLONE_ONLY=0
PULL=1
ONLY=()
SKIP=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    --clone-only)   CLONE_ONLY=1; shift ;;
    --no-pull)      PULL=0; shift ;;
    --only)         shift
                    while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do ONLY+=("$1"); shift; done
                    ;;
    --skip)         shift
                    while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do SKIP+=("$1"); shift; done
                    ;;
    *)              echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# ---------------------------------------------------------------------------
# Parse projects.toml (no python required — handles our simple [[repos]] arrays)
# ---------------------------------------------------------------------------
# Emits one line per repo: name<TAB>url<TAB>path<TAB>branch<TAB>setup_script<TAB>skip_setup
parse_toml() {
  awk '
    BEGIN { in_repo = 0 }
    /^\[\[repos\]\]/ {
      if (in_repo) emit()
      in_repo = 1
      name=""; url=""; path=""; branch="main"; setup="./install.sh"; skip="false"
      next
    }
    /^\[/ && !/^\[\[repos\]\]/ {
      if (in_repo) { emit(); in_repo = 0 }
      next
    }
    in_repo && /^[a-z_]+ *=/ {
      key = $1
      sub(/ *=.*/, "", key)
      val = $0
      sub(/^[a-z_]+ *= *"?/, "", val)
      sub(/"? *(#.*)?$/, "", val)
      if (key == "name")          name = val
      else if (key == "url")      url = val
      else if (key == "path")     path = val
      else if (key == "branch")   branch = val
      else if (key == "setup_script") setup = val
      else if (key == "skip_setup")   skip = val
    }
    END { if (in_repo) emit() }
    function emit() {
      printf "%s\t%s\t%s\t%s\t%s\t%s\n", name, url, path, branch, setup, skip
    }
  ' "$TOML"
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
in_array() {  # $1 = needle, $2..N = haystack
  local needle="$1"; shift
  local x
  for x in "$@"; do [[ "$x" == "$needle" ]] && return 0; done
  return 1
}

resolve_path() {
  local p="$1"
  case "$p" in
    /*) echo "$p" ;;
    *)  echo "$SAO_DIR/$p" ;;
  esac
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
need() {
  command -v "$1" &>/dev/null || { echo "ERROR: missing required tool: $1" >&2; exit 1; }
}
need git
need awk

# ---------------------------------------------------------------------------
# Process each repo
# ---------------------------------------------------------------------------
echo "==> Orchestrating from $SAO_DIR"
echo "    Config: $TOML"
echo

while IFS=$'\t' read -r name url path branch setup_script skip_setup; do
  [[ -z "$name" ]] && continue

  if [[ ${#ONLY[@]} -gt 0 ]] && ! in_array "$name" "${ONLY[@]}"; then
    echo "[skip] $name (not in --only list)"
    continue
  fi
  if [[ ${#SKIP[@]} -gt 0 ]] && in_array "$name" "${SKIP[@]}"; then
    echo "[skip] $name (--skip)"
    continue
  fi

  abspath="$(resolve_path "$path")"
  echo "==> $name"
  echo "    URL:    $url"
  echo "    Path:   $abspath"
  echo "    Branch: $branch"

  if [[ -d "$abspath/.git" ]]; then
    if [[ "$PULL" == "1" ]]; then
      echo "    [pull] existing repo — git fetch + pull --ff-only on $branch"
      git -C "$abspath" fetch --tags --prune origin
      # If we're not already on `branch`, check it out (create-tracking if needed).
      cur="$(git -C "$abspath" symbolic-ref --short HEAD 2>/dev/null || echo "")"
      if [[ "$cur" != "$branch" ]]; then
        if git -C "$abspath" show-ref --verify --quiet "refs/heads/$branch"; then
          git -C "$abspath" checkout "$branch"
        else
          git -C "$abspath" checkout -b "$branch" "origin/$branch"
        fi
      fi
      git -C "$abspath" pull --ff-only
    else
      echo "    [skip-pull] --no-pull: leaving working tree as-is"
    fi
  else
    echo "    [clone] $url → $abspath"
    mkdir -p "$(dirname "$abspath")"
    git clone --branch "$branch" "$url" "$abspath"
  fi

  if [[ "$CLONE_ONLY" == "1" ]]; then
    echo "    [clone-only] skipping setup"
    echo
    continue
  fi
  if [[ "$skip_setup" == "true" ]]; then
    echo "    [skip-setup] projects.toml has skip_setup=true"
    echo
    continue
  fi

  if [[ -f "$abspath/$setup_script" ]]; then
    echo "    [setup] $setup_script"
    ( cd "$abspath" && bash "$setup_script" )
  else
    echo "    [setup] $setup_script not found in $abspath — skipping (repo can set up manually)"
  fi
  echo

done < <(parse_toml)

echo "==> Done."
