"""Approved configuration supplies endpoints; trace membership supplies scope."""

from datetime import datetime
from hashlib import sha256

from agt_mcp.core.models import Provenance
from agt_mcp.correlation.rules import identity
from agt_mcp.probes.models import (
    CAPABILITIES,
    Endpoint,
    ProbeCapability,
    ProbePlan,
    ProbeRequest,
    ProbeTarget,
    ProbeType,
)
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.trace.models import VirtualTrace
from agt_mcp.troubleshooting.models import TroubleshootingResult


def target_from(endpoint: Endpoint, timestamp: datetime) -> ProbeTarget:
    return ProbeTarget(
        **endpoint.model_dump(),
        provenance=Provenance(
            source_id="approved-probe-endpoints",
            environment_id=endpoint.environment_id,
            retrieved_at=timestamp,
            source_reference=f"configuration/probes/endpoints/{endpoint.id}",
            content_sha256=sha256(endpoint.model_dump_json().encode()).hexdigest(),
        ),
    )


class ProbePlanner:
    def __init__(self, policy: ProbePolicy, capabilities: frozenset[ProbeCapability]) -> None:
        self.policy, self.capabilities = policy, capabilities

    def plan(
        self,
        trace: VirtualTrace,
        timestamp: datetime,
        diagnosis: TroubleshootingResult | None = None,
    ) -> ProbePlan:
        resolved = {h.reference for h in trace.hops if h.structural_status == "RESOLVED"}
        warnings = (
            {"target_unresolved"}
            if any(h.structural_status == "UNRESOLVED" for h in trace.hops)
            else set()
        )
        if diagnosis is not None:
            if (
                diagnosis.context.environment_id != trace.environment_id
                or diagnosis.correlation_result.id != trace.correlation_id
            ):
                raise ValueError("diagnostic context mismatch")
            missing_resources = {
                r
                for h in diagnosis.hypotheses
                if h.evaluation.missing_evidence
                for r in h.resources
            }
            resolved &= missing_resources
        requests = []
        if "routing_target_unresolved" in trace.warnings:
            resolved.clear()
            warnings.add("structural_path_incomplete")
        for endpoint in sorted(self.policy.config.endpoints, key=lambda e: e.id):
            if (
                endpoint.environment_id != trace.environment_id
                or endpoint.resource_id not in resolved
            ):
                continue
            target = target_from(endpoint, timestamp)
            kinds = [ProbeType.DNS, ProbeType.TCP]
            if target.protocol in {"tls", "https"}:
                kinds.append(ProbeType.TLS)
            if target.protocol in {"http", "https"}:
                kinds.append(ProbeType(target.protocol.upper()))
            for kind in kinds:
                timeout = self.policy.config.limits.timeout_seconds
                reason = self.policy.target(target, trace.environment_id, kind, timeout)
                if CAPABILITIES[kind] not in self.capabilities:
                    reason = "CAPABILITY_UNAVAILABLE"
                requests.append(
                    ProbeRequest(
                        id=identity("probe", trace.id, target.id, kind),
                        target=target,
                        probe_type=kind,
                        timeout_seconds=timeout,
                        allowed=reason == "ALLOWED",
                        reason=reason,
                        required_capability=CAPABILITIES[kind],
                    )
                )
        if not requests:
            warnings.add("target_unresolved")
        if len(requests) > self.policy.config.limits.max_probes_per_request:
            warnings.add("probe_plan_truncated")
        return ProbePlan(
            id=identity("probe-plan", trace.id, self.policy.config.model_dump_json()),
            trace_id=trace.id,
            environment_id=trace.environment_id,
            requests=tuple(requests[: self.policy.config.limits.max_probes_per_request]),
            warnings=tuple(sorted(warnings)),
        )
