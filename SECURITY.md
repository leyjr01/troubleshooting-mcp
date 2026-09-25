# Security policy — v1.0.0

Supported security-contract line: 1.x with the qualification limits in
[release notes](docs/release/v1.0.0.md). No production certification is claimed.
READ, DIAGNOSE, RECOMMEND only: no apply/delete/patch/restart, database writes,
Secret discovery or remediation. Derived caches/indexes may change. Opt-in probes
are active network observations: read-only does not mean passive networking.

Authorization defaults deny access, with principal/environment/source permissions.
STDIO/local HTTP trust the OS user. Remote HTTP requires a configured bearer and
exact Hosts, operator-managed TLS termination and network restrictions. Shared
reader credentials are not production SSO. Kubernetes grants only explicit get/list,
never Secret access or wildcards. Recommendations cannot execute changes.

No secrets in Git, examples, CLI arguments, responses or logs. Providers resolve
scoped credentials; the server may read its explicitly configured mounted token
without Secret API permission. External logs/docs are untrusted data, not executable
instructions. SSRF protections enforce approved endpoints, DNS/CIDRs and verified
TLS. Errors expose categories, not traceback, paths or raw messages.

Limits/redaction do not guarantee production DDoS resistance or perfect secret
recognition. Operator configuration is privileged. SSO/OIDC, HA, public multi-tenant
access, automatic remediation and live OpenShift/3scale certification are excluded.
Current CVE status is not certified. See [review](docs/release/security-review.md)
and [threat model](docs/security/threat-model.md).

Report vulnerabilities privately through a channel agreed with the maintainer.
Include affected version, sanitized reproduction, impact and safe IDs. Never post
credentials, kubeconfig or customer dumps. No public contact address or response
SLA has been established.
