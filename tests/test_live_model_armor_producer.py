"""Fault-injection tests for the live Model Armor evidence producer."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from scripts.live_model_armor import (
    EXPECTED_FILTER_CONFIG,
    EXPECTED_LABELS,
    EXPECTED_TEMPLATE_METADATA,
    EXPECTED_TEMPLATE_NAME,
    LOG_POLL_ATTEMPTS,
    _require_blocked,
    _require_clean,
    _require_owned_template,
    _sanitize_log,
)


def _template(**overrides) -> dict[str, object]:
    template = {
        "name": EXPECTED_TEMPLATE_NAME,
        "filterConfig": EXPECTED_FILTER_CONFIG,
        "labels": EXPECTED_LABELS,
        "templateMetadata": EXPECTED_TEMPLATE_METADATA,
    }
    template.update(overrides)
    return template


def _blocked_result() -> dict[str, object]:
    return {
        "filterMatchState": "MATCH_FOUND",
        "invocationResult": "SUCCESS",
        "filterResults": {
            "pi_and_jailbreak": {
                "piAndJailbreakFilterResult": {
                    "executionState": "EXECUTION_SUCCESS",
                    "matchState": "MATCH_FOUND",
                }
            }
        },
    }


def _clean_result() -> dict[str, object]:
    return {
        "filterMatchState": "NO_MATCH_FOUND",
        "invocationResult": "SUCCESS",
        "filterResults": {
            "pi_and_jailbreak": {
                "piAndJailbreakFilterResult": {
                    "executionState": "EXECUTION_SUCCESS",
                    "matchState": "NO_MATCH_FOUND",
                }
            }
        },
    }


class LiveModelArmorProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sleep = patch(
            "scripts.live_model_armor.time.sleep", return_value=None
        )
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def test_owned_template_is_accepted(self) -> None:
        _require_owned_template(_template())

    def test_drifted_template_is_rejected(self) -> None:
        mutations = (
            {"name": EXPECTED_TEMPLATE_NAME + "-other"},
            {"filterConfig": {}},
            {"labels": {"custody-proof": "other"}},
            {"templateMetadata": {"logSanitizeOperations": False}},
        )
        for override in mutations:
            with self.subTest(override=override):
                with self.assertRaises(RuntimeError):
                    _require_owned_template(_template(**override))

    def test_blocked_result_is_accepted(self) -> None:
        _require_blocked(_blocked_result())

    def test_unblocked_result_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            _require_blocked(_clean_result())

    def test_clean_result_is_accepted(self) -> None:
        _require_clean(_clean_result())

    def test_matched_result_is_rejected_as_not_clean(self) -> None:
        with self.assertRaises(RuntimeError):
            _require_clean(_blocked_result())

    def test_log_polling_recovers_from_transient_reads_and_is_bounded(self) -> None:
        class AlwaysTransientCloud:
            def __init__(self) -> None:
                self.calls = 0

            def json(self, *arguments: str):
                del arguments
                self.calls += 1
                raise subprocess.CalledProcessError(1, ["gcloud"], "transient")

        cloud = AlwaysTransientCloud()

        with self.assertRaises(RuntimeError):
            _sanitize_log(cloud, prompt_text="irrelevant")  # type: ignore[arg-type]

        self.assertEqual(cloud.calls, LOG_POLL_ATTEMPTS)

    def test_log_polling_rejects_ambiguous_multi_entry_reads(self) -> None:
        class DuplicateLogCloud:
            def json(self, *arguments: str):
                del arguments
                return [{"insertId": "a"}, {"insertId": "b"}]

        with self.assertRaises(RuntimeError):
            _sanitize_log(DuplicateLogCloud(), prompt_text="irrelevant")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
