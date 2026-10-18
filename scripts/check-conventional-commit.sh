#!/usr/bin/env bash
# Decides whether a commit header or PR title is a Conventional Commit.
# Used by .githooks/commit-msg and by CI, so both always agree.
#
#   check-conventional-commit.sh <max-length> <header>
#   check-conventional-commit.sh <max-length> --file <commit-message-file>
set -euo pipefail

usage() {
  echo "usage: $0 <max-length> <header> | $0 <max-length> --file <path>" >&2
  exit 64
}

[[ $# -ge 2 ]] || usage
max="$1"
if [[ "$2" == "--file" ]]; then
  [[ $# -eq 3 ]] || usage
  # first line that is not a git comment
  header="$(grep -v '^#' "$3" | head -n 1 || true)"
else
  header="$2"
fi

types="feat|fix|refactor|perf|test|docs|build|ci|chore|style|revert"
pattern="^($types)(\([a-z0-9._/-]+\))?!?: [^ ].*$"

# Headers git writes itself.
if [[ "$header" =~ ^(Merge\ |fixup!\ |squash!\ |amend!\ ) ]]; then
  exit 0
fi

if [[ ! "$header" =~ $pattern ]]; then
  echo "not a Conventional Commit: '$header'" >&2
  echo "expected '<type>(<scope>): <subject>', type one of: ${types//|/, }" >&2
  exit 1
fi

if ((${#header} > max)); then
  echo "too long: ${#header} characters, at most $max: '$header'" >&2
  exit 1
fi
