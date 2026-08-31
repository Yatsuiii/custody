"""Judge a deployed page by what it actually serves, not by what a deploy said.

Three live regressions have been caused by a deploy that reported success:
an inline ``<script>`` corrupted in transit, which blanked every widget
while still returning 200; a project setting that put a login wall in front
of every URL; and a 404 at ``/``, the one URL ``README.md`` and
``EVALUATION_GUIDE.md`` send judges to. None was visible in the deploy output.

So this compares the bytes the origin serves against the bytes ``make gui``
just built, per route. Byte equality is what catches the corruption case:
a page mangled in transit differs from disk, whatever status code it
returns.

Deliberately not part of ``make check``, which is network-free and finishes
in a fraction of a second.

    make verify-deploy
    CUSTODY_DEPLOY_URL=https://some-preview.vercel.app make verify-deploy
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB = REPO_ROOT / "web"

DEFAULT_BASE = "https://custody-incident-cave2.vercel.app"

#: Each route that must serve a page, and the local build it must equal.
#: ``/`` is a rewrite: ``web/`` holds no ``index.html``, so without the
#: rewrite in ``web/vercel.json`` a plain static deploy leaves the root dead.
SERVED_ROUTES: Mapping[str, str] = {
    "/": "incident.html",
    "/incident.html": "incident.html",
    "/architecture.html": "architecture.html",
}

#: The Vercel CLI writes ``web/.env.local`` (a short-lived
#: ``VERCEL_OIDC_TOKEN``) into the very directory it uploads.
#: ``web/.vercelignore`` excludes it; this confirms that rather than trusting it.
WITHHELD_ROUTES: tuple[str, ...] = (".env.local",)


class Unreachable(Exception):
    """The origin could not be reached at all, which is not a page defect."""


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes


def fetch(url: str, *, timeout: float = 30.0) -> Response:
    """Return the response, treating an HTTP error status as an answer.

    A 404 is a fact this script needs, not a failure to get one, so only a
    transport-level problem raises.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "custody-verify-deploy"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return Response(response.status, response.read())
    except urllib.error.HTTPError as error:
        return Response(error.code, error.read() or b"")
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise Unreachable(f"{url}: {error}") from error


def judge(
    responses: Mapping[str, Response], local: Mapping[str, bytes]
) -> dict[str, bool]:
    """Compare what each route served with the build on disk."""
    gates: dict[str, bool] = {}
    for route, filename in SERVED_ROUTES.items():
        response = responses[route]
        gates[f"{route} serves the current {filename}"] = (
            response.status == 200 and response.body == local[filename]
        )
    for route in WITHHELD_ROUTES:
        gates[f"/{route} is not served"] = responses[f"/{route}"].status in (403, 404)
    return gates


def _reason(route: str, response: Response, local: Mapping[str, bytes]) -> str:
    filename = SERVED_ROUTES.get(route)
    if filename is None:
        return f"HTTP {response.status}; it must not be served at all"
    if response.status != 200:
        return f"HTTP {response.status}, expected 200"
    expected = local[filename]
    return (
        f"HTTP 200 but the body is not web/{filename}: served "
        f"{len(response.body)} bytes, built {len(expected)}. Redeploy, or "
        "run make gui first if the local build is the stale one"
    )


def main() -> int:
    base = os.environ.get("CUSTODY_DEPLOY_URL", DEFAULT_BASE).rstrip("/")
    local = {name: (WEB / name).read_bytes() for name in set(SERVED_ROUTES.values())}
    routes = list(SERVED_ROUTES) + [f"/{route}" for route in WITHHELD_ROUTES]

    print(f"\nDeployed pages, judged against the local build, at {base}\n")
    try:
        responses = {route: fetch(f"{base}{route}") for route in routes}
    except Unreachable as error:
        print(f"  [BLOCKED] origin unreachable: {error}")
        print("            this is a network or hostname problem, not a page defect\n")
        return 2

    for route in routes:
        print(f"  {route:<22} -> {responses[route].status}")
    print()

    gates = judge(responses, local)
    for name, passed in gates.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        if not passed:
            route = name.split(" ", 1)[0]
            print(f"         {_reason(route, responses[route], local)}")

    failed = [name for name, passed in gates.items() if not passed]
    print(
        f"\n  {len(gates) - len(failed)} passed, {len(failed)} failed\n"
        "  This proves the origin serves the bytes make gui built. It does not\n"
        "  execute the page, so open both and read the browser console too.\n"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
