import asyncio
from datetime import timedelta

import pytest

from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
    SanitizationError,
)
from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.probes.planner import ProbePlanner
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.runner import ProbeRunner
from agt_mcp.services.trace import TraceService
from agt_mcp.services.troubleshooting import TroubleshootingService
from agt_mcp.trace.models import TraceOperation
from agt_mcp.troubleshooting.models import TroubleshootingOperation
from tests.correlation_support import NOW, context, query
from tests.probe_support import FakeExecutor, config
from tests.troubleshooting_support import engine

GRANTS = frozenset(Capability)


def service(settings=None):
    policy = ProbePolicy(settings or config())
    fake = FakeExecutor()
    return TraceService(
        TroubleshootingService(engine()),
        ProbePlanner(policy, fake.capabilities()),
        ProbeRunner(policy, fake),
    )


def call(subject, tool=ToolName.TRACE_RESOURCE, operation=None, grants=GRANTS, ctx=None):
    return asyncio.run(
        subject.execute(
            operation or TraceOperation(query=query()), ctx or context(tool), grants, False
        )
    )


def test_trace_plan_execute_explain_reuses_collection():
    subject = service()
    trace = call(subject)
    plan = call(subject, ToolName.PLAN_PROBES, TraceOperation(trace_id=trace["id"]))
    assert plan["requests"] and not subject.runner.executor.calls
    executed = call(subject, ToolName.EXECUTE_PROBE_PLAN, TraceOperation(plan_id=plan["id"]))
    assert executed["trace"]["trace_type"] == "PROBED_TRACE" and executed["diagnosis"]
    explained = call(subject, ToolName.EXPLAIN_TRACE, TraceOperation(trace_id=trace["id"]))
    assert explained["probes"] and explained["relationships"]
    assert subject.troubleshooting.engine.correlation.provider.calls == 1


@pytest.mark.parametrize(
    "case", ["principal", "environment", "missing", "expired", "revoked", "execute_permission"]
)
def test_trace_cache_authorization(case):
    subject = service()
    trace = call(subject)
    p = call(subject, ToolName.PLAN_PROBES, TraceOperation(trace_id=trace["id"]))
    ctx = context(ToolName.EXPLAIN_TRACE)
    op = TraceOperation(trace_id=trace["id"])
    grants = GRANTS
    if case in {"principal", "environment"}:
        ctx = ctx.model_copy(
            update={"principal_id" if case == "principal" else "environment_id": "other"}
        )
    elif case == "missing":
        op = TraceOperation(trace_id="missing")
    elif case == "expired":
        subject.troubleshooting.engine.correlation.clock.value = NOW + timedelta(seconds=301)
    elif case == "revoked":
        grants = frozenset({Capability.TRACE_READ})
    else:
        ctx = context(ToolName.EXECUTE_PROBE_PLAN)
        op = TraceOperation(plan_id=p["id"])
        grants = GRANTS - {Capability.PROBE_EXECUTE}
    with pytest.raises(
        AuthorizationError if case in {"revoked", "execute_permission"} else ResourceNotFound
    ):
        call(subject, operation=op, grants=grants, ctx=ctx)
    assert not subject.runner.executor.calls


@pytest.mark.parametrize("case", ["query", "resource", "component", "permissions", "size", "plan"])
def test_invalid_requests_fail_without_network(case):
    subject = service()
    op = TraceOperation() if case == "query" else TraceOperation(query=query())
    tool = ToolName.TRACE_GATEWAY_COMPONENT if case == "component" else ToolName.TRACE_RESOURCE
    if case == "resource":
        op = TraceOperation(
            query=query().model_copy(update={"resource_id": None, "component_id": "component"})
        )
    if case == "plan":
        trace = call(subject)
        op = TraceOperation(trace_id=trace["id"], plan_id="unknown")
        tool = ToolName.EXECUTE_PROBE_PLAN
    ctx = context(tool)
    if case == "size":
        ctx = ctx.model_copy(update={"max_payload_bytes": 1024})
    error = (
        AuthorizationError
        if case == "permissions"
        else SanitizationError
        if case == "size"
        else ResourceNotFound
        if case == "plan"
        else ConfigurationError
    )
    with pytest.raises(error):
        call(
            subject, operation=op, grants=frozenset() if case == "permissions" else GRANTS, ctx=ctx
        )
    assert not subject.runner.executor.calls


@pytest.mark.parametrize("case", ["valid", "missing", "expired", "permission"])
def test_planning_from_missing_diagnostic_evidence(case):
    subject = service()
    diagnosis = asyncio.run(
        subject.troubleshooting.execute(
            TroubleshootingOperation(query=query()), context(ToolName.DIAGNOSE_API), GRANTS, False
        )
    )
    op = TraceOperation(troubleshooting_id=diagnosis["id"] if case != "missing" else "missing")
    if case == "expired":
        subject.troubleshooting.engine.correlation.clock.value = NOW + timedelta(seconds=301)
    if case == "valid":
        result = call(subject, ToolName.PLAN_PROBES, op)
        assert result["trace_id"] and not result["executed"]
    else:
        with pytest.raises(AuthorizationError if case == "permission" else ResourceNotFound):
            call(
                subject,
                ToolName.PLAN_PROBES,
                op,
                grants=GRANTS - {Capability.TROUBLESHOOTING_READ}
                if case == "permission"
                else GRANTS,
            )


def test_cache_eviction():
    subject = service(config(limits={"cache_entries": 1}))
    first = call(subject)
    call(subject, operation=TraceOperation(query=query().model_copy(update={"resource_id": "pod"})))
    assert len(subject.cache) == 1
    with pytest.raises(ResourceNotFound):
        call(subject, ToolName.EXPLAIN_TRACE, TraceOperation(trace_id=first["id"]))
