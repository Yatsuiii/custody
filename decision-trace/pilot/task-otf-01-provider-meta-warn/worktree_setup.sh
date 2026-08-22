#!/usr/bin/env bash
# Resettable worktree setup for task-otf-01-provider-meta-warn.
#
# opentofu/opentofu is a single Go module (unlike kubernetes/kubernetes's
# 30+ staging modules), so a shallow, blob-filtered fetch of just the pinned
# commit is sufficient -- no sparse checkout needed. Does NOT do a full clone
# (no history, no other branches/tags).
#
# Usage: ./worktree_setup.sh <target_dir>
# Re-running with the same target_dir wipes and recreates it (deterministic
# reset). Requires network access (git fetch + `go build`/`go test` module
# downloads on first run; subsequent runs reuse the shared Go module cache).

set -euo pipefail

PINNED_SHA="f831fa1aa4b90cdbdb1e0b5a8d5815f9e74646a5"
REPO_URL="https://github.com/opentofu/opentofu.git"

if [ $# -ne 1 ]; then
  echo "usage: $0 <target_dir>" >&2
  exit 1
fi
TARGET_DIR="$1"

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

git init -q
git remote add origin "$REPO_URL"
git fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git checkout -q FETCH_HEAD

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "Verify with:"
echo "  cd $TARGET_DIR && go test ./internal/tofu/ -run TestContext2Apply_ProviderMeta"
