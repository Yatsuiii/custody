#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="19fbc45b24ca0d577c9b256bb404b0dbaf4903da"
REPO_URL="https://github.com/pypa/packaging.git"

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <new_target_dir>" >&2
  exit 1
fi

TARGET_DIR="$1"
if [ -e "$TARGET_DIR" ]; then
  echo "target already exists; choose a new isolated directory: $TARGET_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
git -C "$TARGET_DIR" init -q
git -C "$TARGET_DIR" remote add origin "$REPO_URL"
git -C "$TARGET_DIR" fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git -C "$TARGET_DIR" checkout -q FETCH_HEAD

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "No install is required; replay uses stdlib unittest with PYTHONPATH=."
