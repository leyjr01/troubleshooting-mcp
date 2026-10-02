# ADR-0014 — Red Hat 3scale Semantic Discovery

## Status

APPROVED — Sprint 3, 2026-09-23; implementation of the authorized sprint scope.

## Context

Sprint 2 discovers infrastructure but cannot identify product roles from its
generic resource kinds. Red Hat 3scale 2.16 also requires a representation of
externally managed databases that does not depend on internal Deployments.

## Decision

Implement ThreeScaleGatewayAdapter over the canonical RuntimeAdapter. Retain
GatewayAdapter compatibility and explicitly reject unimplemented Admin API,
policy, log and request-trace operations. Product models, classifier and profiles
live under gateways/threescale; no Kubernetes SDK, FastMCP, shell or independent
network client is imported there. Bootstrap owns runtime lifecycle.

Project a fixed allowlist of labels and APIManager booleans inside the Kubernetes
adapter. Raw CRs never cross this boundary. This is a narrow evolution of ADR-0012:
arbitrary custom specs remain withheld, while APIManager externalComponents and
zync.enabled can reach semantic classification as safe hints. Workload template
references are collected even when no Pod is currently present.

Evidence precedence is APIManager declaration, UID ownership, managed metadata,
component labels, runtime relationships, configuration references, then exact
documented names. Names alone never establish membership. Strong ownership plus
component metadata supports HIGH; labels alone remain MEDIUM candidates with
ambiguity warnings. Unsupported roles remain UNKNOWN. No classification is a
diagnosis. Every classification and semantic edge has provenance and qualitative
confidence. A single snapshot is reused across all components of an operation.

Profiles distinguish observed version from configured expectations. Primary
profile 2.16 marks System database, Backend Redis storage/queues and System Redis
as external expectations; explicit APIManager flags take precedence and conflicts
are reported. Zync enablement and database externalization are separate controls.
Unknown or unsupported versions continue with limited expectations and warnings.
Profile sources and verification dates are stored with the rules.

Secret references can identify documented connection roles, never hosts, ports,
users or values. External endpoints remain unresolved. The APIManager namespace is
the installation's primary namespace, while the runtime namespace allowlist bounds
the complete discovery snapshot. APIcast workloads in another authorized namespace
may join the installation through product/component labels and runtime relationships
when exactly one APIManager makes that association unambiguous. UID ownership remains
authoritative; resources owned by another APIManager are excluded. With multiple
APIManagers, unowned cross-namespace APIcast labels are not assigned automatically.
Presence distinguishes PRESENT, ABSENT_EXPECTED, ABSENT_OPTIONAL, EXTERNAL,
DISABLED and UNKNOWN. Incomplete reads cannot prove an expected component absent.

## Consequences

discover_gateway retains the memory-adapter path and gains automatic scoped
installation discovery. Three opt-in tools expose topology, component inspection
and dependencies with internal authorization and existing runtime bounds.
APIManager requires an explicit custom-resource allowlist and get/list Role.
There are no Secret grants, probes, Admin Portal connections or deployment manifests.
Operator metadata indicates management observations, not operator process health.

## Alternatives Considered

- SDK access from the gateway adapter: rejected; duplicates the runtime boundary.
- Names-only detection: rejected; false positives and installation mixing.
- Guessing Redis/database endpoints: rejected; values are unavailable by policy.
- Applying 2.16 rules to every installation: rejected; unsafe historical assumptions.

See [discovery and sources](../architecture/threescale-discovery.md),
[semantic topology](../architecture/threescale-semantic-topology.md) and
[data access](../security/threescale-data-access.md).
