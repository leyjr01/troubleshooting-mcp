import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError

from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
    SanitizationError,
)
from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.evidence.bundle import IncidentBundle
from agt_mcp.services.troubleshooting import TroubleshootingService
from agt_mcp.troubleshooting.models import TroubleshootingOperation
from tests.correlation_support import NOW, context, query
from tests.troubleshooting_support import diagnose, engine

GRANTS = frozenset(Capability)


def call(service, op=None, tool=ToolName.DIAGNOSE_API, grants=GRANTS, ctx=None):
    return asyncio.run(
        service.execute(
            op or TroubleshootingOperation(query=query()), ctx or context(tool), grants, False
        )
    )


def test_scoped_cache_explanation_plan_and_expiry():
    service = TroubleshootingService(engine())
    result = call(service)
    identifier = result["hypotheses"][0]["id"]
    explanation = call(
        service, TroubleshootingOperation(hypothesis_id=identifier), ToolName.EXPLAIN_HYPOTHESIS
    )
    assert (
        explanation["hypothesis"]["id"] == identifier
        and explanation["definition"]["required_evidence"]
    )
    plan = call(
        service, TroubleshootingOperation(result_id=result["id"]), ToolName.GET_TROUBLESHOOTING_PLAN
    )
    assert plan["troubleshooting_plan"] == result["troubleshooting_plan"]
    assert service.engine.correlation.provider.calls == 1
    service.engine.correlation.clock.value = NOW + timedelta(seconds=301)
    with pytest.raises(ResourceNotFound):
        call(
            service, TroubleshootingOperation(hypothesis_id=identifier), ToolName.EXPLAIN_HYPOTHESIS
        )
    assert not service.cache


@pytest.mark.parametrize(
    "case", ["principal", "environment", "permission", "missing", "plan_permission"]
)
def test_cache_scope_and_permissions_rechecked(case):
    service = TroubleshootingService(engine())
    result = call(service)
    op = TroubleshootingOperation(
        hypothesis_id=result["hypotheses"][0]["id"], result_id=result["id"]
    )
    ctx = context(ToolName.EXPLAIN_HYPOTHESIS)
    grants = GRANTS
    if case in {"principal", "environment"}:
        ctx = ctx.model_copy(
            update={"principal_id" if case == "principal" else "environment_id": "other"}
        )
    elif case in {"permission", "plan_permission"}:
        grants = frozenset({Capability.TROUBLESHOOTING_READ})
        if case == "plan_permission":
            ctx = context(ToolName.GET_TROUBLESHOOTING_PLAN)
    else:
        op = op.model_copy(update={"hypothesis_id": "missing"})
    with pytest.raises(AuthorizationError if "permission" in case else ResourceNotFound):
        call(service, op, grants=grants, ctx=ctx)


@pytest.mark.parametrize(
    "tool", [ToolName.DIAGNOSE_API, ToolName.DIAGNOSE_COMPONENT, ToolName.DIAGNOSE_GATEWAY]
)
def test_missing_tool_subject_is_rejected(tool):
    with pytest.raises(ConfigurationError):
        call(TroubleshootingService(engine()), TroubleshootingOperation(), tool)


def test_permissions_precede_collection_and_oversized_output_not_cached():
    service = TroubleshootingService(engine())
    with pytest.raises(AuthorizationError):
        call(service, grants=frozenset({Capability.TROUBLESHOOTING_READ}))
    assert service.engine.correlation.provider.calls == 0
    with pytest.raises(SanitizationError):
        call(
            service,
            ctx=context(ToolName.DIAGNOSE_API).model_copy(update={"max_payload_bytes": 1000}),
        )
    assert not service.cache


def test_unmapped_api_limit_and_missing_component_error():
    service = TroubleshootingService(engine())
    limited = call(service, TroubleshootingOperation(query=query(resource_id="unmapped-api")))
    assert limited["status"] == "LIMITED" and not limited["root_cause_candidates"]
    with pytest.raises(ResourceNotFound):
        call(
            service,
            TroubleshootingOperation(query=query(resource_id=None, component_id="unmapped")),
            ToolName.DIAGNOSE_COMPONENT,
        )
    with pytest.raises(ResourceNotFound):
        call(service, TroubleshootingOperation(), ToolName.GET_TROUBLESHOOTING_PLAN)


def test_bounded_cache_eviction():
    service = TroubleshootingService(engine(cache_entries=1))
    first = call(service)
    second = call(service, TroubleshootingOperation(query=query(resource_id="pod")))
    assert first["id"] != second["id"] and len(service.cache) == 1


def test_bundle_keeps_findings_and_recommendations_separate(bundle_data):
    original = IncidentBundle.model_validate(bundle_data)
    bundle = IncidentBundle(**(original.model_dump() | {"troubleshooting": (diagnose(),)}))
    assert (
        bundle.findings == original.findings and bundle.recommendations == original.recommendations
    )
    assert bundle.incident.root_cause_finding_id == original.incident.root_cause_finding_id
    assert IncidentBundle.model_validate_json(bundle.model_dump_json()) == bundle
    foreign = original.model_dump() | {
        "environment": original.environment.model_copy(update={"id": "other"}),
        "troubleshooting": (diagnose(),),
    }
    with pytest.raises(ValidationError):
        IncidentBundle(**foreign)
