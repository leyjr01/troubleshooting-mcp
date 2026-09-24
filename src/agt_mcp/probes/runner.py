"""Budgeted per-target chains with bounded concurrency and explicit cancellation audit."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic

from agt_mcp.core.execution import ExecutionContext
from agt_mcp.core.models import Confidence, Evidence, Provenance
from agt_mcp.correlation.rules import identity
from agt_mcp.probes.models import (
    CAPABILITIES,
    ProbeEvidence,
    ProbeObservation,
    ProbePlan,
    ProbeRequest,
    ProbeResult,
    ProbeStatus,
    ProbeType,
)
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.ports import ProbeExecutor, ProbeFailure


def as_evidence(result: ProbeResult) -> ProbeEvidence:
    kind = "http" if result.probe_type == ProbeType.HTTPS else result.probe_type.lower()
    source = Provenance(
        source_id="network-probe",
        environment_id=result.target.environment_id,
        retrieved_at=result.timestamp,
        source_reference=f"probe/{result.request_id}/{result.target.id}",
        content_sha256=sha256(result.model_dump_json().encode()).hexdigest(),
    )
    evidence = Evidence(
        id=identity("probe-evidence", result.model_dump_json()),
        environment_id=result.target.environment_id,
        timestamp=result.timestamp,
        source=source,
        type="observation",
        resource_id=result.target.resource_id,
        observation=f"probe.{kind} {result.status.value} {result.error_category or 'observed'}",
        raw_reference=source.source_reference,
        confidence=Confidence(
            level="low",
            rationale="Point-in-time network observation, not root cause",
            source_reliability="Controlled network executor",
            temporal_relevance="Timestamped probe",
            topological_relevance="Approved endpoint linked to scoped resource",
            historical_similarity="Not used",
        ),
        metadata={
            "probe_type": f"probe.{kind}",
            "target_id": result.target.id,
            "target_origin": result.target.derived_from,
            "duration_ms": str(result.duration_ms),
            "status": result.status.value,
        },
    )
    return ProbeEvidence(result=result, evidence=evidence)


class ProbeRunner:
    def __init__(self, policy: ProbePolicy, executor: ProbeExecutor) -> None:
        self.policy, self.executor = policy, executor
        self.logger = logging.getLogger("agt_mcp.audit")

    def audit(self, result: ProbeResult, context: ExecutionContext, decision: str) -> None:
        self.logger.info(
            json.dumps(
                {
                    "event": "probe_finished",
                    "request_id": context.request_id,
                    "correlation_id": context.correlation_id,
                    "environment_id": context.environment_id,
                    "probe_type": result.probe_type.value,
                    "target_id": result.target.id,
                    "target_origin": result.target.derived_from,
                    "duration_ms": result.duration_ms,
                    "status": result.status.value,
                    "policy_decision": decision,
                }
            )
        )

    async def execute(
        self, plan: ProbePlan, context: ExecutionContext
    ) -> tuple[ProbeEvidence, ...]:
        plan = ProbePlan.model_validate(plan.model_dump())
        if plan.environment_id != context.environment_id:
            raise ValueError("cross-environment plan")
        config = self.policy.config
        if len(plan.requests) > config.limits.max_probes_per_request:
            raise ValueError("probe limit exceeded")
        results: dict[str, ProbeResult] = {}
        semaphore = asyncio.Semaphore(config.limits.max_parallel_probes)

        async def chain(requests: list[ProbeRequest]) -> None:
            addresses: tuple[str, ...] = ()
            previous = True
            async with semaphore:
                for request in requests:
                    started = monotonic()
                    decision = self.policy.target(
                        request.target,
                        context.environment_id,
                        request.probe_type,
                        request.timeout_seconds,
                    )
                    category: str | None
                    status, category, observation = (
                        ProbeStatus.NOT_EXECUTED,
                        "UPSTREAM_NOT_SUCCESSFUL",
                        ProbeObservation(),
                    )
                    if not config.enabled or config.execution_mode != "execute_allowed":
                        decision = "EXECUTION_DISABLED"
                    if not request.allowed:
                        decision = (
                            request.reason
                            if request.reason != "ALLOWED"
                            else "TARGET_BLOCKED_BY_POLICY"
                        )
                    if CAPABILITIES[request.probe_type] not in self.executor.capabilities():
                        decision = "CAPABILITY_UNAVAILABLE"
                    if decision != "ALLOWED":
                        status, category = ProbeStatus.BLOCKED, decision
                    elif previous:
                        try:
                            async with asyncio.timeout(request.timeout_seconds):
                                observation = await self.executor.execute(request, addresses)
                            if request.probe_type == ProbeType.DNS:
                                if (
                                    self.policy.addresses(request.target, observation.addresses)
                                    != "ALLOWED"
                                ):
                                    raise ProbeFailure("TARGET_BLOCKED_BY_POLICY", blocked=True)
                                addresses = observation.addresses
                            status, category = ProbeStatus.PASS, None
                        except ProbeFailure as exc:
                            status = ProbeStatus.BLOCKED if exc.blocked else ProbeStatus.FAILED
                            category, observation = exc.category, exc.observation
                        except TimeoutError:
                            status = ProbeStatus.FAILED
                            category = (
                                "HTTP_TIMEOUT"
                                if request.probe_type in {ProbeType.HTTP, ProbeType.HTTPS}
                                else "DNS_TIMEOUT"
                                if request.probe_type == ProbeType.DNS
                                else "CONNECTION_TIMEOUT"
                            )
                        except asyncio.CancelledError:
                            result = ProbeResult(
                                request_id=request.id,
                                target=request.target,
                                probe_type=request.probe_type,
                                status=ProbeStatus.CANCELLED,
                                error_category="CANCELLED",
                                timestamp=datetime.now(UTC),
                                duration_ms=(monotonic() - started) * 1000,
                            )
                            results[request.id] = result
                            self.audit(result, context, decision)
                            raise
                        except Exception:
                            status, category = ProbeStatus.FAILED, "EXECUTOR_ERROR"
                    result = ProbeResult(
                        request_id=request.id,
                        target=request.target,
                        probe_type=request.probe_type,
                        status=status,
                        error_category=category,
                        observation=observation,
                        timestamp=datetime.now(UTC),
                        duration_ms=(monotonic() - started) * 1000,
                    )
                    results[request.id] = result
                    self.audit(result, context, decision)
                    previous = status == ProbeStatus.PASS

        groups: dict[str, list[ProbeRequest]] = {}
        for request in plan.requests:
            groups.setdefault(request.target.id, []).append(request)
        try:
            async with asyncio.timeout(
                min(config.limits.overall_probe_budget, max(0.001, context.deadline - monotonic()))
            ):
                async with asyncio.TaskGroup() as group:
                    for requests in groups.values():
                        group.create_task(chain(requests))
        except TimeoutError:
            self.logger.debug("probe_budget_exhausted")
        for request in plan.requests:
            if request.id not in results:
                result = ProbeResult(
                    request_id=request.id,
                    target=request.target,
                    probe_type=request.probe_type,
                    status=ProbeStatus.NOT_EXECUTED,
                    error_category="OVERALL_BUDGET_EXHAUSTED",
                    timestamp=datetime.now(UTC),
                    duration_ms=0,
                )
                results[request.id] = result
                self.audit(result, context, "BUDGET_EXHAUSTED")
        return tuple(as_evidence(results[r.id]) for r in plan.requests)
