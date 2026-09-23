# Knowledge sources

| Adapter | Authoritative input | Revision | Implemented operations |
| --- | --- | --- | --- |
| GitKnowledgeSource | configured local Git clone and branch | pinned commit | list/read/changes/health/metadata |
| CuratedLocalSource | reviewed local documents with official attribution | bounded content digest | list/read/changes/health/metadata |
| LocalIncidentSource | local JSON rows plus declarative mapping | bounded content digest | document operations plus schema inspection |

Git reads committed blobs only. Uncommitted work is not ingested. Branch, optional
subpath and include prefixes are configuration, not query arguments. Remote HTTPS
repository URLs are supported as configuration metadata; clone/fetch/authentication
are intentionally unimplemented. The executable is the installed Git CLI; no Git
Python dependency is introduced. Git global/system credential configuration is not
used, command stderr is discarded and no credential helper is invoked by these reads.

Official sources require product/version and a configured allowlisted HTTPS URL.
The URL is attribution, never fetched. Categories are INTERNAL_KNOWLEDGE,
OFFICIAL_DOCUMENTATION, HISTORICAL_INCIDENT, RUNBOOK, ARCHITECTURE, KNOWN_ERROR,
CMDB and OTHER_EXTERNAL_SOURCE. Runbook/architecture/known-error directories can
provide conservative category metadata. Environment is never inferred from a name.

IncidentMappingEngine maps configured columns into the existing canonical Incident.
Use historical_root_cause and historical_remediation for historical descriptions.
Mappings accept table/column identifiers, not SQL or executable expressions.
Unmapped personal fields are discarded, selected text is sanitized, and source
provenance/environment cannot be overwritten by row data. SchemaDescription exposes
declared column names only, not row values. PostgreSQL/Oracle/SQL Server/MySQL and
ITSM connectors are future implementations of this boundary, not live connections.

Health states: NOT_INDEXED before explicit refresh, HEALTHY after successful refresh,
STALE when source revision differs, DEGRADED after failed refresh with readable source,
UNAVAILABLE when source revision cannot be read. No background polling exists.

Examples: [Git](../../config/knowledge/local-git.example.yaml),
[official](../../config/knowledge/official-docs.example.yaml),
[incident](../../config/knowledge/incident-source.example.yaml).
