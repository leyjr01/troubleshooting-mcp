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
from agt_mcp.correlation.models import CorrelationOperation
from agt_mcp.services.correlation import CorrelationService
from tests.correlation_support import NOW, context, engine, query

GRANTS = frozenset(Capability)


def invoke(service, operation=None, ctx=None, grants=GRANTS):
    return asyncio.run(
        service.execute(
            operation or CorrelationOperation(query=query()), ctx or context(), grants, False
        )
    )


def test_cached_timeline_explanation_and_expiration():
    service = CorrelationService(engine())
    result = invoke(service)
    op = CorrelationOperation(result_id=result["id"])
    timeline = invoke(service, op, context(ToolName.GET_CORRELATION_TIMELINE))
    assert timeline["timeline"] == result["timeline"]
    explanation = invoke(service, op, context(ToolName.EXPLAIN_CORRELATION))
    assert explanation["candidates"] == result["candidates"]
    candidate = result["candidates"][0]
    assert invoke(
        service,
        op.model_copy(update={"candidate_id": candidate["id"]}),
        context(ToolName.EXPLAIN_CORRELATION),
    )["candidates"] == [candidate]
    assert service.engine.provider.calls == 1
    service.engine.clock.value = NOW + timedelta(seconds=301)
    with pytest.raises(ResourceNotFound):
        invoke(service, op, context(ToolName.GET_CORRELATION_TIMELINE))
    assert not service.cache


@pytest.mark.parametrize("case", ["principal", "environment", "permission", "candidate", "missing"])
def test_cached_scope_and_permission_rechecked(case):
    service = CorrelationService(engine())
    result = invoke(service)
    op = CorrelationOperation(result_id=result["id"])
    ctx = context(ToolName.EXPLAIN_CORRELATION)
    grants = GRANTS
    if case == "principal":
        ctx = ctx.model_copy(update={"principal_id": "other"})
    elif case == "environment":
        ctx = ctx.model_copy(update={"environment_id": "prod"})
    elif case == "permission":
        grants = frozenset({Capability.CORRELATION_READ})
    elif case == "candidate":
        op = op.model_copy(update={"candidate_id": "absent"})
    else:
        op = CorrelationOperation()
    with pytest.raises(AuthorizationError if case == "permission" else ResourceNotFound):
        invoke(service, op, ctx, grants)


def test_required_permissions_checked_before_collecting():
    service = CorrelationService(engine())
    with pytest.raises(AuthorizationError):
        invoke(service, grants=frozenset({Capability.CORRELATION_READ}))
    assert service.engine.provider.calls == 0
    permissions = service.permissions(
        query(gateway_id="gateway", include_knowledge=True, include_history=True), True
    )
    assert {
        Capability.GATEWAY_DISCOVER,
        Capability.KNOWLEDGE_ISSUES,
        Capability.KNOWLEDGE_OFFICIAL,
    } <= permissions


def test_missing_query_and_payload_bound():
    service = CorrelationService(engine())
    with pytest.raises(ConfigurationError):
        invoke(service, CorrelationOperation())
    with pytest.raises(SanitizationError):
        invoke(service, ctx=context().model_copy(update={"max_payload_bytes": 1000}))
    assert not service.cache


def test_cache_eviction():
    service = CorrelationService(engine(cache_entries=1))
    first = invoke(service)
    second = invoke(service, CorrelationOperation(query=query(resource_id="pod")))
    assert first["id"] != second["id"] and len(service.cache) == 1
