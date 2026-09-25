"""Refresh correlation with original runtime evidence plus typed probe observations."""

from datetime import datetime

from agt_mcp.core.execution import ExecutionContext
from agt_mcp.correlation.models import (
    CorrelationResult,
    CorrelationSnapshot,
    EvidenceAtom,
    SignalCode,
    TimeWindow,
)
from agt_mcp.probes.models import ProbeEvidence, ProbeStatus, ProbeType
from agt_mcp.troubleshooting.engine import TroubleshootingEngine
from agt_mcp.troubleshooting.models import TroubleshootingResult


async def reevaluate(
    engine: TroubleshootingEngine,
    original: CorrelationResult,
    probes: tuple[ProbeEvidence, ...],
    context: ExecutionContext,
    *,
    additional: tuple[EvidenceAtom, ...] = (),
    time_window: TimeWindow | None = None,
    resource_scope: frozenset[str] | None = None,
) -> TroubleshootingResult:
    atoms = []
    states = {s.evidence_id: s for s in original.observed_states}
    timeline = {t.evidence_id: t for t in original.timeline}
    for group in original.evidence_sets:
        for evidence in group.evidence:
            state = states.get(evidence.id)
            atoms.append(
                EvidenceAtom(
                    evidence=evidence,
                    occurred_at=timeline[evidence.id].timestamp,
                    origin=state.origin if state else "runtime",
                    state=state.state if state else "unknown",
                    kind=timeline[evidence.id].event_type,
                    signals=state.signals if state else (),
                )
            )
    for probe in probes:
        probe = ProbeEvidence.model_validate(probe.model_dump())
        result = probe.result
        signals: tuple[SignalCode, ...] = ()
        if result.status in {ProbeStatus.PASS, ProbeStatus.FAILED}:
            if result.probe_type == ProbeType.DNS:
                if result.status == ProbeStatus.PASS and result.observation.addresses:
                    signals = (SignalCode.PROBE_DNS_RESOLVED,)
                elif result.status == ProbeStatus.FAILED and result.error_category in {
                    "DNS_RESOLUTION_FAILED",
                    "DNS_TIMEOUT",
                }:
                    signals = (SignalCode.PROBE_DNS_FAILED,)
            if result.probe_type in {ProbeType.HTTP, ProbeType.HTTPS}:
                status = result.observation.http_status
                if result.status == ProbeStatus.PASS and status is not None:
                    signals = (
                        SignalCode.PROBE_HTTP_RESPONSE,
                        SignalCode.PROBE_HTTP_SERVER_ERROR
                        if status >= 500
                        else SignalCode.PROBE_HTTP_NON_SERVER_ERROR,
                    )
                elif (
                    result.status == ProbeStatus.FAILED and result.error_category == "HTTP_TIMEOUT"
                ):
                    signals = (SignalCode.PROBE_HTTP_TIMEOUT,)
            if result.probe_type == ProbeType.TLS:
                if result.observation.certificate_verified is False:
                    signals = (SignalCode.PROBE_TLS_FAILED,)
                    if result.observation.chain_verified is False:
                        signals += (SignalCode.PROBE_TLS_CHAIN_FAILED,)
                    if result.observation.valid_until:
                        try:
                            expiry = datetime.fromisoformat(result.observation.valid_until)
                            if expiry.tzinfo is not None and expiry < result.timestamp:
                                signals += (SignalCode.PROBE_TLS_EXPIRED,)
                        except ValueError:
                            pass  # Unparseable dates cannot establish certificate expiry.
                elif result.observation.certificate_verified is True:
                    signals = (SignalCode.PROBE_TLS_VERIFIED,)
            if result.probe_type == ProbeType.TCP:
                signals = (
                    SignalCode.PROBE_TCP_CONNECTED
                    if result.status == ProbeStatus.PASS
                    else SignalCode.PROBE_TCP_FAILED,
                )
        # Unknown state prevents network failure being misread as workload unavailability.
        atoms.append(
            EvidenceAtom(
                evidence=probe.evidence,
                occurred_at=result.timestamp,
                origin="network-probe",
                kind="probe",
                signals=signals,
            )
        )
    snapshot = CorrelationSnapshot(
        environment_id=original.context.environment_id,
        observed_at=original.context.correlated_at,
        topology=original.topology_context,
        evidence=tuple(
            a
            for a in (*atoms, *additional)
            if resource_scope is None or a.evidence.resource_id in resource_scope
        ),
        components=original.component_context,
        links=original.semantic_links,
        warnings=original.warnings,
        installation_id=original.installation_id,
        gateway_type=original.gateway_type,
        version=original.version,
        coverage=original.coverage,
    )
    query = original.context.request.model_copy(
        update={"time_window": time_window, "include_knowledge": False, "include_history": False}
    )
    refreshed = await engine.correlation.correlate(query, context, snapshot=snapshot)
    return engine.evaluate(refreshed, context)
