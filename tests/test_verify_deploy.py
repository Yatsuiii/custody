"""The deploy judge is tested against the three regressions that really shipped.

Fetching is separated from judging precisely so this runs with no network,
keeping `make check` offline. Each case below is a failure that reached
production once and was not visible in the deploy output.
"""

from __future__ import annotations

import unittest

from scripts.verify_deploy import Response, judge

INCIDENT = b"<html>incident</html>"
ARCHITECTURE = b"<html>architecture</html>"
LOCAL = {"incident.html": INCIDENT, "architecture.html": ARCHITECTURE}


def healthy() -> dict[str, Response]:
    return {
        "/": Response(200, INCIDENT),
        "/incident.html": Response(200, INCIDENT),
        "/architecture.html": Response(200, ARCHITECTURE),
        "/.env.local": Response(404, b""),
    }


class AGoodDeployPassesEveryGate(unittest.TestCase):
    def test_every_route_serving_the_local_build_passes(self):
        gates = judge(healthy(), LOCAL)
        self.assertTrue(all(gates.values()), gates)
        self.assertEqual(len(gates), 4)


class TheRegressionsThatActuallyShipped(unittest.TestCase):
    def test_a_dead_root_fails_even_though_the_named_pages_are_fine(self):
        """web/ has no index.html, so a plain static deploy leaves / dead.

        Both README.md and EVALUATION_GUIDE.md send judges to the bare root,
        so this passing while the other two routes work is the whole point.
        """
        responses = healthy() | {"/": Response(404, b"")}
        gates = judge(responses, LOCAL)

        self.assertFalse(gates["/ serves the current incident.html"])
        self.assertTrue(gates["/incident.html serves the current incident.html"])
        self.assertTrue(gates["/architecture.html serves the current architecture.html"])

    def test_a_page_corrupted_in_transit_fails_despite_returning_200(self):
        """The inline <script> mangled by a deploy tool blanked every widget.

        It returned a clean 200 and looked fine in a screenshot, so status
        code alone can never catch it. Byte equality is what does.
        """
        mangled = ARCHITECTURE.replace(b"architecture", b"architectur\\e")
        responses = healthy() | {"/architecture.html": Response(200, mangled)}

        gates = judge(responses, LOCAL)
        self.assertFalse(
            gates["/architecture.html serves the current architecture.html"]
        )

    def test_a_login_wall_in_front_of_every_url_fails_every_page_gate(self):
        """Deployment protection once gated every URL behind an SSO redirect."""
        wall = Response(401, b"<html>authentication required</html>")
        responses = {route: wall for route in healthy()}
        responses["/.env.local"] = wall

        gates = judge(responses, LOCAL)
        self.assertFalse(any(gates.values()), gates)

    def test_a_served_dotenv_fails(self):
        """The CLI writes a VERCEL_OIDC_TOKEN into the uploaded directory."""
        responses = healthy() | {"/.env.local": Response(200, b"VERCEL_OIDC_TOKEN=x")}

        self.assertFalse(judge(responses, LOCAL)["/.env.local is not served"])

    def test_a_stale_deploy_fails_even_with_no_corruption(self):
        """The ordinary case: someone ran make gui and forgot to redeploy."""
        responses = healthy() | {"/architecture.html": Response(200, b"<html>old</html>")}

        self.assertFalse(
            judge(responses, LOCAL)["/architecture.html serves the current architecture.html"]
        )


class WithheldRoutesMayBeRefusedEitherWay(unittest.TestCase):
    def test_a_forbidden_dotenv_is_as_good_as_a_missing_one(self):
        """Either answer proves the token is not downloadable, which is the claim."""
        responses = healthy() | {"/.env.local": Response(403, b"")}

        self.assertTrue(judge(responses, LOCAL)["/.env.local is not served"])


if __name__ == "__main__":
    unittest.main()
