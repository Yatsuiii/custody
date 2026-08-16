# DecisionTrace v0 falsifier results

n = 37 decisions across 4 repos.

| Condition | Citation-correct | Rationale-match | Combined (both) | Hallucination rate | Supersession-aware |
|---|---|---|---|---|---|
| code_only | 14% (5/37) | 16% (6/37) | 3% | 8% | 28% (5/18) |
| rag | 76% (28/37) | 62% (23/37) | 57% | 3% | 94% (17/18) |
| structured | 100% (37/37) | 100% (37/37) | 100% | 3% | 100% (18/18) |

## Per-decision detail

| decision_id | repo | code_only | rag | structured |
|---|---|---|---|---|
| rust-lang-rust-revert-149375 | rust-lang/rust | cR | CR | CR |
| rust-lang-rust-revert-148937 | rust-lang/rust | cr | CR | CR |
| rust-lang-rust-revert-149060 | rust-lang/rust | cr | CR | CR |
| rust-lang-rust-revert-149516 | rust-lang/rust | cr | CR | CR |
| rust-lang-rust-revert-142034 | rust-lang/rust | cR | CR | CR |
| kubernetes-kubernetes-revert-140448 | kubernetes/kubernetes | cr | CR | CR |
| kubernetes-kubernetes-revert-306 | kubernetes/kubernetes | cr | cr | CR |
| kubernetes-kubernetes-revert-136254 | kubernetes/kubernetes | cr | CR | CR |
| kubernetes-kubernetes-revert-126794 | kubernetes/kubernetes | cr | CR | CR |
| kubernetes-kubernetes-revert-127300 | kubernetes/kubernetes | cr | CR | CR |
| elastic-elasticsearch-revert-154503 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-152050 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-151875 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-120214 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-147071 | elastic/elasticsearch | cr | CR | CR |
| kep-keps-sig-storage-1979-object-storage-support | kubernetes/enhancements | CR | cR | CR |
| kep-keps-sig-auth-1205-bound-service-account-tokens | kubernetes/enhancements | Cr | cr | CRH |
| kep-keps-sig-auth-2718-20210511-client-exec-proxy | kubernetes/enhancements | cr | CR | CR |
| kep-keps-sig-cloud-provider-2133-out-of-tree-credential-provider | kubernetes/enhancements | cr | CR | CR |
| kep-keps-sig-api-machinery-2332-pruning-for-custom-resources | kubernetes/enhancements | cRH | cr | CR |
| rust-lang-rust-revert-144407 | rust-lang/rust | cr | CR | CR |
| kubernetes-kubernetes-revert-129701 | kubernetes/kubernetes | cR | CR | CR |
| kubernetes-kubernetes-revert-126599 | kubernetes/kubernetes | cr | CR | CR |
| kep-keps-sig-auth-279-limit-node-access | kubernetes/enhancements | cr | cR | CR |
| kep-keps-sig-storage-2451-service-account-token-volumes | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-cli-2382-kustomize-exec-secret-generator | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-instrumentation-647-apiserver-tracing | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-storage-1790-recover-resize-failure | kubernetes/enhancements | Cr | cr | CR |
| kep-keps-sig-auth-5681-conditional-authorization | kubernetes/enhancements | cr | CR | CR |
| kep-keps-sig-api-machinery-3488-cel-admission-control | kubernetes/enhancements | cr | cr | CR |
| kep-keps-sig-api-machinery-2523-consistent-resource-versions-semantics | kubernetes/enhancements | crH | cr | CR |
| kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay | kubernetes/enhancements | Cr | crH | CR |
| kep-keps-sig-scheduling-5501-reflect-preenqueue-rejections-in-pod-status | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-api-machinery-2885-server-side-unknown-field-validation | kubernetes/enhancements | cR | Cr | CR |
| kep-keps-sig-api-machinery-2876-crd-validation-expression-language | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-scheduling-5229-asynchronous-api-calls-during-scheduling | kubernetes/enhancements | Cr | CR | CR |
| kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure | kubernetes/enhancements | crH | Cr | CR |

(Capital = correct/true, lowercase = incorrect/false, H = hallucinated a wrong citation.)


## Verdict: GO

RAG reached only 57% (<=70%) while structured memory reached 100% (>=85%). Structured decision memory materially beats naive RAG. Build DecisionTrace.
