"""Configure the one GitHub App webhook without printing credential material.

The script is intentionally narrow: it accepts an App private key and webhook
secret from local files, updates only the ingress App's single hook, verifies
the immutable hook ID and least-privilege event configuration, and prints only
that hook ID.  It never serializes a JWT, key, secret, response body, or token.
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


APP_ID = 4_725_929
API_VERSION = "2026-03-10"
EXPECTED_EVENT = "issue_comment"
EXPECTED_URL = "https://custody-external-validity-receiver.vercel.app/api/webhook"
API_ROOT = "https://api.github.com"
DEFAULT_SECRET_DIR = Path("/home/Yatsuiii/.config/custody-execution-secrets")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _jwt(private_key: bytes, now: int) -> str:
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {"iat": now - 60, "exp": now + 540, "iss": APP_ID}
    signing_input = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(claims, separators=(',', ':')).encode())}".encode()
    key = serialization.load_pem_private_key(private_key, password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return signing_input.decode() + "." + _b64(signature)


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "custody-external-validity-hook-config/1",
    }


def _request(method: str, path: str, token: str, **kwargs: Any) -> requests.Response:
    response = requests.request(
        method,
        API_ROOT + path,
        headers=_headers(token),
        timeout=20,
        **kwargs,
    )
    if not 200 <= response.status_code < 300:
        # Do not include GitHub's body: it can echo configuration details.
        raise RuntimeError(f"github_api_{method.lower()}_{response.status_code}")
    return response


def _json(response: requests.Response) -> dict[str, Any]:
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("github_response_not_object")
    return value


def _hook_id(token: str) -> int:
    """Read the hook ID from delivery metadata after the config exists.

    GitHub exposes App webhook configuration at ``/app/hook/config`` and
    includes the numeric hook ID in each delivery's request headers. Updating
    the config emits a ping, so polling delivery metadata gives us an
    independently queryable immutable hook ID without storing payloads.
    """
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        deliveries = _request(
            "GET", "/app/hook/deliveries?per_page=20", token
        ).json()
        if not isinstance(deliveries, list):
            raise RuntimeError("github_deliveries_response_not_list")
        for delivery in deliveries:
            if not isinstance(delivery, dict) or not isinstance(delivery.get("id"), int):
                continue
            detail = _json(
                _request("GET", f"/app/hook/deliveries/{delivery['id']}", token)
            )
            request = detail.get("request")
            headers = request.get("headers") if isinstance(request, dict) else None
            if not isinstance(headers, dict):
                continue
            raw_id = next(
                (
                    value
                    for key, value in headers.items()
                    if str(key).lower() == "x-github-hook-id"
                ),
                None,
            )
            try:
                hook_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if hook_id > 0:
                return hook_id
        time.sleep(1)
    raise RuntimeError("github_hook_id_unavailable")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--key-path",
        type=Path,
        default=DEFAULT_SECRET_DIR / "ingress.pem",
    )
    parser.add_argument(
        "--secret-path",
        type=Path,
        default=DEFAULT_SECRET_DIR / "webhook.secret",
    )
    parser.add_argument("--receiver-url", default=EXPECTED_URL)
    return parser


def main() -> int:
    args = _parser().parse_args()
    private_key = args.key_path.read_bytes()
    secret = args.secret_path.read_text(encoding="utf-8").strip()
    if not secret or len(secret) < 32:
        raise RuntimeError("webhook_secret_missing_or_too_short")
    token = _jwt(private_key, int(time.time()))
    _request(
        "PATCH",
        "/app/hook/config",
        token,
        json={
            "url": args.receiver_url,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0",
        },
    )
    config = _json(_request("GET", "/app/hook/config", token))
    if config.get("url") != args.receiver_url:
        raise RuntimeError("github_hook_url_mismatch")
    if config.get("content_type") != "json":
        raise RuntimeError("github_hook_content_type_mismatch")
    if str(config.get("insecure_ssl")) != "0":
        raise RuntimeError("github_hook_ssl_mismatch")
    app = _json(_request("GET", "/app", token))
    if app.get("id") != APP_ID or app.get("slug") != "custody-ev-ingress-yatsuiii":
        raise RuntimeError("github_app_identity_mismatch")
    if app.get("events") != [EXPECTED_EVENT]:
        raise RuntimeError("github_hook_event_mismatch")
    hook_id = _hook_id(token)
    # Only this immutable identifier is allowed on stdout.
    print(f"hook_id={hook_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
