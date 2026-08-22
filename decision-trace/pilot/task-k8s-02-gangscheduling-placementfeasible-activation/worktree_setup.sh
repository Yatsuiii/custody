#!/usr/bin/env bash
# Resettable worktree setup for task-k8s-02-gangscheduling-placementfeasible-activation.
#
# Creates an isolated, sparse, blob-filtered checkout of kubernetes/kubernetes
# at the pinned commit, containing only the packages needed to build and test
# pkg/scheduler/framework/plugins/gangscheduling (plus its real transitive Go
# dependencies within the monorepo). Does NOT do a full clone.
#
# Usage: ./worktree_setup.sh <target_dir>
# Re-running with the same target_dir wipes and recreates it (deterministic
# reset). Requires network access (git fetch + `go build`/`go test` module
# downloads on first run; subsequent runs reuse the shared Go module cache).

set -euo pipefail

PINNED_SHA="e81f39c0e03ce8ed8e2660c9147b391edd9e262b"
REPO_URL="https://github.com/kubernetes/kubernetes.git"

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
git config core.sparsecheckout true

git sparse-checkout init --cone
git sparse-checkout set \
  pkg/api pkg/apis pkg/features pkg/scheduler \
  staging/src/k8s.io \
  test/e2e/framework/testfiles test/e2e/testing-manifests test/utils/image

git fetch --filter=blob:none --depth 1 origin "$PINNED_SHA"
git checkout FETCH_HEAD

echo "Worktree ready at $TARGET_DIR (pinned $PINNED_SHA)."
echo "Verify with:"
echo "  cd $TARGET_DIR && GOWORK=off go test ./pkg/scheduler/framework/plugins/gangscheduling/..."
