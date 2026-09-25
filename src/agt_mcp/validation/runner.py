"""Run the existing application entrypoints with injected fixture composition."""

from collections.abc import Awaitable, Callable
from typing import cast

from pydantic import JsonValue

from agt_mcp.core.errors import AGTError
from agt_mcp.core.execution import ToolName
from agt_mcp.mcp.context import create_context
from agt_mcp.observability.models import ObservabilityQuery, ObservabilityResult
from agt_mcp.services.runtime import Runtime
from agt_mcp.trace.models import TraceOperation, VirtualTrace
from agt_mcp.troubleshooting.models import TroubleshootingOperation, TroubleshootingResult
from agt_mcp.validation.assertions import evaluate
from agt_mcp.validation.models import FailureScenario, ScenarioResult

Invoke = Callable[[ToolName, dict[str, JsonValue]], Awaitable[dict[str, JsonValue]]]


class ScenarioRunner:
    def __init__(self, factory: Callable[[FailureScenario], Runtime]) -> None:
        self.factory = factory

    async def run(self, scenario: FailureScenario) -> ScenarioResult:
        runtime = self.factory(scenario)

        async def invoke(tool: ToolName, args: dict[str, JsonValue]) -> dict[str, JsonValue]:
            context = create_context(
                runtime.configuration,
                tool,
                scenario.request_environment or scenario.environment,
                "scenario-run",
            )
            if tool == ToolName.DIAGNOSE_API:
                return await runtime.execute(
                    context,
                    troubleshooting_operation=TroubleshootingOperation(query=scenario.query),
                )
            if tool == ToolName.INSPECT_OBSERVABILITY:
                return await runtime.execute(
                    context, observability_query=ObservabilityQuery.model_validate(args["query"])
                )
            return await runtime.execute(
                context, trace_operation=TraceOperation.model_validate(args)
            )

        async with runtime.lifespan():
            return await self.run_with(scenario, invoke)

    async def run_with(self, scenario: FailureScenario, invoke: Invoke) -> ScenarioResult:
        """The same sequence accepts an actual FastMCP Client invocation in E2E tests."""
        trace = None
        diagnosis = None
        error = None
        try:
            data = await invoke(
                ToolName.DIAGNOSE_API, {"query": scenario.query.model_dump(mode="json")}
            )
            diagnosis = TroubleshootingResult.model_validate(data)
            traced = await invoke(ToolName.TRACE_RESOURCE, {"troubleshooting_id": diagnosis.id})
            trace = VirtualTrace.model_validate(traced)
            if scenario.probes.enabled:
                plan = await invoke(ToolName.PLAN_PROBES, {"trace_id": trace.id})
                probed = await invoke(ToolName.EXECUTE_PROBE_PLAN, {"plan_id": plan["id"]})
                trace = VirtualTrace.model_validate(probed["trace"])
                diagnosis = TroubleshootingResult.model_validate(probed["diagnosis"])
            if scenario.observations or scenario.source_unavailable:
                enriched = ObservabilityResult.model_validate(
                    await invoke(
                        ToolName.INSPECT_OBSERVABILITY,
                        {
                            "query": cast(
                                dict[str, JsonValue],
                                {
                                    "environment_id": scenario.environment,
                                    "virtual_trace_id": trace.id,
                                    "time_window": scenario.query.time_window.model_dump(
                                        mode="json"
                                    )
                                    if scenario.query.time_window
                                    else None,
                                },
                            )
                        },
                    )
                )
                diagnosis, trace = enriched.diagnosis, enriched.virtual_trace
        except AGTError as exc:
            error = exc.code.value
        return evaluate(scenario, diagnosis, trace, error)
