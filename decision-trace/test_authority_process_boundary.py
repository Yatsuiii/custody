import json
import subprocess
import sys

from authority_benchmark import adapt_decisions, load_public, visible_checkpoint

sys.path.insert(0,"app")
from authority import resolve_authority
from store import JSONFileDecisionStore


def test_fresh_process_continuation_matches_uninterrupted_replay(tmp_path):
    timelines,checkpoints=load_public(); by_t={t["timeline_id"]:t for t in timelines}
    pairs=(("packaging-governance","packaging-governance-c2","packaging-governance-c4"),
           ("rust-str-as-str","rust-str-as-str-c2","rust-str-as-str-c3"))
    by_c={c["checkpoint_id"]:c for c in checkpoints}
    for timeline_id,middle_id,final_id in pairs:
        timeline=by_t[timeline_id]; middle=by_c[middle_id]; final=by_c[final_id]
        store_path=tmp_path/f"{timeline_id}.jsonl"
        middle_decisions,_=adapt_decisions(visible_checkpoint(timeline,middle))
        JSONFileDecisionStore(store_path).save_many(middle_decisions)
        proc=subprocess.run([sys.executable,"process_boundary_authority.py",timeline_id,final_id,str(store_path)],check=True,capture_output=True,text=True)
        restarted=json.loads(proc.stdout)
        full,_=adapt_decisions(visible_checkpoint(timeline,final))
        uninterrupted=resolve_authority(full,final["authority_scope"])
        assert restarted=={"state":uninterrupted.state,
                           "governing_decision_id":uninterrupted.governing_decision_id,
                           "evidence_ids":list(uninterrupted.evidence_ids)}
