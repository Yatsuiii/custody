#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="fd11d8efde4895a2159a29dcd586a7db99917057"
REPO_URL="https://github.com/tokio-rs/axum.git"

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <new_target_dir> <new_cargo_home> <new_target_cache>" >&2
  exit 1
fi

TARGET_DIR="$1"
CARGO_CACHE="$2"
BUILD_CACHE="$3"
for path in "$TARGET_DIR" "$CARGO_CACHE" "$BUILD_CACHE"; do
  if [ -e "$path" ]; then
    echo "path already exists; choose new isolated paths: $path" >&2
    exit 1
  fi
done

mkdir -p "$TARGET_DIR" "$CARGO_CACHE" "$BUILD_CACHE"
git -C "$TARGET_DIR" init -q
git -C "$TARGET_DIR" remote add origin "$REPO_URL"
git -C "$TARGET_DIR" fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git -C "$TARGET_DIR" checkout -q FETCH_HEAD

CARGO_HOME="$CARGO_CACHE" CARGO_TARGET_DIR="$BUILD_CACHE" \
  cargo test --manifest-path "$TARGET_DIR/Cargo.toml" -p axum-extra \
    --features typed-header typed_header --no-run

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "Cargo caches ready at $CARGO_CACHE and $BUILD_CACHE."
