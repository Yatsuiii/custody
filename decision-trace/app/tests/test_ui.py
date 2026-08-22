"""UI-layer logic that doesn't need Streamlit itself: which decision the
"Current decision" card should track for a given answer, HTML-escaping
of untrusted content rendered alongside the status-pill HTML, and the
frozen-benchmark seeding guarantee."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import resolve_authority_with_proof  # noqa: E402
from collaborate import Claim, ClaimCategory  # noqa: E402
from graph import DecisionGraph, resolve_active  # noqa: E402
from loader import load_decisions  # noqa: E402
from models import Decision, DecisionStatus  # noqa: E402
from store import JSONFileDecisionStore  # noqa: E402
import ui  # noqa: E402
from ui import DEMO_EXCLUDED_DECISION_IDS, ensure_frozen_benchmark_seeded, grounded_decision_id  # noqa: E402

FALSIFIER_DATA = Path(__file__).resolve().parents[2] / "data" / "decisions.jsonl"


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


def _evil_decision() -> Decision:
    return Decision(
        id="xss-test-decision",
        subject='Support <b>generic Map&lt;K,V&gt;</b> <img src=x onerror=alert(1)>',
        current_status=DecisionStatus.ACCEPTED,
    )


def test_decision_card_html_escapes_untrusted_subject_text(tmp_path):
    """Real bug found in review: the pill-badge change made
    render_decision_card's st.markdown calls unsafe_allow_html=True, which
    also carries decision.subject — real, external text from arbitrary
    GitHub PR/KEP titles via live-ingest. Without escaping, a title
    containing HTML renders as live HTML instead of literal text."""
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    store.save(_evil_decision())

    captured = []
    with patch.object(ui.st, "markdown", lambda text, *a, **k: captured.append(text)), \
         patch.object(ui.st, "subheader", lambda *a, **k: None):
        ui.render_decision_card("xss-test-decision", store)

    combined = "\n".join(captured)
    assert "<img src=x onerror=alert(1)>" not in combined
    assert "&lt;img src=x onerror=alert(1)&gt;" in combined
    assert '<span class="dt-pill' in combined  # the pill itself must stay real HTML


def test_status_line_html_escapes_untrusted_active_subject(tmp_path):
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    store.save(_evil_decision())
    graph = DecisionGraph(store.list_all())
    decision = store.get("xss-test-decision")
    resolution = resolve_active(graph, "xss-test-decision")

    captured = []
    with patch.object(ui.st, "markdown", lambda text, *a, **k: captured.append(text)):
        ui.render_status_line(decision, resolution, False, store, graph)

    combined = "\n".join(captured)
    assert "<img src=x onerror=alert(1)>" not in combined
    assert "&lt;img src=x onerror=alert(1)&gt;" in combined


class _NoopExpander:
    """Minimal stand-in for `st.expander(...)`'s context-manager return
    value — the body only calls `st.markdown` inside it, which is
    separately captured, so this needs no behavior of its own."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_render_authority_proof_shows_governing_and_excluded(tmp_path):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"])
    b = Decision(id="B", subject="B", current_status=DecisionStatus.PROPOSED,
                 related_components=["scope"])
    proof = resolve_authority_with_proof([a, b], "scope")

    captured = []
    with patch.object(ui.st, "markdown", lambda text, *a, **k: captured.append(text)), \
         patch.object(ui.st, "caption", lambda *a, **k: None), \
         patch("ui.st.expander", return_value=_NoopExpander()):
        ui.render_authority_proof(proof)

    combined = "\n".join(captured)
    assert "CURRENTLY GOVERNING" in combined
    assert "`A`" in combined
    assert "✓ `A`" in combined
    assert "✗ `B`" in combined
    assert "PROPOSED_NOT_ACCEPTED" in combined


def test_render_authority_proof_none_is_a_no_op():
    captured = []
    with patch.object(ui.st, "markdown", lambda text, *a, **k: captured.append(text)):
        ui.render_authority_proof(None)
    assert captured == []


def test_render_authority_proof_escapes_untrusted_witness_text():
    evil = Decision(
        id="<script>evil</script>", subject="evil", current_status=DecisionStatus.PROPOSED,
        related_components=["scope"],
    )
    accepted = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                         related_components=["scope"])
    proof = resolve_authority_with_proof([accepted, evil], "scope")

    captured = []
    with patch.object(ui.st, "markdown", lambda text, *a, **k: captured.append(text)), \
         patch.object(ui.st, "caption", lambda *a, **k: None), \
         patch("ui.st.expander", return_value=_NoopExpander()):
        ui.render_authority_proof(proof)

    combined = "\n".join(captured)
    assert "<script>evil</script>" not in combined
    assert "&lt;script&gt;evil&lt;/script&gt;" in combined


def test_frozen_benchmark_seeds_even_when_store_already_has_other_data(tmp_path):
    """Real bug found in review: seeding used to be gated on `if not
    store.list_all()`. Firestore is shared/persistent, so a single early
    live-ingest write left the store permanently non-empty and the frozen,
    falsifier-graded benchmark never (re)loaded — 18 of 37 graded
    decisions were silently missing from production. Seeding must be an
    idempotent upsert that runs regardless of prior store state."""
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    # Simulate a store that already has unrelated live-ingested data,
    # exactly the scenario that broke the old empty-store-only guard.
    store.save(Decision(
        id="kubernetes/kubernetes-pr-999999",
        subject="Some live-ingested decision",
        current_status=DecisionStatus.IMPLEMENTED,
    ))

    ensure_frozen_benchmark_seeded(store)

    frozen_ids = {
        d.id for d in load_decisions(FALSIFIER_DATA)
        if d.id not in DEMO_EXCLUDED_DECISION_IDS
    }
    stored_ids = {d.id for d in store.list_all()}
    assert frozen_ids <= stored_ids
    assert "kubernetes/kubernetes-pr-999999" in stored_ids  # untouched, not clobbered


def test_frozen_benchmark_seeding_never_reintroduces_the_excluded_decision(tmp_path):
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    ensure_frozen_benchmark_seeded(store)
    stored_ids = {d.id for d in store.list_all()}
    assert DEMO_EXCLUDED_DECISION_IDS.isdisjoint(stored_ids)
