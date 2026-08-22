#!/usr/bin/env bash
# Resettable worktree setup for task-02-django-index-together-superseded.
#
# Creates an isolated, blob-filtered, shallow checkout of django/django at
# the pinned commit (the 4.2 release tag) and installs it editable into a
# dedicated venv (Django 4.2 requires Python <= 3.12; this box's default
# python3 is 3.14, so a 3.12 interpreter is used explicitly if available).
#
# Usage: ./worktree_setup.sh <target_dir> [python_executable]
# Re-running with the same target_dir wipes and recreates it (deterministic
# reset). Requires network access (git fetch + pip install on first run).

set -euo pipefail

PINNED_SHA="879e5d587b84e6fc961829611999431778eb9f6a"
REPO_URL="https://github.com/django/django.git"

if [ $# -lt 1 ]; then
  echo "usage: $0 <target_dir> [python_executable]" >&2
  exit 1
fi
TARGET_DIR="$1"
PYTHON_BIN="${2:-python3}"

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

git init -q
git remote add origin "$REPO_URL"
git fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git checkout -q FETCH_HEAD

# Django's own test runner needs a real install (editable is fine, no
# compiled extensions).
"$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -e .

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "Verify with:"
echo "  cd $TARGET_DIR && source .venv/bin/activate && cd tests && python runtests.py model_indexes -v1"
