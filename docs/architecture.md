# Architecture

Two diagrams. The first is what the system is made of. The second is the path a
single piece of content takes, and every place that path can be stopped.

Committed as Mermaid source rather than an image, so it stays correct when the
design moves and renders on GitHub with no toolchain.

## What it is made of

```mermaid
flowchart TB
    subgraph fleet["The governed population"]
        A1["sales agent"]
        A2["support agent"]
        A3["finance agent"]
    end

    subgraph custody["Custody"]
        direction TB
        REV["revision.py<br/>pin live MCP tool revisions<br/>block drift before dispatch"]
        ORIGIN["origin.py<br/>label by structure<br/>USER · MODEL · TOOL · DERIVED"]
        SPLIT["service.py<br/>split before the write"]
        GRAPH["graph.py<br/>derivation graph<br/>descendants · revoke"]
        CAT["catalog.py<br/>per-department grants"]
        GATE["action.py<br/>export must cite trusted memory"]
    end

    subgraph google["Google Cloud"]
        MB[("Memory Bank<br/>via BaseMemoryService")]
        FS[("Firestore<br/>graph · quarantine · audit")]
        GEM["Gemini via Vertex<br/>explains a quarantine<br/>never labels one"]
    end

    QUAR[["quarantine<br/>withheld, reviewable"]]

    A1 & A2 & A3 -->|"discover and bind tools"| REV
    REV -->|"admitted session events"| ORIGIN
    ORIGIN --> SPLIT
    CAT -->|"which tools this<br/>department vouched for"| SPLIT
    SPLIT -->|"trusted only"| MB
    SPLIT -->|"untrusted"| QUAR
    SPLIT -->|"records"| GRAPH
    GRAPH --> FS
    QUAR --> GEM
    GRAPH -->|"revocation"| MB
    MB -->|"retrieval"| A1 & A2 & A3
    A1 -->|"export request"| GATE

    classDef built fill:#1f6f3f,stroke:#0d3d22,color:#fff
    class REV,ORIGIN,SPLIT,GRAPH,CAT,GATE,QUAR,MB,GEM,FS built
```

Green is built and evidenced. Every node above is green: Firestore was the
last amber one, and it is live behind the same ports as the offline SQLite
store (`custody/firestore_store.py`, `custody/nonce_ledger.py`), carrying
the derivation graph, the demotion log, the approved revision pins, and the
dispatch nonce ledger. See `README.md`'s status table for the command that
demonstrates each.

## The live Gateway enforcement slice

```mermaid
sequenceDiagram
    participant P as proof producer
    participant I as IAP policy
    participant R as Agent Runtime<br/>Agent Identity
    participant G as Agent Gateway
    participant C as Agent Registry
    participant M as owned MCP on Cloud Run

    P->>I: allow exact principal + lookup_customer
    P->>R: query with W3C trace A
    R->>G: MCP tools/call lookup_customer
    G->>C: resolve registered server and tool
    G->>I: evaluate roles/iap.egressor condition
    I-->>G: ALLOWED
    G->>M: dispatch
    M-->>P: ledger count +1

    P->>I: replace with handshake/non-tool passthrough<br/>and no registered tool
    P->>R: query with W3C trace B
    R->>G: MCP tools/call lookup_customer
    G->>I: evaluate roles/iap.egressor condition
    I-->>G: DENIED
    G-->>R: 403 before dispatch
    M-->>P: ledger unchanged
    P->>I: read Admin Activity etag chain
    P->>G: reread exact trace + insert IDs
```

This slice proves one owned Runtime-to-Gateway-to-MCP route. The Registry still
contains the stale v1 surface while Cloud Run serves v2; Gateway IAP authorizes
the registered tool name, not a revision digest. It therefore strengthens the
execution boundary without closing Custody's allowed-call surface-read to
dispatch TOCTOU window. The empty-name condition passes MCP handshake/non-tool
requests; the demonstrated enforcement claim is specifically registered
`tools/call` admission, not universal request classification.

## The path one piece of content takes

Every branch below is a place the content can be stopped, and each is a test.

```mermaid
flowchart TD
    START(["an agent discovers a tool"]) --> PIN{"does its live definition<br/>match the approved revision?"}
    PIN -->|no| BLOCK["refused before dispatch"]
    PIN -->|yes| TOOL_CALL(["a tool returns text"])
    TOOL_CALL --> STRUCT{"is it inside a<br/>function_response?"}

    STRUCT -->|yes| TOOL["origin = TOOL"]
    STRUCT -->|"no, and author is 'user'"| USER["origin = USER"]
    STRUCT -->|"no, and an untrusted tool<br/>already answered in<br/>this invocation"| DERIV["origin = DERIVED<br/>inherits the distrust"]
    STRUCT -->|"no, clean invocation"| MODEL["origin = MODEL"]

    TOOL --> VOUCH{"was this exact tool revision<br/>approved for the department?"}
    VOUCH -->|no| UNTRUSTED
    VOUCH -->|yes| TRUSTED

    DERIV --> UNTRUSTED["trust = UNTRUSTED"]
    USER --> TRUSTED["trust = TRUSTED"]
    MODEL --> TRUSTED

    UNTRUSTED --> HELD[["withheld from memory<br/>held in quarantine"]]
    TRUSTED --> ATTR{"can it be attributed?<br/>invocation and author present"}
    ATTR -->|no| REFUSED[["refused<br/>never stored as trusted"]]
    ATTR -->|yes| WRITE["written to Memory Bank<br/>record added to the graph"]

    WRITE --> LATER{"is the source tool revision<br/>demoted later?"}
    LATER -->|yes| REVOKE[["revoked<br/>with every descendant"]]
    LATER -->|no| RETRIEVE["retrievable"]

    RETRIEVE --> EXPORT{"an export cites it"}
    EXPORT -->|"citation untrusted<br/>or absent"| DENY[["egress refused"]]
    EXPORT -->|"every citation<br/>instruction-eligible"| SEND(["egress allowed"])

    classDef stop fill:#7a2020,stroke:#3d0f0f,color:#fff
    classDef ok fill:#1f6f3f,stroke:#0d3d22,color:#fff
    class BLOCK,HELD,REFUSED,REVOKE,DENY stop
    class SEND,RETRIEVE ok
```

## The two rules worth knowing

**Taint crosses events, inside an invocation.** A model turn following an
untrusted tool response is `DERIVED`. When an agent summarises a hostile page,
the summary is what survives into memory and the raw response is discarded, so
labelling only raw tool output would let the laundered copy through. Custody is
therefore taken over the whole session in one pass, never per event.

**Enforcement is at the write, not at retrieval.** Memory Bank derives memories
server-side, so a stored memory is not byte-identical to any event and cannot be
matched back to a custody record afterwards. A memory derived from mixed-trust
events has no single origin at all, because the derivation destroys the
provenance. Splitting before the write also means retrieval needs no filter,
which is fortunate: `search_memory(app_name, user_id, query)` does not offer one.
