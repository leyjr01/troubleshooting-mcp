# v1 security and dependency review

Development review of source, config, deployment and negative suites; not a pentest
or live certification. No approved architectural decision was reopened.

| Boundary | Status | Control / remaining limit |
|---|---|---|
| Secret handling | mitigated | scoped providers, safe errors, projection/redaction; no Secret API grants |
| SSRF | mitigated | approved bindings/CIDRs, DNS pinning, TLS, redirect/proxy restrictions |
| Prompt injection | mitigated | external content is data; no content-driven tool execution |
| RBAC/source writes | mitigated | explicit get/list, no wildcard; 38 read-only tools |
| Authorization/isolation | mitigated | deny-all defaults, principal/environment permissions, scoped caches |
| Path traversal | mitigated | bounded approved Git/file readers, negative tests; config is privileged |
| Command injection | mitigated | no tool-driven shell; local Git uses fixed argv and deadline |
| SQL/query injection | out of scope / bounded | no live database adapter; typed queries, no raw PromQL input |
| Errors/logs | mitigated | safe categories/IDs, principal and hashed resource/query reference |
| HTTP exposure | mitigated | remote bearer, Host/Origin policy; operator TLS/network protection required |
| Container | mitigated by definition | non-root, arbitrary UID design, read-only root, drop ALL; live unqualified |
| Resource exhaustion | mitigated | byte/count/depth/deadline bounds; not a DDoS benchmark |
| Shared reader token | accepted | no per-human attribution; SSO future work |
| Ephemeral caches/indexes | accepted | bounded/rebuildable; no HA/durable database |
| Remediation | out of scope | no source-write tool or executable recommendation |

## Secret scan

Reviewed Bearer/password/token/client_secret/private-key/AWS-key/connection-string
patterns across release files. Config/deploy contain references/mounts, not secret
values; examples use reserved domains and generic paths. Source matches are
validation/redaction/authentication code. Tests intentionally contain fake tokens,
passwords, Secret payloads and malicious URLs to assert non-disclosure. The container
test generates an ephemeral token. These are intentional fixtures, not real credentials.
No real credential identified. This pattern review is not proof that every possible
secret format is absent; sanitized output remains untrusted.

## Dependencies and licenses

Direct requirements remain pydantic>=2.10,<3, PyYAML>=6,<7, fastmcp==4.0.5 and
kubernetes==36.0.3. All are used; no broad upgrades. Runtime wheel excludes dev extras.
Windows lock plus Linux-only constraints pin resolution; base image requires digest.
Builder setuptools/wheel are pinned build tools, not runtime project requirements.
The base Python image may contain its own installer tooling.

[Inventory](dependency-inventory.json) records the installed runtime closure and
license metadata (87 entries, including selected dependency extras) using available
libraries, not a standards-certified SBOM.
UNKNOWN license metadata and the project's unspecified redistribution license need
maintainer review before public distribution; no license or repository URL is invented.
Bandit checks source and pip check checks dependency consistency. They do not query
CVE databases: current dependency vulnerabilities are **not assessed**, not "none".
No dedicated vulnerability scanner was already supplied; no new scanning stack added.

Two narrow B104 exceptions document authenticated 0.0.0.0 and its guard; the existing
YAML exception covers a restricted SafeLoader. No global security check or coverage
gate was disabled. Live qualification, CVE monitoring and public distribution
approval remain explicit release-owner responsibilities.
