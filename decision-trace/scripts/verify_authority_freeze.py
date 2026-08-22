"""Fail if any frozen authority-resolver file's hash has drifted.

Guards ACTION_COMPLIANCE_PROTOCOL.md Section 3/6: the deterministic
AuthorityProof engine and its pinning tests must not change once the
action-compliance experiment freeze is committed. Run from anywhere;
paths are resolved relative to this file's repository root.
"""

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FROZEN_HASHES = {
    "app/authority.py": "687be19116305a773f061383a5ce17b8ac8a84b3ab50dff9d8d0d485e49f49ee",
    "app/collaborate.py": "65b77c8f79ac652d1d656669b5de3c0688fbce1f475c46dd95e7aebcb600a22b",
    "app/ui.py": "9f95c3f831f187439a356cb42930b254bbe9da05fc7763314b8373e4fdac04a2",
    "app/tests/test_authority_explanation.py": "e5abd66bae31320ed5308520b2066912e237ab1544e17ad0827b61ce6ab197a6",
    "app/tests/test_authority_proof.py": "df7088ebd27072e09730a2a6c5ec3b87504759721f04de0ec5de8132ff88d38a",
    "app/tests/test_authority.py": "adabde5deba2a2920bb0d47fb756abdfac0f4e6172011de94ba514e7130dae32",
    "app/tests/test_authority_reconsideration.py": "0b6541038b874ccf9e5e30a7bf52a339ce989bd865511681b42296369ffd3614",
    "app/tests/test_authority_regression_prospective.py": "c6227df3eedc40a20ec48418070047ae3be2511436528288998bac21ddc75f02",
    "app/tests/test_collaborate_authority.py": "6ef8bd6f98b2ae4fd1fd4f40c96b2fdfd23eff3e004e2bf982e8e57081c521de",
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    mismatches = []
    missing = []
    for relative_path, expected_hash in FROZEN_HASHES.items():
        full_path = REPO_ROOT / relative_path
        if not full_path.exists():
            missing.append(relative_path)
            continue
        actual_hash = sha256_of(full_path)
        if actual_hash != expected_hash:
            mismatches.append((relative_path, expected_hash, actual_hash))

    if missing:
        print("AUTHORITY FREEZE VIOLATION: missing frozen file(s):")
        for relative_path in missing:
            print(f"  - {relative_path}")

    if mismatches:
        print("AUTHORITY FREEZE VIOLATION: hash mismatch:")
        for relative_path, expected_hash, actual_hash in mismatches:
            print(f"  - {relative_path}")
            print(f"      expected: {expected_hash}")
            print(f"      actual:   {actual_hash}")

    if missing or mismatches:
        return 1

    print(f"OK: all {len(FROZEN_HASHES)} frozen authority files match ACTION_COMPLIANCE_PROTOCOL.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
