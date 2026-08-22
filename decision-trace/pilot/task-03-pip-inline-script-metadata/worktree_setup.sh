#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="b35182d8f7245f046eed2975275c57b54ce3ba56"
REPO_URL="https://github.com/pypa/pip.git"

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <target_dir>" >&2
  exit 1
fi

TARGET_DIR="$1"
rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
git -C "$TARGET_DIR" init -q
git -C "$TARGET_DIR" remote add origin "$REPO_URL"
git -C "$TARGET_DIR" fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git -C "$TARGET_DIR" checkout -q FETCH_HEAD

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "No install is required; tests use stdlib unittest and pip's vendored TOML parser."
