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


APP_ID = 47_525_929
API_VERSION = "2026-03-10"
EXPECTED_EVENT = "issue_comment"
EXPECTED_URL = "https://custody-external-validity-receiver.vercel.app/api/webhook"
API_ROOT = "https://api.github.com"


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--key-path",
        type=Path,
        default=Path("/tmp/custody-execution-secrets/ingress.pem"),
    )
    parser.add_argument(
        "--secret-path",
        type=Path,
        default=Path("/tmp/custody-execution-secrets/webhook.secret"),
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
    hook = _request("GET", "/app/hook", token).json()
    if hook.get("active") is not True:
        raise RuntimeError("github_hook_not_active")
    if hook.get("events") != [EXPECTED_EVENT]:
        raise RuntimeError("github_hook_event_mismatch")
    config = hook.get("config")
    if not isinstance(config, dict) or config.get("url") != args.receiver_url:
        raise RuntimeError("github_hook_url_mismatch")
    hook_id = hook.get("id")
    if not isinstance(hook_id, int) or hook_id <= 0:
        raise RuntimeError("github_hook_id_missing")
    # Only this immutable identifier is allowed on stdout.
    print(f"hook_id={hook_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
