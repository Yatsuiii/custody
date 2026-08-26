"""Freeze live issue-comment delivery GUIDs before any treatment runs."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


ROOT = Path(__file__).parent
SCOPE = json.loads((ROOT / "RUNNER_SCOPE.json").read_text(encoding="utf-8"))
MANIFEST_PATH = ROOT / "CASE_MANIFEST.json"
ORDER_PATH = ROOT / "DELIVERY_ORDER.json"
API = SCOPE["api"]["host"]
API_VERSION = SCOPE["api"]["version"]
RECEIVER = SCOPE["receiver"]["url"]
INGRESS_KEY = Path("/home/Yatsuiii/.config/custody-execution-secrets/ingress.pem")
RECEIVER_TOKEN = Path("/home/Yatsuiii/.config/custody-execution-secrets/receiver-read.token")


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def jwt() -> str:
    app_id = SCOPE["apps"]["ingress"]["app_id"]
    key = serialization.load_pem_private_key(INGRESS_KEY.read_bytes(), password=None)
    now = int(time.time())
    signing = (
        f'{b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())}.'
        f'{b64(json.dumps({"iat": now - 30, "exp": now + 540, "iss": app_id}, separators=(",", ":")).encode())}'
    ).encode()
    return signing.decode() + "." + b64(key.sign(signing, padding.PKCS1v15(), hashes.SHA256()))


def api(method: str, path: str, token: str, **kwargs: Any) -> Any:
    response = requests.request(
        method,
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "custody-external-validity-delivery-freeze/1",
        },
        timeout=20,
        **kwargs,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"github_api_{method.lower()}_{response.status_code}")
    return response.json() if response.content else None


def receiver(guid: str, token: str) -> dict[str, Any]:
    response = requests.get(
        f"{RECEIVER}/api/delivery",
        params={"guid": guid, "content": "1"},
        headers={"x-receiver-read-token": token},
        timeout=20,
    )
    if response.status_code != 200:
        raise RuntimeError(f"receiver_delivery_{response.status_code}")
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("receiver_envelope_not_object")
    return value


def hook_id(detail: dict[str, Any]) -> int | None:
    request = detail.get("request")
    headers = request.get("headers") if isinstance(request, dict) else None
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if str(key).lower() == "x-github-hook-id":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return None
            return value if value > 0 else None
    return None


def payload_from_envelope(envelope: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    if envelope.get("schema") != "github-issue-comment-raw-delivery-v1":
        raise RuntimeError("receiver_schema_mismatch")
    import binascii

    try:
        raw = base64.b64decode(envelope["body_b64"], validate=True)
    except (KeyError, ValueError, binascii.Error) as error:
        raise RuntimeError("receiver_body_invalid") from error
    digest = hashlib.sha256(raw).hexdigest()
    if digest != envelope.get("body_sha256"):
        raise RuntimeError("receiver_body_digest_mismatch")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("payload_not_object")
    return raw, payload


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    token = jwt()
    read_token = RECEIVER_TOKEN.read_text(encoding="utf-8").strip()
    expected_comments = {
        int(comment["id"]): comment
        for case in manifest["cases"]
        for comment in case["comments"]
    }
    assigned: dict[int, dict[str, Any]] = {}
    deadline = time.monotonic() + 120
    while len(assigned) < len(expected_comments) and time.monotonic() < deadline:
        rows = api("GET", "/app/hook/deliveries?per_page=100", token)
        if not isinstance(rows, list):
            raise RuntimeError("github_deliveries_not_list")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), int):
                continue
            detail = api("GET", f"/app/hook/deliveries/{row['id']}", token)
            if not isinstance(detail, dict):
                continue
            if detail.get("event") != "issue_comment" or detail.get("action") != "created":
                continue
            if detail.get("repository_id") != SCOPE["repository"]["id"]:
                continue
            if detail.get("installation_id") != SCOPE["apps"]["ingress"]["installation_id"]:
                continue
            if hook_id(detail) != SCOPE["apps"]["ingress"]["hook_id"]:
                continue
            request = detail.get("request")
            payload = request.get("payload") if isinstance(request, dict) else None
            comment = payload.get("comment") if isinstance(payload, dict) else None
            comment_id = comment.get("id") if isinstance(comment, dict) else None
            if not isinstance(comment_id, int) or comment_id not in expected_comments:
                continue
            guid = detail.get("guid")
            if not isinstance(guid, str):
                continue
            is_redelivery = bool(detail.get("redelivery"))
            previous = assigned.get(comment_id)
            if previous is not None and (not previous["redelivery"] or is_redelivery):
                continue
            envelope = receiver(guid, read_token)
            _, received_payload = payload_from_envelope(envelope)
            received_comment = received_payload.get("comment")
            if not isinstance(received_comment, dict) or received_comment.get("id") != comment_id:
                raise RuntimeError("receiver_comment_mismatch")
            received_body = received_comment.get("body")
            if not isinstance(received_body, str):
                raise RuntimeError("receiver_comment_body_missing")
            comment_digest = hashlib.sha256(received_body.encode("utf-8")).hexdigest()
            if comment_digest != expected_comments[comment_id]["body_sha256"]:
                raise RuntimeError(
                    "comment_body_digest_mismatch_"
                    f"comment_{comment_id}_expected_{expected_comments[comment_id]['body_sha256']}"
                    f"_received_{comment_digest}"
                )
            if envelope.get("delivery_guid") != guid:
                raise RuntimeError("receiver_guid_mismatch")
            assigned[comment_id] = {
                "delivery_guid": guid,
                "delivery_id": detail["id"],
                "hook_id": hook_id(detail),
                "redelivery": is_redelivery,
                "status_code": detail.get("status_code"),
                "delivery_body_sha256": envelope.get("body_sha256"),
            }
        if len(assigned) < len(expected_comments):
            time.sleep(2)
    if len(assigned) != len(expected_comments):
        raise RuntimeError("delivery_freeze_incomplete")

    l2 = next(case for case in manifest["cases"] if case["case_id"] == "L2_RELAY")
    l2_activation = next(comment for comment in l2["comments"] if comment["role"] == "activation")
    l2_meta = assigned[int(l2_activation["id"])]

    def redelivery_ids() -> list[int]:
        values: list[int] = []
        rows = api("GET", "/app/hook/deliveries?per_page=100", token)
        for row in rows if isinstance(rows, list) else []:
            if row.get("guid") == l2_meta["delivery_guid"] and row.get("redelivery") is True:
                value = row.get("id")
                if isinstance(value, int):
                    values.append(value)
        return values

    existing_redeliveries = redelivery_ids()
    if len(existing_redeliveries) > 1:
        raise RuntimeError("redelivery_multiple")
    if existing_redeliveries:
        redelivery_id = existing_redeliveries[0]
    else:
        api(
            "POST",
            f"/app/hook/deliveries/{l2_meta['delivery_id']}/attempts",
            token,
        )
        redelivery_id = None
    redelivery_deadline = time.monotonic() + 90
    while redelivery_id is None and time.monotonic() < redelivery_deadline:
        values = redelivery_ids()
        if len(values) > 1:
            raise RuntimeError("redelivery_multiple")
        if values:
            redelivery_id = values[0]
            break
        time.sleep(2)
    if not isinstance(redelivery_id, int):
        raise RuntimeError("redelivery_not_observed")

    for case in manifest["cases"]:
        for comment in case["comments"]:
            comment.update(assigned[int(comment["id"])])
    manifest["status"] = "FROZEN_PRETREATMENT"
    manifest["delivery_freeze_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["compromise_interval"] = SCOPE["generation_control"]
    manifest["redelivery"].update(
        {
            "activation_comment_id": l2_activation["id"],
            "delivery_guid": l2_meta["delivery_guid"],
            "delivery_id": redelivery_id,
            "initial_delivery_id": l2_meta["delivery_id"],
        }
    )
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    sequence = []
    for case in manifest["cases"]:
        sequence.extend(comment["delivery_guid"] for comment in case["comments"])
        if case["case_id"] == "L2_RELAY":
            sequence.append(l2_meta["delivery_guid"])
    ORDER_PATH.write_text(
        json.dumps(
            {
                "format": "custody.external-validity.github-delivery-order",
                "schema_version": 1,
                "treatment": "B_RULE",
                "delivery_guids": sequence,
                "redelivery_guid": l2_meta["delivery_guid"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"frozen_comments={len(expected_comments)} redelivery_observed=yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
