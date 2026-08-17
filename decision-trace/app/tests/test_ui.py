"""UI-layer logic that doesn't need Streamlit itself: which decision the
"Current decision" card should track for a given answer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collaborate import Claim, ClaimCategory  # noqa: E402
from ui import grounded_decision_id  # noqa: E402


def test_all_missing_or_uncertain_claims_yield_no_grounded_decision():
    claims = [
        Claim(text="not enough info", category=ClaimCategory.MISSING_OR_UNCERTAIN, decision_id=None),
    ]
    assert grounded_decision_id(claims) is None


def test_missing_or_uncertain_claim_with_a_decision_id_is_still_ungrounded():
    """A claim can carry a decision_id even when the model itself flagged
    the answer as uncertain — that citation must not be treated as a
    resolution, or the card would contradict the answer text next to it."""
    claims = [
        Claim(text="not enough info", category=ClaimCategory.MISSING_OR_UNCERTAIN, decision_id="kep-1979"),
    ]
    assert grounded_decision_id(claims) is None


def test_current_active_decision_claim_grounds_the_card():
    claims = [
        Claim(text="X is why", category=ClaimCategory.CURRENT_ACTIVE_DECISION, decision_id="kep-42"),
    ]
    assert grounded_decision_id(claims) == "kep-42"


def test_first_grounded_claim_wins_when_mixed_with_uncertain_ones():
    claims = [
        Claim(text="unrelated", category=ClaimCategory.MISSING_OR_UNCERTAIN, decision_id=None),
        Claim(text="the fact", category=ClaimCategory.VERIFIED_HISTORICAL_FACT, decision_id="kep-7"),
    ]
    assert grounded_decision_id(claims) == "kep-7"
