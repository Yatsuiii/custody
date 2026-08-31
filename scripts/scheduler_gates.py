"""Independently judge G5: the daily Cloud Scheduler heartbeat's
multi-day elapsed-time claim.

The producer asks two durable Cloud resources directly, under the project's
own credentials: `gcloud scheduler jobs describe` for the job's own
`lastAttemptTime`/`schedule`/`state`, and a live `/auditor` call against the
deployed control plane for the elapsed-day count itself. It writes only the
bounded fields needed to re-judge that claim to `proof-out/live-scheduler.json`.
The aggregate offline gate and architecture page consume that artifact; they
never turn the producer's exit code into a pass.

    make scheduler-gates
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPECTED_SCHEDULE = "0 6 * * *"
EXPECTED_JOB = "custody-g5-auditor"
EXPECTED_SERVICE = "custody-control-plane"
OUT = REPO_ROOT / "proof-out" / "live-scheduler.json"

CLAIM_BOUNDARY = (
    "Proves the named Cloud Scheduler job was enabled on its declared daily "
    "schedule, fired naturally within 25 hours, and that a fresh call to the "
    "deployed Auditor reported a positive real multi-day span from its "
    "durable seed. A direct read confirms that seed remains unrevoked; the "
    "destructive transition is intentionally reserved for the filmed demo."
)


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


def _json_get(url: str) -> dict | None:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def collect_live(*, project: str, region: str, service: str, job: str) -> dict:
    scheduler = _scheduler_job(project=project, region=region, job=job)
    url = _service_url(project=project, region=region, service=service)
    live = _json_post(f"{url}/auditor", {})
    seed = _json_get(f"{url}/custody/g5-elapsed-time-seed")

    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "region": region,
        "service": service,
        "job": job,
        "claim_boundary": CLAIM_BOUNDARY,
        "scheduler": {
            "state": scheduler.get("state"),
            "schedule": scheduler.get("schedule"),
            "last_attempt_time": scheduler.get("lastAttemptTime"),
        },
        "auditor": {
            "day": live.get("day"),
            "elapsed_days_since_seed": live.get("elapsed_days_since_seed"),
            "first_run": live.get("first_run"),
        },
        "seed": seed,
    }


def judge_offline(
    evidence: dict, *, now: datetime | None = None
) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    capture_age = current - captured

    scheduler = evidence["scheduler"]
    last_attempt = scheduler.get("last_attempt_time")
    last_attempt_age = None
    if last_attempt:
        parsed = datetime.fromisoformat(last_attempt.replace("Z", "+00:00"))
        last_attempt_age = captured - parsed

    auditor = evidence["auditor"]
    elapsed = auditor.get("elapsed_days_since_seed")
    seed = evidence.get("seed")

    return {
        "fresh_live_evidence": (
            captured.tzinfo is not None
            and timedelta(0) <= capture_age <= timedelta(hours=24)
        ),
        "scheduler_identity_matches_the_declared_job": (
            evidence.get("job") == EXPECTED_JOB
            and evidence.get("service") == EXPECTED_SERVICE
        ),
        "scheduler_job_enabled": scheduler.get("state") == "ENABLED",
        "scheduler_job_runs_daily_at_the_declared_schedule": (
            scheduler.get("schedule") == EXPECTED_SCHEDULE
        ),
        "scheduler_last_natural_fire_within_25_hours_of_capture": (
            last_attempt_age is not None
            and timedelta(0) <= last_attempt_age <= timedelta(hours=25)
        ),
        "live_auditor_reports_the_capture_day": (
            auditor.get("day") == captured.astimezone(UTC).date().isoformat()
        ),
        "live_auditor_reports_this_was_not_the_first_run": (
            auditor.get("first_run") is False
        ),
        "elapsed_days_since_seed_is_a_real_positive_multi_day_span": (
            isinstance(elapsed, int) and not isinstance(elapsed, bool) and elapsed >= 1
        ),
        "durable_seed_is_directly_readable_and_unrevoked": (
            seed is not None
            and seed.get("id") == "g5-elapsed-time-seed"
            and seed.get("revocation_id") is None
        ),
        "claim_boundary_reserves_seed_revocation_for_the_demo": (
            "remains unrevoked" in evidence.get("claim_boundary", "")
            and "reserved for the filmed demo" in evidence.get("claim_boundary", "")
        ),
    }


def judge(*, project: str, region: str, service: str, job: str) -> dict[str, bool]:
    """Collect live evidence and judge it without trusting the live caller."""
    return judge_offline(
        collect_live(project=project, region=region, service=service, job=job)
    )


def main() -> int:
    project = os.environ.get("CUSTODY_PROJECT")
    region = os.environ.get("CUSTODY_REGION", "us-central1")
    service = os.environ.get("CUSTODY_CONTROL_PLANE_SERVICE", "custody-control-plane")
    job = os.environ.get("CUSTODY_G5_SCHEDULER_JOB", "custody-g5-auditor")
    if not project:
        print("[BLOCKED] CUSTODY_PROJECT is required")
        return 2

    try:
        evidence = collect_live(
            project=project,
            region=region,
            service=service,
            job=job,
        )
        gates = judge_offline(evidence)
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

    if gates and all(gates.values()):
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(f"live Scheduler evidence written to {OUT}")

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
