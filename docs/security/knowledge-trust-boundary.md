# Knowledge trust boundary

All retrieved content is inert untrusted data, including official documentation.
The system does not execute a runbook command or follow a document's instructions.
Source labels indicate origin, not permission to override policy. Similarity is not
diagnostic confidence and historical cause text is not proof of a current cause.

[ADR-0016](../adr/0016-knowledge-security-trust-boundary.md) defines the policy.
Sanitization occurs before hashing/indexing/embedding. Raw source bytes exist only
inside the bounded ingestion call; manifests/chunks store sanitized representations.
Git commit IDs and local source revision digests identify source revisions; document
checksums use sanitized normalized text and effective metadata. Rotating a redacted
secret alone need not change an indexed document checksum.

Never put credentials in source URLs. Enabled credential-dependent integrations are
rejected; future authenticated adapters must use the existing CredentialProvider.
No live web fetch means queries cannot reach localhost, metadata services or arbitrary
URLs. No Secret content, Git token, SSH key or database credentials are required.
Audit logs contain operation identity/status, not query text or document excerpts.

Global source scope is an explicit administrator choice. Global sources can contain
documents narrowed to PROD; DEV retrieval excludes those before scoring and again
at the retriever boundary. A DEV-only source cannot broaden itself with front matter.
Source inventories never reveal local filesystem paths or credential references.

Redaction uses patterns and may over-redact useful opaque identifiers. It cannot
guarantee detection of every credential format or personal name. Review and minimize
input data. Local filesystem snapshots assume trusted administrative configuration;
they are bounded but not transactionally protected against concurrent file changes.

Tests cover malformed YAML, credential/private-key/connection-string removal,
inert malicious instructions, source/category authorization, environment isolation,
oversized input and failed-refresh preservation. There is no automatic remediation.
