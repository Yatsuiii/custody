#!/usr/bin/env python3
"""Verify V4 crash cleanup and abandoned-slot recovery without model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from action_compliance_v4_storage import V4StoragePolicy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    storage = V4StoragePolicy(args.storage_root.resolve(), worker_count=2)
    storage.initialize()
    storage.recover_abandoned()

    with storage.lifecycle(run_id="recovery-live-marker", slot=0):
        live_recovery = storage.recover_abandoned()
        live_marker_preserved = storage.slot_root(0).exists()

    stale_root = storage.slot_root(1)
    stale_root.mkdir(parents=True, exist_ok=True)
    (stale_root / "disposable.txt").write_text("stale\n", encoding="utf-8")
    (stale_root / ".v4_slot_marker.json").write_text(
        json.dumps({"experiment": "action-compliance-v4", "pid": 999999, "slot": 1, "run_id": "stale"}) + "\n",
        encoding="utf-8",
    )
    recovered = storage.recover_abandoned()
    stale_removed = not stale_root.exists()

    try:
        with storage.lifecycle(run_id="intentional-crash-cleanup", slot=0):
            raise RuntimeError("intentional model-free cleanup probe")
    except RuntimeError as error:
        crash_exception_observed = str(error) == "intentional model-free cleanup probe"
    crash_slot_removed = not storage.slot_root(0).exists()
    result = {
        "model_calls": 0,
        "live_marker_not_recovered": not live_recovery and live_marker_preserved,
        "stale_marker_recovered": bool(recovered) and stale_removed,
        "crash_exception_observed": crash_exception_observed,
        "crash_slot_removed": crash_slot_removed,
        "pass": not live_recovery and live_marker_preserved and bool(recovered) and stale_removed and crash_exception_observed and crash_slot_removed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"V4_STORAGE_RECOVERY_VERIFY_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
