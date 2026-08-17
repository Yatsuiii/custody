"""Minimal Streamlit UI — BUILD_SCOPE.md §13, Stage 6.

Exactly five surfaces: conversation, current-decision card, timeline,
evidence links, candidate creation. No new business logic lives here — the
UI calls Stage 3-5's functions directly (`retrieval.search` via
`collaborate.answer`, `graph.lineage`, `memory.propose_reconsideration`)
and renders their output. The store/index are process-level
(`st.cache_resource`); real persistence is the underlying file
(`ui_store.jsonl`), the same mechanism Stage 5's tests already proved —
restarting this process is what proves a fresh session, not anything
special the UI does.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

import vertex  # noqa: E402
from collaborate import ClaimCategory, answer  # noqa: E402
from graph import DecisionGraph, resolve_active  # noqa: E402
from loader import load_decisions  # noqa: E402
from memory import propose_reconsideration  # noqa: E402
from models import DecisionStatus, RelationshipType  # noqa: E402
from retrieval import DecisionIndex, default_cache_path  # noqa: E402
from store import DecisionStore, FirestoreDecisionStore, JSONFileDecisionStore  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
FALSIFIER_DATA = APP_DIR.parent / "data" / "decisions.jsonl"
UI_STORE_PATH = APP_DIR / "data" / "ui_store.jsonl"
FIRESTORE_COLLECTION = "decisiontrace-decisions"

STATUS_COLOR = {
    DecisionStatus.PROPOSED: "orange",
    DecisionStatus.ACCEPTED: "green",
    DecisionStatus.IMPLEMENTED: "green",
    DecisionStatus.REVERTED: "red",
    DecisionStatus.SUPERSEDED: "red",
    DecisionStatus.REAFFIRMED: "green",
}

CATEGORY_LABEL = {
    ClaimCategory.VERIFIED_HISTORICAL_FACT: "📜 verified historical fact",
    ClaimCategory.CURRENT_ACTIVE_DECISION: "✅ current active decision",
    ClaimCategory.INFERRED_ADVICE: "💭 inferred advice",
    ClaimCategory.MISSING_OR_UNCERTAIN: "❓ missing/uncertain",
}


@st.cache_resource
def load_store_and_index() -> tuple[DecisionStore, DecisionIndex]:
    store: DecisionStore
    if os.environ.get("DECISIONTRACE_STORE") == "firestore":
        store = FirestoreDecisionStore(FIRESTORE_COLLECTION, project=vertex.PROJECT)
    else:
        store = JSONFileDecisionStore(UI_STORE_PATH)
    if not store.list_all():
        store.save_many(load_decisions(FALSIFIER_DATA))
    index = DecisionIndex(store, cache_path=default_cache_path())
    return store, index


def render_status_badge(status: DecisionStatus) -> str:
    color = STATUS_COLOR.get(status, "gray")
    return f":{color}[**{status.value}**]"


def _reconsidered_target_id(decision) -> str | None:
    for target_id, rel in decision.related_decisions:
        if rel == RelationshipType.RECONSIDERS:
            return target_id
    return None


def render_status_line(
    decision, resolution, is_current: bool, store: DecisionStore, graph: DecisionGraph,
) -> None:
    badge = render_status_badge(decision.current_status)
    if is_current:
        st.markdown(f"{badge} — this is the currently active decision")
        return
    if decision.current_status == DecisionStatus.PROPOSED:
        # A candidate's own lineage is trivially just itself (RECONSIDERS
        # isn't a lifecycle edge), so re-resolve from what it reconsiders
        # instead of the candidate's own meaningless self-resolution.
        target_id = _reconsidered_target_id(decision)
        target_resolution = resolve_active(graph, target_id) if target_id else None
        active = target_resolution.active_id if target_resolution else None
        active_subject = store.get(active).subject if active else "none"
        st.markdown(
            f"{badge} — a proposed candidate, not yet accepted. "
            f"Active decision for what it reconsiders: *{active_subject}* (`{active}`)"
        )
    else:
        active = resolution.active_id
        active_subject = store.get(active).subject if active else "none"
        st.markdown(f"{badge} — **not current**. Active: *{active_subject}* (`{active}`)")


def render_decision_card(decision_id: str, store: DecisionStore) -> None:
    decision = store.get(decision_id)
    if decision is None:
        st.warning(f"Unknown decision id: {decision_id}")
        return

    graph = DecisionGraph(store.list_all())
    resolution = resolve_active(graph, decision_id)
    # Same rule as RetrievalCandidate.is_current (retrieval.py): a PROPOSED
    # decision trivially resolves "active" in its own one-node lineage
    # (RECONSIDERS isn't a lifecycle edge), but a proposal that hasn't been
    # accepted must never present as settled current guidance.
    is_current = (
        resolution.active_id == decision_id
        and decision.current_status != DecisionStatus.PROPOSED
    )

    st.subheader(decision.subject)
    render_status_line(decision, resolution, is_current, store, graph)

    if decision.chosen_approach:
        st.markdown(f"**Chosen approach:** {decision.chosen_approach}")
    if decision.rejected_alternatives:
        st.markdown(f"**Rejected alternatives:** {'; '.join(decision.rejected_alternatives)}")
    if decision.rationale:
        st.markdown(f"**Rationale:** {decision.rationale}")

    if decision.evidence:
        st.markdown("**Evidence:**")
        for e in decision.evidence:
            if e.url:
                st.markdown(f"- [{e.type}]({e.url}): {e.quote}")
            else:
                st.markdown(f"- {e.type} (conversation): {e.quote}")

    st.markdown("**Timeline:**")
    for node_id in resolution.history:
        node = store.get(node_id)
        marker = "→" if node_id != decision_id else "▶"
        current_mark = " (current)" if node_id == resolution.active_id else ""
        st.markdown(f"{marker} `{node_id}` — {render_status_badge(node.current_status)}{current_mark}: {node.subject}")


def render_candidate_form(decision_id: str, store: DecisionStore, index: DecisionIndex) -> None:
    with st.form(key=f"reconsider-{decision_id}"):
        st.markdown("**Record a reconsideration of this decision:**")
        changed = st.text_area("What assumption has changed?", key=f"assumption-{decision_id}")
        submitted = st.form_submit_button("Record reconsideration")
        if submitted and changed.strip():
            candidate = propose_reconsideration(store, decision_id, changed.strip())
            index.reindex(store)
            st.success(f"Recorded candidate decision `{candidate.id}` (status: PROPOSED).")
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="DecisionTrace", layout="wide")
    st.title("DecisionTrace")
    st.caption("Persistent engineering-decision memory — ask why, get the current answer.")

    store, index = load_store_and_index()

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "current_decision_id" not in st.session_state:
        st.session_state.current_decision_id = None

    conversation_col, card_col = st.columns([3, 2])

    with conversation_col:
        for turn in st.session_state.chat_history:
            with st.chat_message(turn["role"]):
                st.markdown(turn["text"])

        question = st.chat_input("Ask why something is designed this way...")
        if question:
            st.session_state.chat_history.append({"role": "user", "text": question})
            result = answer(question, index)

            lines = []
            for claim in result.claims:
                label = CATEGORY_LABEL.get(claim.category, claim.category.value)
                cite = f" (`{claim.decision_id}`)" if claim.decision_id else ""
                lines.append(f"- {label}{cite}: {claim.text}")
            st.session_state.chat_history.append({
                "role": "assistant", "text": "\n".join(lines) or "No answer produced.",
            })

            if result.candidates_considered:
                st.session_state.current_decision_id = result.candidates_considered[0]
            st.rerun()

    with card_col:
        st.markdown("### Current decision")
        if st.session_state.current_decision_id:
            render_decision_card(st.session_state.current_decision_id, store)
            st.divider()
            render_candidate_form(st.session_state.current_decision_id, store, index)
        else:
            st.info("Ask a question to see the relevant decision here.")


if __name__ == "__main__":
    main()
