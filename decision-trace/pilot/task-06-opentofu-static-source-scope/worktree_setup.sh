#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="3fdc8090501234c55093078255969ecbc46f2fe2"
REPO_URL="https://github.com/opentofu/opentofu.git"

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <new_target_dir> <new_cache_dir>" >&2
  exit 1
fi

TARGET_DIR="$1"
CACHE_DIR="$2"
if [ -e "$TARGET_DIR" ]; then
  echo "target already exists; choose a new isolated directory: $TARGET_DIR" >&2
  exit 1
fi
if [ -e "$CACHE_DIR" ]; then
  echo "cache already exists; choose a new isolated directory: $CACHE_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR" "$CACHE_DIR/build" "$CACHE_DIR/modules"
git -C "$TARGET_DIR" init -q
git -C "$TARGET_DIR" remote add origin "$REPO_URL"
git -C "$TARGET_DIR" fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git -C "$TARGET_DIR" checkout -q FETCH_HEAD

GOCACHE="$CACHE_DIR/build" GOMODCACHE="$CACHE_DIR/modules" go -C "$TARGET_DIR" mod download
GOCACHE="$CACHE_DIR/build" GOMODCACHE="$CACHE_DIR/modules" \
  go -C "$TARGET_DIR" test ./internal/configs -run '^$' -count=1

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "Go caches ready under $CACHE_DIR."
