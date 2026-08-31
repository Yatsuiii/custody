"""Independently judge G5: the daily Cloud Scheduler heartbeat's
multi-day elapsed-time claim.

Unlike `review_gates.py` / `auditor_gates.py`, there is no `proof-out/*.json`
producer artifact to reread here -- the claim is that real calendar time has
elapsed on Google's own Scheduler clock, so the only honest check is to ask
the two durable Cloud resources directly, right now, under the project's own
credentials: `gcloud scheduler jobs describe` for the job's own
`lastAttemptTime`/`schedule`/`state`, and a live `/auditor` call against the
deployed control plane for the elapsed-day count itself. Both are
independently re-derived by this script, not trusted from any prior run.

    make scheduler-gates
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPECTED_SCHEDULE = "0 6 * * *"


def _service_url(*, project: str, region: str, service: str) -> str:
    command = [
        "gcloud",
        "run",
        "services",
        "describe",
        service,
        f"--project={project}",
        f"--region={region}",
        "--format=json",
    ]
    described = json.loads(
        subprocess.run(command, check=True, capture_output=True, text=True).stdout
    )
    return described["status"]["url"]


def _scheduler_job(*, project: str, region: str, job: str) -> dict:
    command = [
        "gcloud",
        "scheduler",
        "jobs",
        "describe",
        job,
        f"--project={project}",
        f"--location={region}",
        "--format=json",
    ]
    return json.loads(
        subprocess.run(command, check=True, capture_output=True, text=True).stdout
    )


def _json_post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def judge(*, project: str, region: str, service: str, job: str) -> dict[str, bool]:
    scheduler = _scheduler_job(project=project, region=region, job=job)
    url = _service_url(project=project, region=region, service=service)
    live = _json_post(f"{url}/auditor", {})

    last_attempt = scheduler.get("lastAttemptTime")
    last_attempt_age_hours = None
    if last_attempt:
        parsed = datetime.fromisoformat(last_attempt.replace("Z", "+00:00"))
        last_attempt_age_hours = (datetime.now(UTC) - parsed).total_seconds() / 3600

    elapsed = live.get("elapsed_days_since_seed")

    return {
        "scheduler_job_enabled": scheduler.get("state") == "ENABLED",
        "scheduler_job_runs_daily_at_the_declared_schedule": (
            scheduler.get("schedule") == EXPECTED_SCHEDULE
        ),
        "scheduler_last_natural_fire_within_the_last_25_hours": (
            last_attempt_age_hours is not None and last_attempt_age_hours <= 25
        ),
        "live_auditor_call_succeeded_just_now": bool(live),
        "live_auditor_reports_this_run_was_not_the_first": (
            live.get("first_run") is False
        ),
        "live_auditor_reports_todays_utc_date": (
            live.get("day") == datetime.now(UTC).date().isoformat()
        ),
        "elapsed_days_since_seed_is_a_real_positive_multi_day_span": (
            isinstance(elapsed, int) and elapsed >= 1
        ),
    }


def main() -> int:
    project = os.environ.get("CUSTODY_PROJECT")
    region = os.environ.get("CUSTODY_REGION", "us-central1")
    service = os.environ.get("CUSTODY_CONTROL_PLANE_SERVICE", "custody-control-plane")
    job = os.environ.get("CUSTODY_G5_SCHEDULER_JOB", "custody-g5-auditor")
    if not project:
        print("[BLOCKED] CUSTODY_PROJECT is required")
        return 2

    try:
        gates = judge(project=project, region=region, service=service, job=job)
    except (
        subprocess.CalledProcessError,
        urllib.error.URLError,
        KeyError,
        ValueError,
    ) as error:
        print(
            "[FAIL] could not independently reach the live Scheduler job "
            f"or control plane: {error}"
        )
        return 1

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
