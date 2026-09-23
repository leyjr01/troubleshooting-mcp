# ADR-0016 — Knowledge Security and Trust Boundary

## Status
APPROVED — Sprint 4, 2026-09-23.

## Context
Corporate repositories, official excerpts and incident rows can contain credentials,
personal information and prompt injection. Similarity cannot establish truth or cause.

## Decision
Mark all chunks untrusted_data. Documents never invoke tools, interpreters or network
clients. Apply a dedicated pre-index redactor to all text, mapped incident fields
and metadata boundaries; preserve the existing conservative runtime sanitizer.
Remove private key blocks, known credential assignments, authenticated URLs, bearer
tokens, common token formats, email addresses and long opaque mixed strings. Reject
unsafe provenance paths or metadata rather than rewriting ACL identities.

Parse YAML with the restricted SafeLoader, rejecting custom tags, duplicate keys,
anchors and aliases. Bound document bytes, front matter, document counts, chunk
sizes/counts, retrieval count and serialized result bytes. Reject an entire refresh
on invalid data instead of deleting valid old index entries after a partial scan.

Filter source authorization and environment before ranking; recheck at the retriever
boundary. A source configured for one environment cannot widen its scope through
front matter. Explicit global sources may hold narrower per-document scopes.
Path-derived metadata infers category only, not environment or causal severity.

Git executes only fixed read commands against configured local repositories, with
argument arrays, no shell, bounded output and deadlines. Never accept a repository
path or URL from MCP queries. Symlink blobs and local symlinks are rejected. Curated
URLs are metadata only: there is no HTTP path for SSRF. Credentials reuse the existing
CredentialReference model; enabled credential-dependent sources are unsupported in
this sprint rather than introducing another resolver or reading secrets implicitly.

## Consequences
Redaction is conservative pattern detection, not a guarantee of identifying every
possible secret or personal name. Reviewed input repositories remain necessary.
Unknown formats are excluded; malformed or oversized selected files fail closed.
Local filesystem snapshots are not atomic against concurrent administrative edits.
Similarity returns references and historical claims, not current root-cause findings.

## Alternatives Considered
Trusting corporate content as instructions breaks the security boundary. Applying
redaction only at output would leave secrets in embeddings and indexes. Live URL
fetching adds unnecessary SSRF and egress risks. Opaque runtime text withholding
would prevent useful knowledge retrieval, so its separate policy is preserved.
