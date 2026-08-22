"""Fresh-process continuation probe for the secondary persistence test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from authority_benchmark import adapt_decisions, load_public, visible_checkpoint

sys.path.insert(0,str(Path(__file__).resolve().parent/"app"))
from authority import resolve_authority  # noqa: E402
from store import JSONFileDecisionStore  # noqa: E402


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("timeline"); parser.add_argument("checkpoint"); parser.add_argument("store",type=Path)
    args=parser.parse_args()
    timelines,checkpoints=load_public(); timeline=next(t for t in timelines if t["timeline_id"]==args.timeline)
    checkpoint=next(c for c in checkpoints if c["checkpoint_id"]==args.checkpoint)
    decisions,_=adapt_decisions(visible_checkpoint(timeline,checkpoint))
    store=JSONFileDecisionStore(args.store); store.save_many(decisions)
    got=resolve_authority(store.list_all(),checkpoint["authority_scope"])
    print(json.dumps({"state":got.state,"governing_decision_id":got.governing_decision_id,"evidence_ids":got.evidence_ids}))


if __name__=="__main__":main()
