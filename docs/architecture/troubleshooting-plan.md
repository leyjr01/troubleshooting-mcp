# Troubleshooting plans

TroubleshootingPlanner turns missing EvidenceRequirements into ordered, deduplicated
inspection descriptions. When requirements are satisfied, optional recent-event
inspection can strengthen context. Steps carry target, purpose, required capability,
expected evidence, related hypothesis IDs, safety class and status.

READ_ONLY_INSPECTION steps are PLANNED. Future PASSIVE_PROBE requirements are
CAPABILITY_UNAVAILABLE. Every generated step has executable=false and the plan has
executed=false. No plan executor or probe endpoint exists in Sprint 6. The enum reserves
ACTIVE_PROBE and WRITE_OPERATION for schema vocabulary; the engine generates neither.

Examples include inspecting Service/EndpointSlice readiness, declared routing target
and inventory, container waiting state, PVC binding and recent related events.
Unverified external dependencies report REDIS_CONNECTIVITY_NOT_AVAILABLE or
DATABASE_CONNECTIVITY_NOT_AVAILABLE. A reference is not a live connection test.

Ordering prioritizes currently available read-only inspections, then future probes;
target and stable IDs break ties. The count is bounded and plan_truncated warns when
necessary. Steps never contain a command obtained from a runbook, event or user symptom.
Knowledge remains attributed reference material, not a source of executable instructions.

Sprint 7 — Virtual Trace & Active/Passive Probe Foundation — may obtain currently
missing DNS/TCP/TLS/HTTP/dependency connectivity evidence under separate governance.
Nothing in a Sprint 6 plan authorizes or executes such a probe or remediation.
