# Compatibility and support status

`tested` means observed in automated validation; `supported` is the bounded v1
contract; `expected compatible` is an inference, not certification; `not qualified`
means no real execution. STABLE below always carries its stated test boundary.

| Component | Version / scope | Test evidence | Support/maturity |
|---|---|---|---|
| Python | 3.12.10 Windows | full suite and packaging | STABLE, supported tested runtime |
| Python | >=3.12 metadata range, other versions | not executed | expected compatible, NOT QUALIFIED |
| FastMCP | 4.0.5 | actual in-process, STDIO and loopback HTTP | STABLE |
| Kubernetes Python client | 36.0.3 | real SDK with simulated API responses | STABLE SDK boundary |
| Kubernetes clusters | enabled allowlisted APIs; no certified server version | fixtures only | BETA deployment, real NOT QUALIFIED |
| OpenShift | Route/APIManager APIs, restricted SCC design | fixtures/manifests only | BETA deployment, real NOT QUALIFIED |
| 3scale | primary semantic profile 2.16 | classification/diagnosis fixtures | STABLE by fixtures; real NOT QUALIFIED |
| Other 3scale versions | limited metadata/unknown-version warnings | negative fixtures | NOT QUALIFIED |
| Prometheus-compatible metrics | configured health/instant/range GET protocol | bounded fake responses | STABLE protocol-level; live NOT QUALIFIED |
| Linux container | digest-selected Python 3.12 slim | static definition/security tests | expected compatible; NOT QUALIFIED |
| Virtual Trace / hypothesis engine | canonical v1 contracts | 35 scenarios, six golden | STABLE observed-condition contracts |
| Active probes | DNS/TCP/TLS/HTTP(S), operator-approved targets | fake/local transport tests | BETA operational capability |
| Local knowledge retrieval | committed Git, curated files, lexical index | security/ACL fixtures | EXPERIMENTAL production suitability |
| Logs/distributed traces | in-memory providers | fixtures | NOT QUALIFIED for live providers |

No tested cluster version is inferred from SDK version. No platform compatibility
claim upgrades fixture evidence to live qualification. Unknown 3scale versions
retain explicit limitations. Redis/database protocol diagnosis is not supported.
