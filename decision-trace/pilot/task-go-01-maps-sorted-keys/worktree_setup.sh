#!/usr/bin/env bash
# Resettable worktree setup for task-go-01-maps-sorted-keys.
#
# Creates an isolated, sparse, blob-filtered checkout of golang/go at the
# pinned commit, containing only src/maps (the package under test). Does
# NOT clone the full repository and does NOT rebuild the Go toolchain
# (no make.bash). Package `maps` is tested by remapping GOROOT's copy of
# the package onto these checked-out files via `go test -overlay=...`,
# using whatever Go toolchain is already installed on the host (must be
# Go 1.23+, since the package uses range-over-func iterators). This works
# because `maps`'s only non-stdlib-builtin dependency is `iter`, `unsafe`,
# and (for the test files) `slices`/`cmp`/`math`/`strconv`/`testing`, all
# of which are already present, unmodified, in any installed Go 1.23+
# GOROOT — only the package under test itself needs to be swapped in.
#
# Usage: ./worktree_setup.sh <new_target_dir> <new_go_cache_dir>
# Existing paths are refused so setup cannot destroy another replay.
# Requires network access on first run (git fetch of the pinned
# commit); no Go module downloads are needed since `maps` has no external
# dependencies.

set -euo pipefail

PINNED_SHA="56ebf80e57db9f61981fc0636fc6419dc6f68eda"  # tag go1.25.1
REPO_URL="https://github.com/golang/go.git"

if [ $# -ne 2 ]; then
  echo "usage: $0 <new_target_dir> <new_go_cache_dir>" >&2
  exit 1
fi
TARGET_DIR="$1"
GO_CACHE="$2"

for path in "$TARGET_DIR" "$GO_CACHE"; do
  if [ -e "$path" ]; then
    echo "path already exists; choose new isolated paths: $path" >&2
    exit 1
  fi
done

mkdir -p "$TARGET_DIR" "$GO_CACHE"
cd "$TARGET_DIR"

git init -q
git remote add origin "$REPO_URL"
git config core.sparsecheckout true

git sparse-checkout init --cone
git sparse-checkout set src/maps

git fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git checkout -q FETCH_HEAD

GOROOT="$(go env GOROOT)"
if [ ! -d "$GOROOT/src/maps" ]; then
  echo "error: host Go toolchain's GOROOT ($GOROOT) has no src/maps; need Go 1.21+" >&2
  exit 1
fi

# Build the overlay JSON that remaps GOROOT's maps package files onto the
# pinned checkout, so `go test -overlay=overlay.json maps` (using the host
# toolchain) tests exactly the pinned+patched source, isolated from the
# real GOROOT tree, with no toolchain rebuild.
python3 - "$TARGET_DIR" "$GOROOT" <<'PYEOF'
import json, os, sys
target_dir, goroot = sys.argv[1], sys.argv[2]
maps_dir = os.path.join(target_dir, "src", "maps")
mapping = {}
for f in os.listdir(maps_dir):
    if f.endswith(".go"):
        mapping[os.path.join(goroot, "src", "maps", f)] = os.path.join(maps_dir, f)
with open(os.path.join(target_dir, "overlay.json"), "w") as fh:
    json.dump({"Replace": mapping}, fh, indent=2)
PYEOF

GOWORK=off GOCACHE="$GO_CACHE" go test -overlay="$TARGET_DIR/overlay.json" maps

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "Go build cache ready at $GO_CACHE."
echo "Verify with:"
echo "  cd $TARGET_DIR && GOWORK=off GOCACHE=$GO_CACHE go test -overlay=$TARGET_DIR/overlay.json maps"
