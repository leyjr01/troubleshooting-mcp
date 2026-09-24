"""Refresh correlation with original runtime evidence plus typed probe observations."""

from agt_mcp.core.execution import ExecutionContext
from agt_mcp.correlation.models import (
    CorrelationResult,
    CorrelationSnapshot,
    EvidenceAtom,
    SignalCode,
)
from agt_mcp.probes.models import ProbeEvidence, ProbeStatus, ProbeType
from agt_mcp.troubleshooting.engine import TroubleshootingEngine
from agt_mcp.troubleshooting.models import TroubleshootingResult


async def reevaluate(
    engine: TroubleshootingEngine,
    original: CorrelationResult,
    probes: tuple[ProbeEvidence, ...],
    context: ExecutionContext,
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
                    signals=state.signals if state else (),
                )
            )
    for probe in probes:
        probe = ProbeEvidence.model_validate(probe.model_dump())
        result = probe.result
        signals: tuple[SignalCode, ...] = ()
        if result.status in {ProbeStatus.PASS, ProbeStatus.FAILED}:
            if result.probe_type == ProbeType.TLS:
                if result.observation.certificate_verified is False:
                    signals = (SignalCode.PROBE_TLS_FAILED,)
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
                signals=signals,
            )
        )
    snapshot = CorrelationSnapshot(
        environment_id=original.context.environment_id,
        observed_at=original.context.correlated_at,
        topology=original.topology_context,
        evidence=tuple(atoms),
        components=original.component_context,
        links=original.semantic_links,
        warnings=original.warnings,
        installation_id=original.installation_id,
        gateway_type=original.gateway_type,
        version=original.version,
        coverage=original.coverage,
    )
    query = original.context.request.model_copy(
        update={"time_window": None, "include_knowledge": False, "include_history": False}
    )
    refreshed = await engine.correlation.correlate(query, context, snapshot=snapshot)
    return engine.evaluate(refreshed, context)
