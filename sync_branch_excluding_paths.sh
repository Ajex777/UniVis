#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<USAGE
Usage:
  ./${SCRIPT_NAME} [--source BRANCH] [--target BRANCH] [--exclude PATHSPEC]... [--commit-message MESSAGE] [--no-commit]

Examples:
  ./${SCRIPT_NAME}
  ./${SCRIPT_NAME} --source dev_with_docs --target master
  ./${SCRIPT_NAME} --exclude 'docs/**' --exclude '${SCRIPT_NAME}'

Purpose:
  Apply changes from a source branch to a target branch while excluding selected paths.
  This creates a normal commit on the target branch instead of a Git merge commit.

Defaults:
  --source current branch
  --target master
  --exclude docs/**
  --exclude ${SCRIPT_NAME}
USAGE
}

ensure_clean_worktree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "[sync-excluding] Worktree is not clean. Please commit or stash changes first." >&2
    exit 1
  fi
}

current_branch() {
  git branch --show-current
}

append_exclude_pathspecs() {
  local -n output_ref=$1
  shift

  for excluded_path in "$@"; do
    output_ref+=(":(exclude)${excluded_path}")
  done
}

main() {
  local source_branch
  source_branch="$(current_branch)"
  local target_branch="master"
  local commit_message=""
  local should_commit="1"
  local excludes=("docs/**" "${SCRIPT_NAME}")

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --source)
        source_branch="$2"
        shift 2
        ;;
      --target)
        target_branch="$2"
        shift 2
        ;;
      --exclude)
        excludes+=("$2")
        shift 2
        ;;
      --commit-message)
        commit_message="$2"
        shift 2
        ;;
      --no-commit)
        should_commit="0"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "[sync-excluding] Unknown argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done

  if [[ -z "${source_branch}" ]]; then
    echo "[sync-excluding] Could not determine the current branch. Pass --source explicitly." >&2
    exit 1
  fi

  if [[ "${source_branch}" == "${target_branch}" ]]; then
    echo "[sync-excluding] Source and target are both '${source_branch}'." >&2
    exit 1
  fi

  ensure_clean_worktree

  git rev-parse --verify "${source_branch}" >/dev/null
  git rev-parse --verify "${target_branch}" >/dev/null

  local patch_file
  patch_file="$(mktemp "/tmp/univis-${source_branch}-to-${target_branch}.XXXXXX.patch")"
  trap 'rm -f "${patch_file}"' EXIT

  local pathspecs=(".")
  append_exclude_pathspecs pathspecs "${excludes[@]}"

  echo "[sync-excluding] Source: ${source_branch}"
  echo "[sync-excluding] Target: ${target_branch}"
  echo "[sync-excluding] Excludes: ${excludes[*]}"

  git diff --binary "${target_branch}..${source_branch}" -- "${pathspecs[@]}" > "${patch_file}"

  if [[ ! -s "${patch_file}" ]]; then
    echo "[sync-excluding] No non-excluded changes to apply."
    exit 0
  fi

  git checkout "${target_branch}"
  git apply --index --3way "${patch_file}"

  echo "[sync-excluding] Staged files:"
  git diff --cached --name-status

  if [[ "${should_commit}" == "1" ]]; then
    if [[ -z "${commit_message}" ]]; then
      commit_message="Sync non-excluded changes from ${source_branch}"
    fi
    git commit -m "${commit_message}"
  else
    echo "[sync-excluding] --no-commit was set. Changes are staged on ${target_branch}."
  fi
}

main "$@"
