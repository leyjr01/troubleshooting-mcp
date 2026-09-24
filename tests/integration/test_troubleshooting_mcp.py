import asyncio

import pytest
from fastmcp import Client

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.correlation.models import CorrelationQuery
from agt_mcp.gateways.threescale.classifier import ThreeScaleComponentClassifier
from agt_mcp.mcp.context import create_context
from agt_mcp.mcp.server import create_server
from tests.integration.test_correlation_mcp import setup
from tests.threescale_support import config, healthy_resources


@pytest.mark.parametrize("tool", ["diagnose_api", "diagnose_component", "diagnose_gateway"])
def test_diagnostic_tools_and_cached_explanation_plan_via_actual_mcp(tool):
    runtime, adapter, resource = setup()
    installation = ThreeScaleComponentClassifier(adapter.runtime.result).classify()[0]
    component = next(c for c in installation.components if c.type.value == "APICAST_PRODUCTION")

    async def run():
        async with Client(create_server(runtime)) as client:
            tools = {t.name: t for t in await client.list_tools()}
            for name in (tool, "explain_hypothesis", "get_troubleshooting_plan"):
                assert (
                    tools[name].annotations.read_only_hint
                    and not tools[name].annotations.destructive_hint
                )
            query = {"include_knowledge": False, "include_history": False}
            query.update(
                {"resource_id": resource}
                if tool == "diagnose_api"
                else {"component_id": component.id}
                if tool == "diagnose_component"
                else {"gateway_id": installation.id}
            )
            result = (await client.call_tool(tool, {"query": query})).structured_content
            assert result["ok"], result
            data = result["data"]
            assert data["hypotheses"] and data["context"]["engine_version"] == "1.0.0"
            explain = (
                await client.call_tool(
                    "explain_hypothesis", {"hypothesis_id": data["hypotheses"][0]["id"]}
                )
            ).structured_content
            assert explain["ok"] and explain["data"]["definition"]["required_evidence"]
            plan = (
                await client.call_tool("get_troubleshooting_plan", {"result_id": data["id"]})
            ).structured_content
            assert plan["ok"] and not plan["data"]["troubleshooting_plan"]["executed"]
            assert len(adapter.runtime.calls) == 1
            assert "PASSWORD-SYNTHETIC" not in str(data)

    asyncio.run(run())


@pytest.mark.parametrize(
    "case,error",
    [
        ("environment", "authorization"),
        ("permission", "authorization"),
        ("operation", "unsupported_capability"),
        ("missing_subject", "configuration"),
        ("component", "resource_not_found"),
    ],
)
def test_mcp_diagnostic_denials(case, error):
    data = config().model_dump(mode="json")
    if case == "permission":
        data["mcp"]["server"]["authorization"]["permissions"] = [Capability.TROUBLESHOOTING_READ]
    if case == "operation":
        data["application"]["allowed_operations"] = ["health"]
    runtime, _, resource = setup(configuration=Configuration.model_validate(data))

    async def run():
        async with Client(create_server(runtime)) as client:
            tool = (
                "diagnose_component" if case in {"component", "missing_subject"} else "diagnose_api"
            )
            query = {"resource_id": resource, "include_knowledge": False, "include_history": False}
            if case == "component":
                query = {
                    "component_id": "absent",
                    "include_knowledge": False,
                    "include_history": False,
                }
            result = (
                await client.call_tool(
                    tool,
                    {"query": query, "environment_id": "prod" if case == "environment" else "dev"},
                )
            ).structured_content
            assert result["error"] == error, result

    asyncio.run(run())


def test_unmapped_api_returns_explicit_limitation_and_no_invented_mapping():
    runtime, _, _ = setup()

    async def run():
        async with Client(create_server(runtime)) as client:
            result = (
                await client.call_tool(
                    "diagnose_api",
                    {
                        "query": {
                            "resource_id": "admin-api-product-not-discovered",
                            "include_knowledge": False,
                            "include_history": False,
                        }
                    },
                )
            ).structured_content
            assert result["ok"] and result["data"]["status"] == "LIMITED"
            assert result["data"]["missing_capabilities"] == ["API_MAPPING_NOT_AVAILABLE"]
            assert not result["data"]["root_cause_candidates"]
            invalid = await client.call_tool(
                "diagnose_api",
                {"query": {"resource_id": "x", "execute": "restart"}},
                raise_on_error=False,
            )
            assert invalid.is_error

    asyncio.run(run())


def test_installation_b_cannot_support_diagnosis_for_a():
    runtime, adapter, resource = setup(
        healthy_resources("one") + healthy_resources("two"), config(("one", "two"))
    )
    installations = ThreeScaleComponentClassifier(adapter.runtime.result).classify()
    chosen = next(i for i in installations if resource in i.runtime_resources)
    foreign = next(i for i in installations if i.id != chosen.id)
    execution = create_context(runtime.configuration, ToolName.DIAGNOSE_API, "dev", None)

    async def run():
        async with runtime.lifespan():
            return await runtime.troubleshooting.engine.diagnose(
                CorrelationQuery(
                    resource_id=resource, include_knowledge=False, include_history=False
                ),
                execution,
            )

    result = asyncio.run(run())
    assert all(set(h.resources).isdisjoint(foreign.runtime_resources) for h in result.hypotheses)
    evidence = {e.id: e for s in result.correlation_result.evidence_sets for e in s.evidence}
    assert all(
        evidence[i].resource_id in chosen.runtime_resources
        for h in result.hypotheses
        for i in h.evaluation.supporting_evidence
    )
    assert all(c.namespace != foreign.namespace for c in result.correlation_result.coverage)


@pytest.mark.parametrize(
    "scenario", ["no-endpoint", "ready", "missing-route", "disabled-zync", "crash-loop"]
)
def test_real_semantic_projections_produce_safe_hypotheses(scenario):
    resources = healthy_resources()
    if scenario == "missing-route":
        resources = [
            r
            for r in resources
            if not (r["kind"] == "Service" and r["metadata"]["name"] == "apicast-production")
        ]
    if scenario == "no-endpoint":
        for resource in resources:
            if resource["kind"] == "EndpointSlice":
                resource["endpoints"][0]["conditions"]["ready"] = False
    if scenario == "disabled-zync":
        resources[0]["spec"]["zync"]["enabled"] = False
        resources = [r for r in resources if not r["metadata"]["name"].startswith("zync")]
    if scenario == "crash-loop":
        for resource in resources:
            if (
                resource["kind"] == "Pod"
                and resource["metadata"]["name"] == "apicast-production-pod"
            ):
                resource["status"]["containerStatuses"] = [
                    {
                        "name": "apicast",
                        "ready": False,
                        "restartCount": 8,
                        "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                    }
                ]
    data = config().model_dump()
    data["correlation"].update(max_resources=50, max_events=50, max_candidates=50)
    runtime, adapter, resource = setup(resources, Configuration.model_validate(data))
    installation = ThreeScaleComponentClassifier(adapter.runtime.result).classify()[0]
    if scenario == "disabled-zync":
        component = next(c for c in installation.components if c.type.value == "ZYNC")
        request = CorrelationQuery(
            component_id=component.id, include_knowledge=False, include_history=False
        )
    else:
        kind = (
            "route"
            if scenario == "missing-route"
            else "pod"
            if scenario == "crash-loop"
            else "service"
        )
        resource = next(
            n.id
            for n in adapter.runtime.result.topology.nodes
            if n.kind.value == kind
            and n.name == ("apicast-production-pod" if kind == "pod" else "apicast-production")
        )
        request = CorrelationQuery(
            resource_id=resource, include_knowledge=False, include_history=False
        )
    execution = create_context(runtime.configuration, ToolName.DIAGNOSE_API, "dev", None)

    async def run():
        async with runtime.lifespan():
            return await runtime.troubleshooting.engine.diagnose(request, execution)

    result = asyncio.run(run())
    if scenario == "disabled-zync":
        assert not result.hypotheses
    else:
        definition = (
            "ROUTE_TARGET_MISSING"
            if scenario == "missing-route"
            else "POD_CRASH_LOOP"
            if scenario == "crash-loop"
            else "APICAST_NO_READY_RUNTIME_ENDPOINT"
        )
        h = next(
            h for h in result.hypotheses if h.definition_id == definition and h.subject == resource
        )
        assert h.evaluation.status == ("REJECTED" if scenario == "ready" else "SUPPORTED")
        if scenario in {"no-endpoint", "missing-route"}:
            assert h.evaluation.confidence.level == "high"
