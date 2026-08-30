"""E2D-EXT4: manifest-based (huge) parent lists, on top of E2D's mechanism.
Imports Graph/RevocationController/etc. from the frozen E2D run.py rather
than duplicating them.

Run: python3 research/experiments/E2D_EXT4_MANIFEST_PARENTS/run.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).parent
E2D_DIR = Path(__file__).parent.parent / "E2D_DESIGN_FALSIFIER"


def _load_e2d():
    spec = importlib.util.spec_from_file_location("e2d_run", E2D_DIR / "run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["e2d_run"] = mod
    spec.loader.exec_module(mod)
    return mod


e2d = _load_e2d()


def manifest_digest(parent_ids: list[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(parent_ids)).encode()).hexdigest()


def admit_via_manifest(
    graph,
    output_id: str,
    admitted_at: str,
    chunks: list[list[str]],
    declared_count: int,
    declared_digest: str,
    transform_class,
    transform_revision: str,
):
    """The manifest-aware admission path. Verifies count, digest, and that
    every referenced id actually resolves before treating this as an
    ordinary derivation -- any failure produces INCOMPLETE, never a
    partial expansion and never a fresh trusted root.
    """
    expanded = [pid for chunk in chunks for pid in chunk]

    missing = [pid for pid in expanded if pid not in graph.records]
    count_ok = len(expanded) == declared_count
    digest_ok = manifest_digest(expanded) == declared_digest

    if missing or not count_ok or not digest_ok:
        env = e2d.AdmissionEnvelope(
            output_id=output_id,
            admitted_at=admitted_at,
            direct_parent_ids=(),  # declared parents are NOT trusted on failure
            transform_class=e2d.TransformClass.INCOMPLETE,
            transform_revision=transform_revision,
            context_complete=False,
            role=None,
            caps={e2d.SCOPE: e2d.Tier.INFORM},
            support=(output_id, e2d.UNKNOWN_CONTEXT),
        )
        graph.records[output_id] = env
        return env

    # Verified: proceed exactly like an ordinary inline derivation.
    return graph.admit_derived(
        output_id, admitted_at, tuple(expanded), transform_class, transform_revision
    )


def build_fixture():
    return e2d.build_fixture()


def main() -> dict:
    g = build_fixture()

    good_chunks = [["E-BENIGN-1", "E-VENDOR-2"], ["E-MAL-1"]]
    good_expanded = [pid for chunk in good_chunks for pid in chunk]
    good_digest = manifest_digest(good_expanded)

    ok_env = admit_via_manifest(
        g, "E-MANIFEST-OK", "2026-08-16T00:00:00Z", good_chunks, 3, good_digest,
        e2d.TransformClass.REGISTERED, "merge_v1",
    )

    mismatch_env = admit_via_manifest(
        g, "E-MANIFEST-DIGEST-MISMATCH", "2026-08-16T00:01:00Z", good_chunks, 3,
        "0" * 64,  # deliberately wrong digest
        e2d.TransformClass.REGISTERED, "merge_v1",
    )

    missing_chunks = [["E-BENIGN-1"], ["E-DOES-NOT-EXIST"]]
    missing_env = admit_via_manifest(
        g, "E-MANIFEST-MISSING-CHUNK", "2026-08-16T00:02:00Z", missing_chunks, 2,
        manifest_digest(["E-BENIGN-1", "E-DOES-NOT-EXIST"]),
        e2d.TransformClass.REGISTERED, "merge_v1",
    )

    # Reference: what an inline admission over the same three parents
    # would produce, to confirm the manifest path isn't a weaker mechanism.
    g_ref = build_fixture()
    inline_ref = g_ref.admit_derived(
        "E-INLINE-REF", "2026-08-16T00:00:00Z",
        ("E-BENIGN-1", "E-VENDOR-2", "E-MAL-1"),
        e2d.TransformClass.REGISTERED, "merge_v1",
    )

    checks = {
        "manifest_ok_cap_matches_inline": ok_env.caps[e2d.SCOPE] == inline_ref.caps[e2d.SCOPE],
        "manifest_ok_support_matches_inline": (
            tuple(sorted(ok_env.support)) == tuple(sorted(inline_ref.support))
        ),
        "manifest_ok_is_none_capped": ok_env.caps[e2d.SCOPE] == e2d.Tier.NONE,
        "digest_mismatch_is_incomplete": mismatch_env.transform_class == e2d.TransformClass.INCOMPLETE,
        "digest_mismatch_capped_inform": mismatch_env.caps[e2d.SCOPE] == e2d.Tier.INFORM,
        "digest_mismatch_no_partial_parents": mismatch_env.direct_parent_ids == (),
        "digest_mismatch_has_unknown_context": e2d.UNKNOWN_CONTEXT in mismatch_env.support,
        "missing_chunk_is_incomplete": missing_env.transform_class == e2d.TransformClass.INCOMPLETE,
        "missing_chunk_no_partial_parents": missing_env.direct_parent_ids == (),
        "missing_chunk_has_unknown_context": e2d.UNKNOWN_CONTEXT in missing_env.support,
    }

    verdict = "PASS" if all(checks.values()) else "FAIL"
    failed = [k for k, v in checks.items() if not v]

    result = {
        "checks": checks,
        "manifest_ok": {
            "caps": {k: int(v) for k, v in ok_env.caps.items()},
            "support": list(ok_env.support),
        },
        "digest_mismatch": {
            "transform_class": mismatch_env.transform_class.name,
            "caps": {k: int(v) for k, v in mismatch_env.caps.items()},
            "support": list(mismatch_env.support),
        },
        "missing_chunk": {
            "transform_class": missing_env.transform_class.name,
            "caps": {k: int(v) for k, v in missing_env.caps.items()},
            "support": list(missing_env.support),
        },
        "verdict": verdict,
        "verdict_reason": "all checks passed" if verdict == "PASS" else f"failed: {failed}",
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2, default=str))
    print(f"Verdict: {result['verdict']}")
    print(f"Reason: {result['verdict_reason']}")
    print(json.dumps(result["checks"], indent=2))
