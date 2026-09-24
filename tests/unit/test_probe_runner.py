import asyncio
import json
from datetime import timedelta
from unittest.mock import patch

import pytest

from agt_mcp.probes.models import ProbeEvidence, ProbeObservation, ProbeStatus, ProbeType
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.refresh import reevaluate
from agt_mcp.probes.runner import ProbeRunner, as_evidence
from agt_mcp.trace.builder import VirtualTraceBuilder
from agt_mcp.troubleshooting.catalog import HypothesisCatalog
from agt_mcp.troubleshooting.network_hypotheses import NetworkHypothesisProvider
from tests.correlation_support import NOW, context
from tests.probe_support import FakeExecutor, config, plan, trace
from tests.troubleshooting_support import diagnose, engine, hypothesis


@pytest.mark.parametrize(
    "failure,expected",
    [
        (None, ["PASS"] * 4),
        (ProbeType.DNS, ["FAILED", "NOT_EXECUTED", "NOT_EXECUTED", "NOT_EXECUTED"]),
        (ProbeType.TCP, ["PASS", "FAILED", "NOT_EXECUTED", "NOT_EXECUTED"]),
        (ProbeType.TLS, ["PASS", "PASS", "FAILED", "NOT_EXECUTED"]),
    ],
)
def test_sequential_dependencies_failure_taxonomy_and_audit(failure, expected, caplog):
    cfg = config()
    executor = FakeExecutor(failure)
    with caplog.at_level("INFO", logger="agt_mcp.audit"):
        results = asyncio.run(ProbeRunner(ProbePolicy(cfg), executor).execute(plan(cfg), context()))
    assert [p.result.status.value for p in results] == expected
    assert len(executor.calls) == (list(ProbeType).index(failure) + 1 if failure else 4)
    events = [json.loads(r.message) for r in caplog.records]
    assert len(events) == 4 and all(e["target_origin"] and e["policy_decision"] for e in events)
    assert "backend.example" not in caplog.text
    assert all(
        p.evidence.source.content_sha256 and p.evidence.resource_id == "service" for p in results
    )
    if failure is None:
        assert results[-1].result.observation.http_status == 503
        assert results[-1].evidence.metadata["probe_type"] == "probe.http"
    built = VirtualTraceBuilder(cfg.trace).attach(trace(), results)
    assert built.trace_type == "PROBED_TRACE" and not built.communication_verified


@pytest.mark.parametrize(
    "case", ["disabled", "plan_only", "capability", "policy", "forged_allowed", "bad_dns"]
)
def test_execution_checks_every_boundary(case):
    cfg = (
        config(enabled=False)
        if case == "disabled"
        else config(execution_mode="plan_only")
        if case == "plan_only"
        else config()
    )
    executor = FakeExecutor()
    p = plan(cfg)
    if case == "capability":
        executor.capabilities = lambda: frozenset()
    if case == "policy":
        cfg = cfg.model_copy(update={"endpoints": ()})
    if case == "forged_allowed":
        p = p.model_copy(
            update={
                "requests": tuple(
                    r.model_copy(update={"allowed": False, "reason": "HOST_DENIED"})
                    for r in p.requests
                )
            }
        )
    if case == "bad_dns":

        async def unsafe(request, addresses):
            return ProbeObservation(addresses=("169.254.169.254",))

        executor.execute = unsafe
    results = asyncio.run(ProbeRunner(ProbePolicy(cfg), executor).execute(p, context()))
    assert results[0].result.status == ProbeStatus.BLOCKED
    if case != "bad_dns":
        assert not executor.calls
        assert (
            VirtualTraceBuilder(cfg.trace).attach(trace(), results).trace_type == "STRUCTURAL_TRACE"
        )


@pytest.mark.parametrize("stage", [ProbeType.DNS, ProbeType.TCP, ProbeType.HTTPS])
def test_per_probe_timeout(stage):
    cfg = config(limits={"timeout_seconds": 0.01})
    fake = FakeExecutor()
    original = fake.execute

    async def slow(request, addresses):
        if request.probe_type == stage:
            await asyncio.sleep(1)
        return await original(request, addresses)

    fake.execute = slow
    results = asyncio.run(ProbeRunner(ProbePolicy(cfg), fake).execute(plan(cfg), context()))
    timed = next(p for p in results if p.result.probe_type == stage)
    assert timed.result.status == ProbeStatus.FAILED and "TIMEOUT" in timed.result.error_category


def test_budget_and_cancellation_audited(caplog):
    cfg = config(limits={"overall_probe_budget": 0.01})
    fake = FakeExecutor()

    async def slow(request, addresses):
        await asyncio.sleep(10)

    fake.execute = slow
    with caplog.at_level("INFO", logger="agt_mcp.audit"):
        results = asyncio.run(ProbeRunner(ProbePolicy(cfg), fake).execute(plan(cfg), context()))
    assert results[0].result.status == ProbeStatus.CANCELLED
    assert all(p.result.error_category == "OVERALL_BUDGET_EXHAUSTED" for p in results[1:])
    assert '"status": "CANCELLED"' in caplog.text
    cached_plan = plan()

    async def cancel():
        task = asyncio.create_task(
            ProbeRunner(ProbePolicy(config()), fake).execute(cached_plan, context())
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())


def test_concurrency_is_bounded_and_results_ordered():
    cfg = config()
    cfg = cfg.model_copy(
        update={
            "endpoints": tuple(
                cfg.endpoints[0].model_copy(update={"id": f"backend-{i}"}) for i in range(3)
            )
        }
    )
    fake = FakeExecutor()
    original = fake.execute
    active = peak = 0

    async def slow(request, addresses):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.002)
        active -= 1
        return await original(request, addresses)

    fake.execute = slow
    p = plan(cfg)
    results = asyncio.run(ProbeRunner(ProbePolicy(cfg), fake).execute(p, context()))
    assert peak == 2 and [r.result.request_id for r in results] == [r.id for r in p.requests]


@pytest.mark.parametrize(
    "failure,definition,status",
    [
        (ProbeType.TLS, "TLS_VERIFICATION_UNAVAILABLE", "SUPPORTED"),
        (None, "TLS_VERIFICATION_UNAVAILABLE", "REJECTED"),
        (ProbeType.TCP, "DEPENDENCY_TCP_UNAVAILABLE", "SUPPORTED"),
        (None, "DEPENDENCY_TCP_UNAVAILABLE", "REJECTED"),
    ],
)
def test_same_engine_re_evaluates_probe_evidence(failure, definition, status):
    diagnostic_engine = engine()

    class Combined:
        def definitions(self):
            return (
                *diagnostic_engine.catalog.definitions,
                *NetworkHypothesisProvider().definitions(),
            )

    catalog = HypothesisCatalog((Combined(),))
    diagnostic_engine.catalog = catalog
    diagnostic_engine.generator.catalog = catalog
    diagnostic_engine.evaluator.catalog = catalog
    diagnostic_engine.planner.catalog = catalog
    before = diagnose(diagnostic_engine)
    assert hypothesis(before, definition).evaluation.status == "INCONCLUSIVE"
    results = asyncio.run(
        ProbeRunner(ProbePolicy(config()), FakeExecutor(failure)).execute(plan(), context())
    )
    results = tuple(
        as_evidence(p.result.model_copy(update={"timestamp": NOW - timedelta(seconds=1)}))
        for p in results
    )
    with patch.object(
        diagnostic_engine.evaluator, "evaluate", wraps=diagnostic_engine.evaluator.evaluate
    ) as evaluator:
        after = asyncio.run(
            reevaluate(diagnostic_engine, before.correlation_result, results, context())
        )
    assert evaluator.call_count > 0
    assert hypothesis(after, definition).evaluation.status == status
    assert all(c.scope == "observed_condition" for c in after.root_cause_candidates)
    assert any(
        e.observation.startswith("probe.")
        for s in after.correlation_result.evidence_sets
        for e in s.evidence
    )
    with pytest.raises(ValueError):
        ProbeEvidence.model_validate(
            results[0]
            .model_copy(
                update={"evidence": results[0].evidence.model_copy(update={"resource_id": "wrong"})}
            )
            .model_dump()
        )


def test_runner_rejects_scope_and_limit():
    runner = ProbeRunner(ProbePolicy(config(limits={"max_probes_per_request": 1})), FakeExecutor())
    with pytest.raises(ValueError):
        asyncio.run(runner.execute(plan(), context()))
    with pytest.raises(ValueError):
        asyncio.run(
            runner.execute(plan().model_copy(update={"environment_id": "other"}), context())
        )
