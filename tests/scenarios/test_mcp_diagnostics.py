import asyncio

import pytest
from fastmcp import Client

from agt_mcp.core.errors import AuthorizationError
from agt_mcp.core.execution import ToolName
from agt_mcp.mcp.server import create_server
from agt_mcp.validation.runner import ScenarioRunner
from tests.scenarios.fixtures import application, definitions, fixed_world, materialize


@pytest.mark.parametrize(
    "name",
    [
        "backend-down",
        "backend-http-500",
        "tls-expired",
        "contradictory-evidence",
        "secret-in-log",
        "unauthorized-environment",
    ],
)
def test_existing_mcp_diagnostic_path(name):
    case = next(c for c in definitions() if c.id == name)
    scenario = materialize(case)
    runtime = application(scenario)

    async def execute():
        async with Client(create_server(runtime)) as client:
            plans = {}

            async def invoke(tool, args):
                # MCP exposes cached diagnosis tracing through plan_probes.
                # Reuse its plan so this path collects no second snapshot.
                if tool == ToolName.TRACE_RESOURCE:
                    plan = await invoke(ToolName.PLAN_PROBES, args)
                    plans[plan["trace_id"]] = plan
                    trace = await invoke(ToolName.EXPLAIN_TRACE, {"trace_id": plan["trace_id"]})
                    return {k: v for k, v in trace.items() if k != "probe_plan"}
                if tool == ToolName.PLAN_PROBES and args.get("trace_id") in plans:
                    return plans[args["trace_id"]]
                # Existing diagnose tools use their configured 900-second window;
                # the frozen application clock makes it identical to the fixture.
                if tool == ToolName.DIAGNOSE_API:
                    args = {"query": {k: v for k, v in args["query"].items() if k != "time_window"}}
                response = (
                    await client.call_tool(
                        tool.value,
                        {
                            **args,
                            "environment_id": scenario.request_environment or scenario.environment,
                        },
                    )
                ).structured_content
                if not response["ok"]:
                    assert response["error"] == "authorization", response
                    raise AuthorizationError()
                return response["data"]

            return await ScenarioRunner(application).run_with(scenario, invoke)

    with fixed_world():
        result = asyncio.run(execute())
    assert set(result.failed_assertions) == set(case.known_gaps), result.failed_assertions
