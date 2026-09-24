import asyncio

import pytest
from fastmcp import Client

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.correlation.models import CorrelationQuery
from agt_mcp.gateways.threescale.classifier import ThreeScaleComponentClassifier
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.context import create_context
from agt_mcp.mcp.server import create_server
from tests.correlation_support import Clock
from tests.threescale_support import FakeRuntime, config, healthy_resources, snapshot


def setup(resources=None, configuration=None):
    configuration = configuration or config()
    snap, _ = snapshot(resources, configuration)
    runtime = build_runtime(configuration)
    adapter = runtime.gateway_discovery.adapters("dev")["threescale-auto"]
    adapter.runtime = FakeRuntime(snap)
    runtime.correlation.engine.clock = Clock()
    runtime.correlation.engine.clock.value = snap.observed_at
    subject = next(
        n.id
        for n in snap.topology.nodes
        if n.name == "apicast-production" and n.kind.value in {"service", "route"}
    )
    return runtime, adapter, subject


def test_three_tools_via_actual_mcp_and_single_collection():
    runtime, adapter, subject = setup()

    async def scenario():
        async with Client(create_server(runtime)) as client:
            tools = {t.name: t for t in await client.list_tools()}
            assert all(
                tools[name].annotations.read_only_hint
                for name in (
                    "correlate_evidence",
                    "get_correlation_timeline",
                    "explain_correlation",
                )
            )
            response = await client.call_tool(
                "correlate_evidence",
                {
                    "query": {
                        "resource_id": subject,
                        "include_history": False,
                        "include_knowledge": False,
                    }
                },
            )
            assert response.structured_content["ok"], response.structured_content
            result = response.structured_content["data"]
            assert result["candidates"] and result["timeline"]
            for name, key in (
                ("get_correlation_timeline", "timeline"),
                ("explain_correlation", "candidates"),
            ):
                response = await client.call_tool(name, {"result_id": result["id"]})
                assert response.structured_content["ok"], response.structured_content
                assert response.structured_content["data"][key] == result[key]
            assert len(adapter.runtime.calls) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "case,error",
    [
        ("environment", "authorization"),
        ("resource", "resource_not_found"),
        ("permission", "authorization"),
        ("operation", "unsupported_capability"),
        ("missing_cache", "resource_not_found"),
    ],
)
def test_mcp_denials(case, error):
    data = config().model_dump(mode="json")
    if case == "permission":
        data["mcp"]["server"]["authorization"]["permissions"] = [Capability.CORRELATION_READ]
    if case == "operation":
        data["application"]["allowed_operations"] = ["health"]
    runtime, adapter, subject = setup(configuration=Configuration.model_validate(data))

    async def scenario():
        async with Client(create_server(runtime)) as client:
            args = {
                "query": {
                    "resource_id": "missing" if case == "resource" else subject,
                    "include_knowledge": False,
                    "include_history": False,
                }
            }
            if case == "environment":
                args["environment_id"] = "prod"
            name = "correlate_evidence"
            if case == "missing_cache":
                name, args = "explain_correlation", {"result_id": "missing"}
            result = await client.call_tool(name, args)
            assert result.structured_content["error"] == error, result.structured_content

    asyncio.run(scenario())


def test_mcp_unknown_arguments_rejected():
    runtime, _, subject = setup()

    async def scenario():
        async with Client(create_server(runtime)) as client:
            result = await client.call_tool(
                "correlate_evidence",
                {"query": {"resource_id": subject, "execute": "delete pods"}},
                raise_on_error=False,
            )
            assert result.is_error

    asyncio.run(scenario())


def test_multi_installation_isolation_through_real_semantic_adapter():
    configuration = config(("one", "two"))
    runtime, adapter, subject = setup(
        healthy_resources("one") + healthy_resources("two"), configuration
    )
    installation = next(
        i
        for i in ThreeScaleComponentClassifier(adapter.runtime.result).classify()
        if subject in i.runtime_resources
    )
    other = next(
        i
        for i in ThreeScaleComponentClassifier(adapter.runtime.result).classify()
        if i.id != installation.id
    )
    execution = create_context(configuration, ToolName.CORRELATE_EVIDENCE, "dev", None)
    asyncio.run(adapter.connect(execution))
    result = asyncio.run(
        runtime.correlation.engine.correlate(
            CorrelationQuery(resource_id=subject, include_knowledge=False, include_history=False),
            execution,
        )
    )
    resources = {n.id for n in result.topology_context.nodes}
    assert resources <= set(installation.runtime_resources)
    assert resources.isdisjoint(other.runtime_resources)
    assert all(
        e.resource_id not in other.runtime_resources
        for s in result.evidence_sets
        for e in s.evidence
    )
    assert len(adapter.runtime.calls) == 1


def test_missing_route_target_produces_unresolved_structural_reference():
    resources = [
        r
        for r in healthy_resources()
        if not (r["kind"] == "Service" and r["metadata"]["name"] == "apicast-production")
    ]
    runtime, adapter, _ = setup(resources)
    route = next(
        n.id
        for n in adapter.runtime.result.topology.nodes
        if n.kind.value == "route" and n.name == "apicast-production"
    )
    execution = create_context(runtime.configuration, ToolName.CORRELATE_EVIDENCE, "dev", None)
    asyncio.run(adapter.connect(execution))
    result = asyncio.run(
        runtime.correlation.engine.correlate(
            CorrelationQuery(resource_id=route, include_knowledge=False, include_history=False),
            execution,
        )
    )
    assert any(link.relation.startswith("unresolved_") for link in result.semantic_links)
    assert any(c.relation_type.value == "DEPENDENCY" for c in result.candidates)
    assert result.status == "PARTIAL"


@pytest.mark.parametrize("scenario", ["no-endpoint", "crash-loop", "missing-timestamp"])
def test_real_runtime_projection_scenarios(scenario):
    from datetime import UTC, datetime, timedelta

    resources = healthy_resources()
    pod = next(
        r
        for r in resources
        if r["kind"] == "Pod" and r["metadata"]["name"] == "apicast-production-pod"
    )
    deployment = next(
        r
        for r in resources
        if r["kind"] == "Deployment" and r["metadata"]["name"] == "apicast-production"
    )
    event = next(r for r in resources if r["kind"] == "Event")
    event["involvedObject"] = {
        "kind": "Pod",
        "name": pod["metadata"]["name"],
        "namespace": "example",
        "uid": pod["metadata"]["uid"],
    }
    event["lastTimestamp"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    event["reason"] = "BackOff"
    if scenario == "no-endpoint":
        for resource in resources:
            if resource["kind"] == "EndpointSlice":
                resource["endpoints"][0]["conditions"]["ready"] = False
    elif scenario == "crash-loop":
        pod["status"]["containerStatuses"] = [
            {
                "name": "apicast-production",
                "ready": False,
                "restartCount": 4,
                "state": {"waiting": {"reason": "CrashLoopBackOff"}},
            }
        ]
        deployment["status"] = {"unavailableReplicas": 1, "availableReplicas": 0}
    else:
        del event["lastTimestamp"]
    runtime, adapter, _ = setup(resources)
    kind = "service" if scenario == "no-endpoint" else "deployment"
    subject = next(
        n.id
        for n in adapter.runtime.result.topology.nodes
        if n.name == "apicast-production" and n.kind.value == kind
    )
    execution = create_context(runtime.configuration, ToolName.CORRELATE_EVIDENCE, "dev", None)

    async def scenario_run():
        async with runtime.lifespan():
            return await runtime.correlation.engine.correlate(
                CorrelationQuery(
                    resource_id=subject, include_knowledge=False, include_history=False
                ),
                execution,
            )

    result = asyncio.run(scenario_run())
    if scenario == "missing-timestamp":
        assert any(
            t.event_type == "event" and t.timestamp is None and not t.relevant
            for t in result.timeline
        )
        assert "missing_timestamp" in {w.code for w in result.warnings}
    else:
        assert any(
            c.relation_type.value == "STATUS" and c.supporting_evidence for c in result.candidates
        )
        if scenario == "crash-loop":
            assert any(t.event_type == "event" and t.relevant for t in result.timeline)
            assert "CrashLoopBackOff" in result.model_dump_json()
