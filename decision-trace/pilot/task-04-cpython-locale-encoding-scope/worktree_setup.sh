#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="261a452a1300eeeae1428ffd6e6623329c085e2c"
REPO_URL="https://github.com/python/cpython.git"

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
git -C "$TARGET_DIR" sparse-checkout set --no-cone Lib/_pyio.py Lib/test/test_io.py
git -C "$TARGET_DIR" fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git -C "$TARGET_DIR" checkout -q FETCH_HEAD

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "Use a Python 3.12 interpreter for the recorded replay."
