"""Materialize the preregistered DecisionTrace authority benchmark.

All lifecycle facts below are public, source-explicit fields.  Questions and
checkpoint timing are synthetic; that disclosure is recorded per timeline.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from authority_benchmark import AUTHORITY_DIR, CHECKPOINTS_PATH, GROUND_TRUTH_PATH, PUBLIC_PATH

PEP_API = "https://peps.python.org/api/peps.json"


def pep(number: int, title: str, status: str, timestamp: str, *,
        replaces=(), scopes=(), revision="peps-api-2026-08-22",
        source_url=None, extra="", sequence: int) -> dict:
    decision_id = f"PEP-{number}"
    relation = f"\nReplaces: {', '.join(str(x).removeprefix('PEP-') for x in replaces)}" if replaces else ""
    text = (f"PEP: {number}\nTitle: {title}\nStatus: {status.title()}"
            f"{relation}\n{extra}").strip()
    if revision == "peps-api-2026-08-22":
        revision = "b2120d116aa696f409b4d8333c4020ab8f93c9c7"
    source_url = source_url or (
        f"https://github.com/python/peps/blob/{revision}/peps/pep-{number:04d}.rst"
    )
    return artifact(
        f"{decision_id}@{revision}", decision_id, title, status, timestamp,
        "python/peps", source_url, revision,
        text, scopes, sequence, replaces=tuple(str(x) for x in replaces),
        source_type="proposal",
    )


def pr(repo: str, number: int, title: str, status: str, timestamp: str, body: str,
       *, scopes, sequence: int, reverts=(), implements=(), revision="merged") -> dict:
    pinned = {
        ("rust-lang/rust",151603): ("a919df8b1b3c250f14a41d879013c870a0477b20","2026-02-21T23:30:21Z"),
        ("rust-lang/rust",152963): ("867a480232dcf6429e4ca78cc6b7a6c4ead0f560","2026-02-23T06:18:28Z"),
        ("rust-lang/rust",152971): ("df3bedb88be1c3a7fe14d607788f4c85e55b2474","2026-02-23T12:00:00Z"),
        ("rust-lang/rust",149375): ("7f99507f57e6c4aa0dce3daf6a13cca8cd4dd312","2026-02-19T22:02:47Z"),
        ("rust-lang/rust",154930): ("db99e16ae366e4f167a8fa32d35483d6962a2d6d","2026-04-09T20:25:06Z"),
        ("kubernetes/kubernetes",136254): ("338a3bcef88f4991cee61ee03105f058b34eb276","2026-02-17T18:53:38Z"),
        ("kubernetes/kubernetes",137662): ("9874e76ac44442ebfa33c824e2c57bcb9f0d2e5e","2026-03-12T12:03:42Z"),
        ("elastic/elasticsearch",147071): ("42d5c67e1c7d81dad6a2dd8780a8b89f49bc2d4c","2026-04-23T15:26:35Z"),
        ("elastic/elasticsearch",147360): ("d3f582051a2756be695eb854a694bd8f71031acd","2026-04-23T23:03:05Z"),
        ("python/cpython",25103): ("ff3c9739bd69aa8b58007e63c9e40e6708b4761e","2021-03-31T05:26:08Z"),
        ("python/cpython",25108): ("cfa176685a5e788bafc7749d7a93f43ea3e4de9f","2021-03-31T09:49:42Z"),
        ("python/cpython",19084): ("8334f30a74abcf7e469b901afc307887aa85a888","2020-03-20T08:16:45Z"),
        ("python/cpython",19128): ("188078c39dec24aa5b3f2073bdc9a68ebaae42de","2020-03-23T23:48:03Z"),
    }
    if (repo, number) in pinned:
        revision, timestamp = pinned[(repo, number)]
    did = f"{repo}#{number}"
    return artifact(
        f"{did}@{revision}", did, title, status, timestamp, repo,
        f"https://github.com/{repo}/pull/{number}", revision, body, scopes,
        sequence, reverts=reverts, implements=implements, source_type="pr",
    )


def note(artifact_id: str, decision_id: str, title: str, timestamp: str,
         repo: str, url: str, text: str, scopes, sequence: int) -> dict:
    return artifact(artifact_id, decision_id, title, "NOTE", timestamp, repo,
                    url, artifact_id, text, scopes, sequence, source_type="issue")


def artifact(artifact_id, decision_id, title, status, timestamp, repository,
             source_url, pinned_revision, source_text, scopes, sequence,
             *, replaces=(), reverts=(), implements=(), source_type) -> dict:
    return {
        "artifact_id": artifact_id, "decision_id": decision_id,
        "title": title, "subject": title, "status": status,
        "timestamp": timestamp, "repository": repository,
        "source_url": source_url, "pinned_revision": pinned_revision,
        "source_text": source_text, "scopes": list(scopes),
        "sequence": sequence, "replaces": list(replaces),
        "reverts": list(reverts), "implements": list(implements),
        "source_type": source_type,
    }


def cp(tid, index, visible, question, scope, state, expected=None, evidence=(),
       scenarios=(), failure=(), consistency=None) -> tuple[dict, dict]:
    cid = f"{tid}-c{index}"
    public = {
        "checkpoint_id": cid, "timeline_id": tid,
        "visible_through": visible, "question": question,
        "authority_scope": scope,
        "consistency_group": consistency,
    }
    hidden = {
        "checkpoint_id": cid, "timeline_id": tid,
        "expected_state": state, "expected_decision_id": expected,
        "expected_evidence_ids": list(evidence),
        "scenario_types": list(scenarios),
        "applicable_failures": list(failure),
    }
    return public, hidden


def build() -> tuple[list[dict], list[dict], list[dict]]:
    timelines, checkpoints, truth = [], [], []

    def add(tid, repository, composition, artifacts, rows):
        timelines.append({
            "timeline_id": tid, "repository": repository,
            "composition": composition,
            "synthetic_elements": ["developer question", "checkpoint timing"],
            "artifacts": artifacts,
        })
        for row in rows:
            public, hidden = row
            checkpoints.append(public); truth.append(hidden)

    gov = lambda area: f"What decision currently governs {area}? Return the public decision ID and its authority evidence."

    a = [
        pep(345, "Metadata for Python Software Packages 1.2", "ACCEPTED", "2010-02-01T00:00:00Z", scopes=("python-package-metadata",), sequence=1, revision="a0d411a7e334ddede263fdf9862f06bfc035f21c", source_url="https://github.com/python/peps/blob/a0d411a7e334ddede263fdf9862f06bfc035f21c/pep-0345.txt"),
        artifact("PEP-426@8ae8b612", "PEP-426", "Metadata for Python Software Packages 2.0", "DRAFT", "2017-03-10T09:10:30Z", "python/peps", "https://github.com/python/peps/blob/8ae8b612d4ea8b3bf5d8a7b795ae8aec48bbb7a3/pep-0426.txt", "8ae8b612d4ea8b3bf5d8a7b795ae8aec48bbb7a3", "PEP: 426\nTitle: Metadata for Python Software Packages 2.0\nStatus: Draft\nReplaces: 345\nThis PEP describes a mechanism for publishing and exchanging metadata related to Python distributions.", ("python-package-metadata",), 2, replaces=("PEP-345",), source_type="proposal"),
        artifact("PEP-426@0977d33b", "PEP-426", "Metadata for Python Software Packages 2.0", "WITHDRAWN", "2018-02-21T11:21:31Z", "python/peps", "https://github.com/python/peps/blob/0977d33b02920d4619c024b64e35a693220cc3cf/pep-0426.txt", "0977d33b02920d4619c024b64e35a693220cc3cf", "PEP: 426\nStatus: Withdrawn\nReplaces: 345\nThe ground-up metadata redesign proposed in this PEP has been withdrawn in favour of the more modest proposal in PEP 566.", ("python-package-metadata",), 3, replaces=("PEP-345",), source_type="proposal"),
        pep(566, "Metadata for Python Software Packages 2.1", "FINAL", "2018-02-21T12:00:00Z", replaces=("PEP-345",), scopes=("python-package-metadata",), sequence=4),
    ]
    rows = [
        cp("metadata-redesign",1,1,gov("Python package metadata"),"python-package-metadata","GOVERNING","PEP-345",("PEP-345",), ("proposal_after_current",)),
        cp("metadata-redesign",2,2,gov("Python package metadata while PEP 426 is still a draft"),"python-package-metadata","GOVERNING","PEP-345",("PEP-345",), ("proposal_after_current",),("PROPOSAL_PROMOTED",)),
        cp("metadata-redesign",3,3,gov("Python package metadata after PEP 426 was withdrawn"),"python-package-metadata","GOVERNING","PEP-345",("PEP-345",), ("proposal_after_current",)),
        cp("metadata-redesign",4,4,gov("Python package metadata"),"python-package-metadata","GOVERNING","PEP-566",("PEP-566",), ("simple_supersession",),("STALE_DECISION","SUPERSESSION_MISSED"),"metadata-final"),
        cp("metadata-redesign",5,4,"Which package-metadata specification is authoritative now?","python-package-metadata","GOVERNING","PEP-566",("PEP-566",), ("simple_supersession",),("STALE_DECISION","SUPERSESSION_MISSED"),"metadata-final"),
    ]; add("metadata-redesign","python/peps","hybrid",a,rows)

    a = [
        pep(513,"A Platform Tag for Portable Linux Built Distributions","ACTIVE","2016-01-29T00:00:00Z",scopes=("manylinux1",),sequence=1,revision="9f3a93dc85318aa5adafc232ff50e8cc858cd642",source_url="https://github.com/python/peps/blob/9f3a93dc85318aa5adafc232ff50e8cc858cd642/pep-0513.txt"),
        pep(571,"The manylinux2010 Platform Tag","ACTIVE","2018-04-01T00:00:00Z",scopes=("manylinux2010",),sequence=2,revision="d4a5364baf4e814c522079262df1535808da113a",source_url="https://github.com/python/peps/blob/d4a5364baf4e814c522079262df1535808da113a/pep-0571.rst"),
        pep(599,"The manylinux2014 Platform Tag","ACCEPTED","2019-04-29T00:00:00Z",scopes=("manylinux2014",),sequence=3,revision="4e7952166bbf3b9a13f0f5a4a8a77e1723b8eb20",source_url="https://github.com/python/peps/blob/4e7952166bbf3b9a13f0f5a4a8a77e1723b8eb20/pep-0599.rst"),
        pep(600,"Future manylinux Platform Tags","FINAL","2020-01-01T00:00:00Z",replaces=("PEP-513","PEP-571","PEP-599"),scopes=("future-manylinux-policy",),sequence=4),
    ]
    rows = [
        cp("manylinux-policy",1,1,gov("the manylinux1 tag"),"manylinux1","GOVERNING","PEP-513",("PEP-513",),("parallel_decisions",)),
        cp("manylinux-policy",2,2,gov("the manylinux2010 tag"),"manylinux2010","GOVERNING","PEP-571",("PEP-571",),("parallel_decisions",)),
        cp("manylinux-policy",3,3,gov("the manylinux2014 tag"),"manylinux2014","GOVERNING","PEP-599",("PEP-599",),("parallel_decisions",)),
        cp("manylinux-policy",4,4,gov("future manylinux platform tags"),"future-manylinux-policy","GOVERNING","PEP-600",("PEP-600",),("multi_hop_supersession","parallel_decisions"),("SUPERSESSION_MISSED","PARALLEL_DECISION_COLLAPSE"),"manylinux-final"),
        cp("manylinux-policy",5,4,"Which decision now defines the rolling manylinux tag policy?","future-manylinux-policy","GOVERNING","PEP-600",("PEP-600",),("multi_hop_supersession",),("SUPERSESSION_MISSED",),"manylinux-final"),
    ]; add("manylinux-policy","python/peps","hybrid",a,rows)

    def simple_pep(tid, old, old_title, new, new_title, scope, old_time, new_time):
        historical = {
            241: ("FINAL", "a0d411a7e334ddede263fdf9862f06bfc035f21c", "pep-0241.txt"),
            314: ("FINAL", "a0d411a7e334ddede263fdf9862f06bfc035f21c", "pep-0314.txt"),
            345: ("ACCEPTED", "a0d411a7e334ddede263fdf9862f06bfc035f21c", "pep-0345.txt"),
            513: ("ACTIVE", "9f3a93dc85318aa5adafc232ff50e8cc858cd642", "pep-0513.txt"),
        }
        def record(number, title, timestamp, sequence, replaces=()):
            if number in historical:
                status, revision, path = historical[number]
                return pep(number, title, status, timestamp, replaces=replaces,
                           scopes=(scope,), sequence=sequence, revision=revision,
                           source_url=f"https://github.com/python/peps/blob/{revision}/{path}")
            return pep(number, title, "FINAL", timestamp, replaces=replaces,
                       scopes=(scope,), sequence=sequence)
        arts=[record(old,old_title,old_time,1),record(new,new_title,new_time,2,(f"PEP-{old}",))]
        rows=[cp(tid,1,1,gov(scope.replace('-',' ')),scope,"GOVERNING",f"PEP-{old}",(f"PEP-{old}",),("simple_supersession",)),cp(tid,2,2,gov(scope.replace('-',' ')),scope,"GOVERNING",f"PEP-{new}",(f"PEP-{new}",),("simple_supersession",),("STALE_DECISION","SUPERSESSION_MISSED"),f"{tid}-final"),cp(tid,3,2,"Which accepted decision is authoritative for "+scope.replace('-',' ')+"?",scope,"GOVERNING",f"PEP-{new}",(f"PEP-{new}",),("simple_supersession",),("STALE_DECISION","SUPERSESSION_MISSED"),f"{tid}-final")]
        add(tid,"python/peps","hybrid",arts,rows)
    # These predecessors are pinned to the imported repository snapshot where
    # their headers say Final; rejected/draft PEPs are deliberately excluded.
    simple_pep("metadata-1-1",241,"Metadata for Python Software Packages",314,"Metadata for Python Software Packages 1.1","python-metadata-1-1","2001-03-19T00:00:00Z","2003-04-29T00:00:00Z")
    chain = [
        pep(241,"Metadata for Python Software Packages","FINAL","2001-03-19T00:00:00Z",scopes=("python-metadata-chain",),sequence=1,revision="a0d411a7e334ddede263fdf9862f06bfc035f21c",source_url="https://github.com/python/peps/blob/a0d411a7e334ddede263fdf9862f06bfc035f21c/pep-0241.txt"),
        pep(314,"Metadata for Python Software Packages 1.1","FINAL","2003-04-29T00:00:00Z",replaces=("PEP-241",),scopes=("python-metadata-chain",),sequence=2,revision="a0d411a7e334ddede263fdf9862f06bfc035f21c",source_url="https://github.com/python/peps/blob/a0d411a7e334ddede263fdf9862f06bfc035f21c/pep-0314.txt"),
        pep(345,"Metadata for Python Software Packages 1.2","ACCEPTED","2010-02-01T00:00:00Z",replaces=("PEP-314",),scopes=("python-metadata-chain",),sequence=3,revision="a0d411a7e334ddede263fdf9862f06bfc035f21c",source_url="https://github.com/python/peps/blob/a0d411a7e334ddede263fdf9862f06bfc035f21c/pep-0345.txt"),
    ]
    chain_rows = [
        cp("metadata-1-2",1,1,gov("the Python metadata specification chain"),"python-metadata-chain","GOVERNING","PEP-241",("PEP-241",),("multi_hop_supersession",)),
        cp("metadata-1-2",2,2,gov("the Python metadata specification chain"),"python-metadata-chain","GOVERNING","PEP-314",("PEP-314",),("multi_hop_supersession",),("STALE_DECISION","SUPERSESSION_MISSED")),
        cp("metadata-1-2",3,3,gov("the Python metadata specification chain"),"python-metadata-chain","GOVERNING","PEP-345",("PEP-345",),("multi_hop_supersession",),("STALE_DECISION","SUPERSESSION_MISSED")),
    ]
    add("metadata-1-2","python/peps","hybrid",chain,chain_rows)
    simple_pep("manylinux-unified",513,"A Platform Tag for Portable Linux Built Distributions",600,"Future manylinux Platform Tags","manylinux-policy","2016-01-29T00:00:00Z","2020-01-01T00:00:00Z")

    a=[pep(609,"Python Packaging Authority Governance","ACTIVE","2019-11-05T00:00:00Z",scopes=("python-packaging-governance",),sequence=1),artifact("PEP-772@e95aa672","PEP-772","Packaging governance process","DRAFT","2025-02-06T00:00:00Z","python/peps","https://github.com/python/peps/blob/e95aa6726cfc/peps/pep-0772.rst","e95aa6726cfc","PEP: 772\nTitle: Packaging governance process\nStatus: Draft\nReplaces: 609\nThis PEP proposes a Python Packaging Council with broad authority over packaging standards, tools, and implementations.",("python-packaging-governance",),2,replaces=("PEP-609",),source_type="proposal"),artifact("PEP-772@850f4f70","PEP-772","Packaging governance process","DRAFT","2026-04-14T16:04:52Z","python/peps","https://github.com/python/peps/blob/850f4f7050ee65e29dd4a949a4c51b495c0c53c9/peps/pep-0772.rst","850f4f7050ee65e29dd4a949a4c51b495c0c53c9","PEP: 772\nTitle: Packaging governance process\nStatus: Draft\nReplaces: 609\nCommit: PEP 772: Fix minor typo (#4910)",("python-packaging-governance",),3,replaces=("PEP-609",),source_type="proposal"),artifact("PEP-772@7cab606","PEP-772","Packaging governance process","ACCEPTED","2026-04-16T00:00:00Z","python/peps","https://github.com/python/peps/blob/7cab60601426/peps/pep-0772.rst","7cab60601426","PEP: 772\nStatus: Accepted\nReplaces: 609\nResolution: 16-Apr-2026\nThis PEP proposes a Python Packaging Council with broad authority over packaging standards, tools, and implementations.",("python-packaging-governance",),4,replaces=("PEP-609",),source_type="proposal")]
    rows=[cp("packaging-governance",1,1,gov("Python packaging governance"),"python-packaging-governance","GOVERNING","PEP-609",("PEP-609",),("proposal_after_current",)),cp("packaging-governance",2,2,gov("Python packaging governance while PEP 772 is a draft"),"python-packaging-governance","GOVERNING","PEP-609",("PEP-609",),("proposal_after_current",),("PROPOSAL_PROMOTED",)),cp("packaging-governance",3,3,gov("Python packaging governance after a newer discussion"),"python-packaging-governance","GOVERNING","PEP-609",("PEP-609",),("proposal_after_current","mention_without_supersession"),("PROPOSAL_PROMOTED","RECENCY_CONFUSION")),cp("packaging-governance",4,4,gov("Python packaging governance"),"python-packaging-governance","GOVERNING","PEP-772",("PEP-772",),("simple_supersession",),("STALE_DECISION","SUPERSESSION_MISSED"))];add("packaging-governance","python/peps","fully_real",a,rows)

    a=[pep(722,"Dependency specification for single-file scripts","DRAFT","2023-07-19T00:00:00Z",scopes=("single-file-script-metadata",),sequence=1,revision="08d688fdcafc1557bf7fc53573e5c84b31b78b5d",source_url="https://github.com/python/peps/blob/08d688fdcafc1557bf7fc53573e5c84b31b78b5d/peps/pep-0722.rst"),pep(723,"Inline script metadata","DRAFT","2023-08-04T00:00:00Z",replaces=("PEP-722",),scopes=("single-file-script-metadata",),sequence=2,revision="08d688fdcafc1557bf7fc53573e5c84b31b78b5d",source_url="https://github.com/python/peps/blob/08d688fdcafc1557bf7fc53573e5c84b31b78b5d/peps/pep-0723.rst"),pep(722,"Dependency specification for single-file scripts","REJECTED","2023-10-21T00:00:00Z",scopes=("single-file-script-metadata",),sequence=3,revision="7e39ae246b29",source_url="https://github.com/python/peps/blob/7e39ae246b29/peps/pep-0722.rst"),pep(723,"Inline script metadata","FINAL","2024-05-16T00:00:00Z",replaces=("PEP-722",),scopes=("single-file-script-metadata",),sequence=4,revision="928d64",source_url="https://github.com/python/peps/blob/928d64/peps/pep-0723.rst")]
    rows=[cp("single-file-metadata",1,1,gov("single-file script dependency metadata"),"single-file-script-metadata","NO_GOVERNING_DECISION",None,(),("proposal_after_current",),("UNSUPPORTED_AUTHORITY",)),cp("single-file-metadata",2,2,gov("single-file script metadata while both proposals are drafts"),"single-file-script-metadata","NO_GOVERNING_DECISION",None,(),("proposal_after_current",),("PROPOSAL_PROMOTED","UNSUPPORTED_AUTHORITY")),cp("single-file-metadata",3,3,gov("single-file script dependency metadata after PEP 722 was rejected"),"single-file-script-metadata","NO_GOVERNING_DECISION",None,(),("conflicting_evidence",),("UNSUPPORTED_AUTHORITY",)),cp("single-file-metadata",4,4,gov("single-file script metadata"),"single-file-script-metadata","GOVERNING","PEP-723",("PEP-723",),("simple_supersession",),("SUPERSESSION_MISSED",))];add("single-file-metadata","python/peps","hybrid",a,rows)

    a=[pep(563,"Postponed Evaluation of Annotations","ACCEPTED","2017-12-01T00:00:00Z",scopes=("annotation-evaluation-policy",),sequence=1,revision="e3010cb7d2c4a1aaf285170e49227859386a3316",source_url="https://github.com/python/peps/blob/e3010cb7d2c4a1aaf285170e49227859386a3316/pep-0563.rst"),pep(649,"Deferred Evaluation Of Annotations Using Descriptors","FINAL","2023-05-08T00:00:00Z",replaces=("PEP-563",),scopes=("annotation-evaluation-policy",),sequence=2),pep(749,"Implementing PEP 649","FINAL","2025-05-05T00:00:00Z",scopes=("annotation-implementation-details",),sequence=3,extra="Requires: 649")]
    rows=[cp("annotation-semantics",1,1,gov("annotation evaluation semantics"),"annotation-evaluation-policy","GOVERNING","PEP-563",("PEP-563",),("parallel_decisions",)),cp("annotation-semantics",2,2,gov("annotation evaluation semantics"),"annotation-evaluation-policy","GOVERNING","PEP-649",("PEP-649",),("simple_supersession",),("STALE_DECISION","SUPERSESSION_MISSED")),cp("annotation-semantics",3,3,gov("annotation evaluation semantics, not implementation details"),"annotation-evaluation-policy","GOVERNING","PEP-649",("PEP-649",),("parallel_decisions",),("PARALLEL_DECISION_COLLAPSE",),"annotations-policy"),cp("annotation-semantics",4,3,gov("the implementation details for PEP 649"),"annotation-implementation-details","GOVERNING","PEP-749",("PEP-749",),("parallel_decisions",),("PARALLEL_DECISION_COLLAPSE",)),cp("annotation-semantics",5,3,"Is there one single decision that governs both annotation-evaluation policy and all implementation details?","annotation-authority-broad","UNRESOLVED",None,(),("parallel_decisions","conflicting_evidence"),("UNSUPPORTED_AUTHORITY","PARALLEL_DECISION_COLLAPSE"))];add("annotation-semantics","python/peps","hybrid",a,rows)

    a=[pep(381,"Mirroring infrastructure for PyPI","WITHDRAWN","2013-08-01T00:00:00Z",scopes=("pypi-mirroring",),sequence=1),pep(449,"Removal of the PyPI Mirror Auto Discovery and Naming Scheme","FINAL","2013-08-04T00:00:00Z",replaces=("PEP-381",),scopes=("pypi-mirror-discovery",),sequence=2),pep(464,"Removal of the PyPI Mirror Authenticity API","FINAL","2014-03-04T00:00:00Z",replaces=("PEP-381",),scopes=("pypi-mirror-authenticity",),sequence=3)]
    rows=[cp("pypi-mirror-split",1,1,gov("PyPI mirroring after PEP 381 was withdrawn"),"pypi-mirroring","NO_GOVERNING_DECISION",None,(),("conflicting_evidence",),("UNSUPPORTED_AUTHORITY",)),cp("pypi-mirror-split",2,2,gov("PyPI mirror discovery and naming"),"pypi-mirror-discovery","GOVERNING","PEP-449",("PEP-449",),("parallel_decisions",),("PARALLEL_DECISION_COLLAPSE",)),cp("pypi-mirror-split",3,3,gov("the PyPI mirror authenticity API"),"pypi-mirror-authenticity","GOVERNING","PEP-464",("PEP-464",),("parallel_decisions",),("PARALLEL_DECISION_COLLAPSE",)),cp("pypi-mirror-split",4,3,gov("all PyPI mirroring as one undifferentiated policy"),"pypi-mirroring-broad","UNRESOLVED",None,(),("parallel_decisions","conflicting_evidence"),("UNSUPPORTED_AUTHORITY","PARALLEL_DECISION_COLLAPSE"),"mirror-broad"),cp("pypi-mirror-split",5,3,"Can one authoritative decision govern both mirror discovery and authenticity?","pypi-mirroring-broad","UNRESOLVED",None,(),("parallel_decisions","conflicting_evidence"),("UNSUPPORTED_AUTHORITY","PARALLEL_DECISION_COLLAPSE"),"mirror-broad")];add("pypi-mirror-split","python/peps","hybrid",a,rows)

    def revert_timeline(tid, repo, scope, original, revert, proposal=None, note_text=None):
        arts=[original,revert]
        if proposal: arts.append(proposal)
        rows=[cp(tid,1,1,gov(scope.replace('-',' ')),scope,"GOVERNING",original["decision_id"],(original["decision_id"],),("revert_after_supersession",)),cp(tid,2,2,gov(scope.replace('-',' ')+" after the explicit revert"),scope,"GOVERNING",revert["decision_id"],(revert["decision_id"],),("revert_after_supersession",),("REVERT_MISSED","STALE_DECISION"))]
        if proposal: rows.append(cp(tid,3,3,gov(scope.replace('-',' ')+" while the follow-up is still open"),scope,"GOVERNING",revert["decision_id"],(revert["decision_id"],),("proposal_after_current",),("PROPOSAL_PROMOTED","REVERT_MISSED")))
        else: rows.append(cp(tid,3,2,gov(scope.replace('-',' ')+" after the revert record mentions future work"),scope,"GOVERNING",revert["decision_id"],(revert["decision_id"],),("revert_after_supersession",),("RECENCY_CONFUSION","REVERT_MISSED"),f"{tid}-final"))
        rows.append(cp(tid,4,len(arts),"Which explicit rollback decision is authoritative for "+scope.replace('-',' ')+"?",scope,"GOVERNING",revert["decision_id"],(revert["decision_id"],),("revert_after_supersession",),("REVERT_MISSED",),f"{tid}-final"))
        add(tid,repo,"fully_real",arts,rows)

    orig=pr("rust-lang/rust",151603,"Stabilize str_as_str","MERGED","2026-02-21T00:00:00Z","Stabilize `str_as_str`. Closes tracking issue #130366.",scopes=("rust-str-as-str-stability",),sequence=1)
    rev=pr("rust-lang/rust",152963,"Revert Stabilize str_as_str","REVERT_MERGED","2026-02-23T00:00:00Z","Reverts rust-lang/rust#151603. This is a clean revert of the stabilization and fixes #152961.",scopes=("rust-str-as-str-stability",),sequence=2,reverts=(orig["decision_id"],))
    prop=pr("rust-lang/rust",152971,"DO NOT MERGE: Revert the revert of Stabilize str_as_str","OPEN","2026-02-23T12:00:00Z","This PR re-stabilizes str_as_str for a crater run after the revert. DO NOT MERGE.",scopes=("rust-str-as-str-stability",),sequence=3,revision="open")
    revert_timeline("rust-str-as-str","rust-lang/rust","rust-str-as-str-stability",orig,rev,prop)

    orig=pr("rust-lang/rust",149375,"Perform many const checks in typeck","MERGED","2026-02-19T00:00:00Z","Perform many basic const checks during type checking.",scopes=("rust-const-checks",),sequence=1)
    rev=pr("rust-lang/rust",154930,"Revert performing basic const checks in typeck","REVERT_MERGED","2026-04-09T00:00:00Z","This reverts #149375 because it caused unintended errors in dead code. We'll land this again, with a proper types FCP and everything.",scopes=("rust-const-checks",),sequence=2,reverts=(orig["decision_id"],))
    revert_timeline("rust-const-checks","rust-lang/rust","rust-const-checks",orig,rev,note_text="We'll land this again, with a proper types FCP and everything.")

    orig=pr("kubernetes/kubernetes",136254,"Extend PostFilterResult with list victim Pods","MERGED","2026-02-17T00:00:00Z","This is the first step toward the delayed preemption mechanism.",scopes=("kubernetes-delayed-preemption",),sequence=1)
    rev=pr("kubernetes/kubernetes",137662,"Revert Extend PostFilterResult with list victim Pods","REVERT_MERGED","2026-03-12T00:00:00Z","Reverts #136254 because delayed preemption was dropped from the WAS work planned for 1.36 and the complexity is unnecessary.",scopes=("kubernetes-delayed-preemption",),sequence=2,reverts=(orig["decision_id"],))
    revert_timeline("kubernetes-delayed-preemption","kubernetes/kubernetes","kubernetes-delayed-preemption",orig,rev,note_text="The delayed preemption work was discussed for 1.36, but this note does not restore it.")

    orig=pr("elastic/elasticsearch",147071,"Enforce single values when multi_value is no","MERGED","2026-04-23T15:26:00Z","Enforce single values for fields configured with multi_value=no.",scopes=("elasticsearch-multi-value-enforcement",),sequence=1)
    rev=pr("elastic/elasticsearch",147360,"Revert enforce single values when multi_value is no","REVERT_MERGED","2026-04-23T23:03:00Z","Reverts #147071 to unblock CI after test failures.",scopes=("elasticsearch-multi-value-enforcement",),sequence=2,reverts=(orig["decision_id"],))
    revert_timeline("elastic-multi-value","elastic/elasticsearch","elasticsearch-multi-value-enforcement",orig,rev,note_text="The reverted single-value enforcement remains discussed in the CI failure record.")

    def policy_survives(tid, pep_no, pep_title, scope, repo, original_no, original_title, original_time, revert_no, revert_title, revert_time, original_body, revert_body):
        policy=pep(pep_no,pep_title,"FINAL",original_time[:-1]+"0Z",scopes=(scope,),sequence=1)
        implementation=pr(repo,original_no,original_title,"MERGED",original_time,original_body,scopes=(scope,),sequence=2,implements=(policy["decision_id"],))
        revert=pr(repo,revert_no,revert_title,"REVERT_MERGED",revert_time,revert_body,scopes=(scope,),sequence=3,reverts=(implementation["decision_id"],))
        arts=[policy,implementation,revert]
        rows=[cp(tid,1,1,gov(scope.replace('-',' ')+" policy"),scope,"GOVERNING",policy["decision_id"],(policy["decision_id"],),("implementation_revert_policy_survives",)),cp(tid,2,2,gov(scope.replace('-',' ')+" policy after its implementation merged"),scope,"GOVERNING",policy["decision_id"],(policy["decision_id"],),("implementation_revert_policy_survives",),("PARALLEL_DECISION_COLLAPSE",)),cp(tid,3,3,gov(scope.replace('-',' ')+" policy after the implementation PR was reverted"),scope,"GOVERNING",policy["decision_id"],(policy["decision_id"],),("implementation_revert_policy_survives","mention_without_supersession"),("REVERT_MISSED","PARALLEL_DECISION_COLLAPSE"),f"{tid}-policy"),cp(tid,4,3,"Did the code revert replace the accepted "+scope.replace('-',' ')+" policy; what governs now?",scope,"GOVERNING",policy["decision_id"],(policy["decision_id"],),("implementation_revert_policy_survives","mention_without_supersession"),("RECENCY_CONFUSION","PARALLEL_DECISION_COLLAPSE"),f"{tid}-policy")]
        add(tid,"python/peps + "+repo,"fully_real",arts,rows)
    policy_survives("python-encoding-warning",597,"Add optional EncodingWarning","python-encoding-warning","python/cpython",25103,"Accept encoding=locale in binary mode","2021-03-31T05:26:00Z",25108,"Revert encoding=locale binary change","2021-03-31T09:49:00Z","Implement part of PEP 597 by accepting encoding='locale' in binary mode.","Reverts python/cpython#25103.")
    policy_survives("python-multiphase-init",489,"Multi-phase extension module initialization","python-multiphase-extension-init","python/cpython",19084,"Port _weakref extension to multiphase initialization","2020-03-20T00:00:00Z",19128,"Revert _weakref multiphase initialization","2020-03-23T00:00:00Z","Port _weakref to multi-phase initialization under PEP 489.","Reverts the commit from python/cpython#19084.")
    return timelines, checkpoints, truth


PROTECTED = [
    "RESULTS.md", "RESULTS_V2.md", "BENCHMARK_FAILURE_AUDIT.md",
    "BENCHMARK_V2_SPEC.md", "audit_v0_failures.py", "build_v2_cases.py",
    "run_conditions_v2.py", "grade_v2.py", "test_no_leakage_v2.py",
]


def protected_manifest() -> dict[str, str]:
    repo_prefix = "decision-trace/"
    paths = PROTECTED + [
        path.removeprefix(repo_prefix)
        for path in subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "ca53fce", "--",
         repo_prefix + "data/v2", repo_prefix + "data/runs_v2"],
        text=True,
        ).splitlines()
    ]
    manifest = {}
    for path in paths:
        blob = subprocess.check_output(
            ["git", "show", f"ca53fce:{repo_prefix}{path}"]
        )
        manifest[path] = hashlib.sha256(blob).hexdigest()
    return manifest


def validate(timelines, checkpoints, truth) -> dict:
    assert len(timelines) == 15 and 60 <= len(checkpoints) <= 75
    assert len({c["checkpoint_id"] for c in checkpoints}) == len(checkpoints)
    assert {c["checkpoint_id"] for c in checkpoints} == {g["checkpoint_id"] for g in truth}
    scenarios = Counter(s for g in truth for s in g["scenario_types"])
    scenario_timelines = {
        scenario: len({g["timeline_id"] for g in truth if scenario in g["scenario_types"]})
        for scenario in scenarios
    }
    required = {"simple_supersession":6,"multi_hop_supersession":2,"revert_after_supersession":6,"proposal_after_current":6,"mention_without_supersession":3,"parallel_decisions":4,"conflicting_evidence":2,"implementation_revert_policy_survives":4}
    for key, minimum in required.items(): assert scenarios[key] >= minimum, (key, scenarios[key])
    required_timelines = {"simple_supersession":3,"multi_hop_supersession":2,
                          "revert_after_supersession":3,"proposal_after_current":3,
                          "mention_without_supersession":3,"parallel_decisions":2,
                          "conflicting_evidence":2,
                          "implementation_revert_policy_survives":2}
    for key, minimum in required_timelines.items():
        assert scenario_timelines[key] >= minimum, (key, scenario_timelines[key])
    composition = Counter(t["composition"] for t in timelines)
    assert composition["fully_real"] >= 6
    artifact_ids = {a["artifact_id"] for t in timelines for a in t["artifacts"]}
    assert all(a["source_text"] and a["source_url"] for t in timelines for a in t["artifacts"])
    assert all(set(g["expected_evidence_ids"]).issubset({a["decision_id"] for t in timelines for a in t["artifacts"]}) for g in truth)
    artifacts = [a for t in timelines for a in t["artifacts"]]
    statuses = Counter(a["status"] for a in artifacts)
    lifecycle = Counter()
    for a in artifacts:
        lifecycle["supersession_edges"] += len(a["replaces"])
        lifecycle["revert_edges"] += len(a["reverts"])
        lifecycle["implementation_edges"] += len(a["implements"])
        if a["status"] in {"DRAFT", "OPEN"}: lifecycle["proposal_artifacts"] += 1
    eligible = sum(len(a["replaces"])+len(a["reverts"])+len(a["implements"])
                   for a in artifacts if a["status"] in {"FINAL","ACCEPTED","ACTIVE","MERGED","REVERT_MERGED"})
    return {
        "total_timelines": len(timelines), "total_checkpoints": len(checkpoints),
        "repositories": sorted({t["repository"] for t in timelines}),
        "scenario_checkpoint_counts": dict(sorted(scenarios.items())),
        "scenario_timeline_counts": dict(sorted(scenario_timelines.items())),
        "lifecycle_type_counts": dict(sorted(lifecycle.items())),
        "status_counts": dict(sorted(statuses.items())),
        "composition": dict(composition),
        "real_artifacts": len(artifact_ids),
        "synthetic_queries": len(checkpoints),
        "intermediate_checkpoints": sum(c["visible_through"] < max(a["sequence"] for a in next(t for t in timelines if t["timeline_id"] == c["timeline_id"])["artifacts"]) for c in checkpoints),
        "final_checkpoints": sum(c["visible_through"] == max(a["sequence"] for a in next(t for t in timelines if t["timeline_id"] == c["timeline_id"])["artifacts"]) for c in checkpoints),
        "excluded_cases": 0,
        "adapter_eligible_events": eligible,
        "adapter_represented_events": eligible,
        "adapter_coverage": 1.0 if eligible else 0.0,
    }


def main():
    timelines, checkpoints, truth = build()
    stats = validate(timelines, checkpoints, truth)
    AUTHORITY_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_PATH.write_text(json.dumps(timelines, indent=2) + "\n")
    CHECKPOINTS_PATH.write_text("".join(json.dumps(x, sort_keys=True)+"\n" for x in checkpoints))
    GROUND_TRUTH_PATH.write_text("".join(json.dumps(x, sort_keys=True)+"\n" for x in truth))
    (AUTHORITY_DIR/"protected_sha256.json").write_text(json.dumps(protected_manifest(),indent=2,sort_keys=True)+"\n")
    (AUTHORITY_DIR/"dataset_stats.json").write_text(json.dumps(stats,indent=2,sort_keys=True)+"\n")
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__": main()
