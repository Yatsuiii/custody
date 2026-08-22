# Authority benchmark source spot checks

Checked before any Gemini generation. Quoted text is present in the public
artifact record and the linked immutable source. Developer questions and
checkpoint placement are synthetic; lifecycle facts are not.

## Supersession (3)

1. **`metadata-1-2`** — Python PEP repository snapshot
   `a0d411a7e334ddede263fdf9862f06bfc035f21c`.
   PEP 241 says `Status: Final`; PEP 314 says `Status: Final` and
   `Replaces: 241`; PEP 345 says `Status: Accepted` and `Replaces: 314`.
   Therefore the checkpoints resolve PEP-241, then PEP-314, then PEP-345.
   Sources: [PEP 241](https://github.com/python/peps/blob/a0d411a7e334ddede263fdf9862f06bfc035f21c/pep-0241.txt),
   [PEP 314](https://github.com/python/peps/blob/a0d411a7e334ddede263fdf9862f06bfc035f21c/pep-0314.txt),
   [PEP 345](https://github.com/python/peps/blob/a0d411a7e334ddede263fdf9862f06bfc035f21c/pep-0345.txt).

2. **`metadata-redesign`** — PEP 426 at
   `8ae8b612d4ea8b3bf5d8a7b795ae8aec48bbb7a3` says `Status: Draft` and
   `Replaces: 345`; at `0977d33b02920d4619c024b64e35a693220cc3cf`
   it says `Status: Withdrawn` and that the redesign was “withdrawn in favour
   of” PEP 566. PEP 566 is Final and replaces 345. The draft and withdrawal
   do not promote 426; the accepted successor is 566.
   Sources: [draft](https://github.com/python/peps/blob/8ae8b612d4ea8b3bf5d8a7b795ae8aec48bbb7a3/pep-0426.txt),
   [withdrawal](https://github.com/python/peps/blob/0977d33b02920d4619c024b64e35a693220cc3cf/pep-0426.txt),
   [PEP 566](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0566.rst).

3. **`manylinux-policy`** — pinned predecessor headers say `Status: Active`
   for PEPs 513 and 571 and `Status: Accepted` for PEP 599. PEP 600 says
   `Status: Final` and `Replaces: 513, 571, 599`.
   Sources: [PEP 513](https://github.com/python/peps/blob/9f3a93dc85318aa5adafc232ff50e8cc858cd642/pep-0513.txt),
   [PEP 571](https://github.com/python/peps/blob/d4a5364baf4e814c522079262df1535808da113a/pep-0571.rst),
   [PEP 599](https://github.com/python/peps/blob/4e7952166bbf3b9a13f0f5a4a8a77e1723b8eb20/pep-0599.rst),
   [PEP 600](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0600.rst).

## Reverts (3)

1. **`rust-str-as-str`** — merged PR 152963 says `Reverts
   rust-lang/rust#151603` and describes a clean revert. Open PR 152971 says
   `DO NOT MERGE` while attempting to re-stabilize for a crater run; it cannot
   displace the merged rollback.
   Sources: [original](https://github.com/rust-lang/rust/pull/151603),
   [revert](https://github.com/rust-lang/rust/pull/152963),
   [open follow-up](https://github.com/rust-lang/rust/pull/152971).

2. **`kubernetes-delayed-preemption`** — merged PR 137662 says `Reverts
   #136254` because delayed preemption was dropped from the 1.36 work and the
   added complexity was no longer necessary.
   Sources: [original](https://github.com/kubernetes/kubernetes/pull/136254),
   [revert](https://github.com/kubernetes/kubernetes/pull/137662).

3. **`elastic-multi-value`** — merged PR 147360 says `Reverts #147071 to
   unblock CI after test failures.`
   Sources: [original](https://github.com/elastic/elasticsearch/pull/147071),
   [revert](https://github.com/elastic/elasticsearch/pull/147360).

## Proposal is not authority (3)

1. **`packaging-governance`** — PEP 609 is Active. PEP 772 at
   `e95aa6726cfcbb871f3d9a1faccee6107032d3ed` and again at
   `850f4f7050ee65e29dd4a949a4c51b495c0c53c9` says `Status: Draft` and
   `Replaces: 609`. Only commit `7cab606014267c8011d4ccbb8381fb2d56629d60`
   changes it to `Status: Accepted` with a 16-Apr-2026 resolution.
   Sources: [first draft](https://github.com/python/peps/blob/e95aa6726cfcbb871f3d9a1faccee6107032d3ed/peps/pep-0772.rst),
   [later draft](https://github.com/python/peps/blob/850f4f7050ee65e29dd4a949a4c51b495c0c53c9/peps/pep-0772.rst),
   [accepted](https://github.com/python/peps/blob/7cab606014267c8011d4ccbb8381fb2d56629d60/peps/pep-0772.rst).

2. **`metadata-redesign`** — PEP 426 explicitly says `Status: Draft` at the
   proposal checkpoint and later `Status: Withdrawn`; PEP 345 remains the
   governing accepted record until PEP 566.

3. **`rust-str-as-str`** — PR 152971 is Open and titled `DO NOT MERGE`; its
   text cannot restore the stabilization that PR 152963 reverted.

## Parallel authority scopes (2)

1. **`annotation-semantics`** — PEP 649 is Final and replaces PEP 563 for
   annotation-evaluation policy. PEP 749 is Final, titled `Implementing PEP
   649`, and says `Requires: 649`; it is an implementation companion, not a
   replacement of policy PEP 649. Sources: [PEP 649](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0649.rst),
   [PEP 749](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0749.rst).

2. **`pypi-mirror-split`** — PEP 449 and PEP 464 are both Final and both
   replace withdrawn PEP 381, but their titles establish different scopes:
   mirror auto-discovery/naming versus the mirror authenticity API. A broad
   request for one undifferentiated mirror decision is therefore unresolved;
   each narrow scope has its own answer. Sources: [PEP 449](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0449.rst),
   [PEP 464](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0464.rst).

## Excluded during source audit

PEPs 354, 431, and 433 were considered and rejected as predecessor cases.
Pinned headers showed `Rejected`, `Withdrawn`, and `Draft`, respectively. They
cannot ground a “formerly governing” checkpoint merely because today's index
describes them as superseded.
