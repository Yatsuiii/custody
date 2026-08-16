"""Shared `gh` CLI wrapper with a hard timeout.

A `gh pr view` call hung indefinitely mid-mining with no error and 0% CPU —
`subprocess.run()` has no default timeout, so a stalled `gh`/network call
blocks forever instead of failing. Same class of bug as the earlier
untimed Vertex client hang (see vertex.py). Every `gh` call in this
benchmark goes through here now instead of four separate copies of the
same subprocess wrapper.
"""

from __future__ import annotations

import json
import subprocess
import time

TIMEOUT_SECONDS = 30


def gh_json(*args: str, max_attempts: int = 3) -> object:
    delay = 3.0
    for attempt in range(max_attempts):
        try:
            out = subprocess.run(
                ["gh", *args], capture_output=True, text=True,
                check=True, timeout=TIMEOUT_SECONDS,
            )
            return json.loads(out.stdout)
        except subprocess.TimeoutExpired:
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
