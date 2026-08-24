# Dependency and version audit

Installed environment on 2026-08-24:

- Python 3.12.13
- google-cloud-firestore 2.28.1
- google-api-core 2.34.0
- grpcio 1.83.0
- cryptography is constrained to >=44,<51
- google-adk is constrained to >=2.6.3,<3 in requirements.txt
- google-cloud-aiplatform[agent-engines] is pinned to 1.163.0
- fastmcp is pinned to 2.13.1
- OpenTelemetry packages are constrained to ADK-compatible <=1.42.1

The repository has no duplicate active requirement line after inspection. The
pyproject.toml optional ADK extra now carries the same upper bound as deployment
requirements. This was a packaging consistency repair, not a B7 semantic
change. No major dependency upgrade is authorized by this audit.
Version-sensitive Firestore behavior is pinned by the SDK-contract document and
tested through the real adapter path.

No hardcoded private key or customer data was found in production B7 modules.
Test project identifiers occur only in explicitly named live/probe fixtures and
are not customer-production identifiers.
