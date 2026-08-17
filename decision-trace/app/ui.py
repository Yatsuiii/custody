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
from ingest import ingest_repo  # noqa: E402
from loader import load_decisions  # noqa: E402
from memory import propose_reconsideration  # noqa: E402
from models import DecisionStatus, RelationshipType  # noqa: E402
from retrieval import DecisionIndex, default_cache_path  # noqa: E402
from store import DecisionStore, FirestoreDecisionStore, JSONFileDecisionStore  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
FALSIFIER_DATA = APP_DIR.parent / "data" / "decisions.jsonl"
UI_STORE_PATH = APP_DIR / "data" / "ui_store.jsonl"
FIRESTORE_COLLECTION = "decisiontrace-decisions"

# Excluded from the live demo only, not from data/decisions.jsonl or
# RESULTS.md — this decision is a real, correctly-graded falsifier case
# (RESULTS.md row 30, scored CR), but its "rationale" is literal unfilled
# KEP-template boilerplate from GitHub, not a real design rationale. It
# reads as a fabricated/broken answer in a live demo despite being
# verbatim and correctly cited.
DEMO_EXCLUDED_DECISION_IDS = {"kep-keps-sig-storage-1979-object-storage-support"}

STATUS_COLOR = {
    DecisionStatus.PROPOSED: "amber",
    DecisionStatus.ACCEPTED: "accent",
    DecisionStatus.IMPLEMENTED: "accent",
    DecisionStatus.REVERTED: "danger",
    DecisionStatus.SUPERSEDED: "danger",
    DecisionStatus.REAFFIRMED: "accent",
}

_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&display=swap');
:root {
  --dt-bg: #f4f3ee; --dt-panel: #fdfcf9; --dt-panel-2: #f8f6f0;
  --dt-line: #e0ddd2; --dt-ink: #1e1c17; --dt-ink-dim: #6b6858;
  --dt-ink-faint: #9b9786; --dt-accent: #3f6e52; --dt-accent-dim: rgba(63,110,82,0.1);
  --dt-danger: #b5432e; --dt-danger-dim: rgba(181,67,46,0.09);
  --dt-amber: #a6741c; --dt-amber-dim: rgba(166,116,28,0.1);
  --dt-mono: "IBM Plex Mono", "SF Mono", ui-monospace, Menlo, Consolas, monospace;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: var(--dt-bg); }
[data-testid="stSidebar"] { background: var(--dt-panel); border-right: 1px solid var(--dt-line); }
html, body, [class*="css"] { color: var(--dt-ink); }
h1, h2, h3 { font-weight: 700 !important; letter-spacing: -0.01em; }
h1 { font-size: 22px !important; }
[data-testid="stCaptionContainer"], .stCaption {
  color: var(--dt-ink-faint) !important; font-size: 12.5px !important;
}
p, li, span, label { color: var(--dt-ink); }
code, .stMarkdown code { font-family: var(--dt-mono) !important; background: var(--dt-panel-2) !important;
  border: 1px solid var(--dt-line); border-radius: 4px; color: var(--dt-ink-dim) !important; }
hr { border-color: var(--dt-line) !important; }
a { color: var(--dt-accent) !important; }
[data-testid="stChatMessage"] {
  background: var(--dt-panel) !important; border: 1px solid var(--dt-line) !important;
  border-radius: 8px !important;
}
[data-testid="stChatInput"] { border-color: var(--dt-line) !important; }
[data-testid="stForm"] {
  background: var(--dt-panel-2); border: 1px solid var(--dt-line) !important; border-radius: 6px;
}
.stButton button, .stFormSubmitButton button, [data-testid="stBaseButton-secondary"] {
  background: var(--dt-panel) !important; color: var(--dt-ink) !important;
  border: 1px solid var(--dt-line) !important; border-radius: 5px !important;
  font-size: 12.5px !important;
}
.stButton button:hover, .stFormSubmitButton button:hover { border-color: var(--dt-ink-faint) !important; }
div[data-testid="stAlert"], .stAlert {
  border-radius: 6px !important; border: 1px solid var(--dt-line) !important; background: var(--dt-panel-2) !important;
}
.dt-pill {
  display: inline-block; font-family: var(--dt-mono); font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em; padding: 2px 8px; border-radius: 999px;
  border: 1px solid transparent;
}
.dt-pill-accent { background: var(--dt-accent-dim); color: var(--dt-accent); border-color: rgba(63,110,82,0.3); }
.dt-pill-danger { background: var(--dt-danger-dim); color: var(--dt-danger); border-color: rgba(181,67,46,0.3); }
.dt-pill-amber { background: var(--dt-amber-dim); color: var(--dt-amber); border-color: rgba(166,116,28,0.3); }
.dt-pill-gray { background: var(--dt-panel-2); color: var(--dt-ink-faint); border-color: var(--dt-line); }
</style>
"""


def inject_theme() -> None:
    st.markdown(_THEME_CSS, unsafe_allow_html=True)

CATEGORY_LABEL = {
    ClaimCategory.VERIFIED_HISTORICAL_FACT: "📜 verified historical fact",
    ClaimCategory.CURRENT_ACTIVE_DECISION: "✅ current active decision",
    ClaimCategory.INFERRED_ADVICE: "💭 inferred advice",
    ClaimCategory.MISSING_OR_UNCERTAIN: "❓ missing/uncertain",
}


def grounded_decision_id(claims) -> str | None:
    """The decision id an answer actually resolved to, or None.

    Embedding retrieval always returns candidates even when none of them
    answer the question — `Answer.candidates_considered` reflects that raw
    retrieval, not resolution. The "Current decision" card must track
    what the model actually claimed, not what was merely retrieved, or it
    renders a confident-looking card next to a missing/uncertain answer.
    """
    return next(
        (
            c.decision_id for c in claims
            if c.decision_id and c.category != ClaimCategory.MISSING_OR_UNCERTAIN
        ),
        None,
    )


@st.cache_resource
def load_store_and_index() -> tuple[DecisionStore, DecisionIndex]:
    store: DecisionStore
    if os.environ.get("DECISIONTRACE_STORE") == "firestore":
        store = FirestoreDecisionStore(FIRESTORE_COLLECTION, project=vertex.PROJECT)
    else:
        store = JSONFileDecisionStore(UI_STORE_PATH)
    if not store.list_all():
        decisions = [
            d for d in load_decisions(FALSIFIER_DATA)
            if d.id not in DEMO_EXCLUDED_DECISION_IDS
        ]
        store.save_many(decisions)
    index = DecisionIndex(store, cache_path=default_cache_path())
    return store, index


def render_status_badge(status: DecisionStatus) -> str:
    color = STATUS_COLOR.get(status, "gray")
    return f'<span class="dt-pill dt-pill-{color}">{status.value}</span>'


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
        st.markdown(f"{badge} — this is the currently active decision", unsafe_allow_html=True)
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
            f"Active decision for what it reconsiders: *{active_subject}* (`{active}`)",
            unsafe_allow_html=True,
        )
    else:
        active = resolution.active_id
        active_subject = store.get(active).subject if active else "none"
        st.markdown(
            f"{badge} — **not current**. Active: *{active_subject}* (`{active}`)",
            unsafe_allow_html=True,
        )


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
        st.markdown(
            f"{marker} `{node_id}` — {render_status_badge(node.current_status)}{current_mark}: {node.subject}",
            unsafe_allow_html=True,
        )


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


def render_live_ingest(store: DecisionStore, index: DecisionIndex) -> None:
    """Live ingestion entry point — calls the same `ingest_repo()` already
    proven in `app/tests/test_ingest.py`, on whatever repo the judge types
    in, instead of only ever loading the frozen 55-decision benchmark. A
    failure here (bad repo name, no matching PRs/KEPs, a Gemini error) is
    surfaced as a `st.error`, never swallowed into a silently empty result."""
    with st.sidebar:
        st.markdown("### Live ingest")
        st.caption(
            "Point extraction at a real GitHub repo — pulls merged revert "
            "PRs and KEP-style \"Alternatives Considered\" sections, "
            "extracts them with Gemini, and adds them to this session's "
            "decision memory alongside the benchmark."
        )
        repo = st.text_input("GitHub repo (owner/name)", value="kubernetes/kubernetes")
        target = st.number_input("Max candidates per channel", min_value=1, max_value=10, value=2)
        if st.button("Ingest"):
            with st.spinner(f"Ingesting {repo}..."):
                try:
                    decisions = ingest_repo(repo, revert_target=int(target), kep_target=int(target))
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")
                    return
            if not decisions:
                st.warning(
                    f"No revert pairs or KEP alternatives found in {repo} "
                    "(or none survived quote verification)."
                )
                return
            store.save_many(decisions)
            index.reindex(store)
            st.success(f"Ingested {len(decisions)} decision(s) from {repo}.")


def main() -> None:
    st.set_page_config(page_title="DecisionTrace", layout="wide")
    inject_theme()
    st.title("DecisionTrace")
    st.caption("Persistent engineering-decision memory — ask why, get the current answer.")

    store, index = load_store_and_index()
    render_live_ingest(store, index)

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

            st.session_state.current_decision_id = grounded_decision_id(result.claims)
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
