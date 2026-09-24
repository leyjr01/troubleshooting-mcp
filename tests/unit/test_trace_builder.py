import pytest

from agt_mcp.configuration.probes import TraceLimits
from agt_mcp.core.errors import ResourceNotFound
from agt_mcp.correlation.models import CorrelationLink
from agt_mcp.probes.models import ProbeCapability
from agt_mcp.probes.planner import ProbePlanner
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.trace.builder import VirtualTraceBuilder
from agt_mcp.trace.models import VirtualTrace
from tests.correlation_support import NOW, provenance
from tests.probe_support import config, trace
from tests.troubleshooting_support import diagnose


def test_structural_path_is_not_network_trace():
    result = trace()
    assert {h.reference for h in result.hops} >= {"service", "slice", "pod"}
    assert result.trace_type == "STRUCTURAL_TRACE" and not result.communication_verified
    assert result.relationships and all(r.provenance for r in result.relationships)
    assert result == trace()


@pytest.mark.parametrize(
    "limit,value,warning",
    [
        ("max_hops", 1, "trace_node_limit"),
        ("max_nodes", 1, "trace_node_limit"),
        ("max_branches", 1, "trace_branch_limit"),
        ("max_depth", 0, "trace_depth_limit"),
    ],
)
def test_trace_bounds(limit, value, warning):
    result = VirtualTraceBuilder(TraceLimits(**{limit: value})).build(diagnose().correlation_result)
    assert warning in result.warnings


@pytest.mark.parametrize("direction", ["incoming", "both"])
def test_direction_and_component_origin(direction):
    original = diagnose().correlation_result
    original = original.model_copy(
        update={"context": original.context.model_copy(update={"subject": "pod"})}
    )
    built = VirtualTraceBuilder(TraceLimits()).build(original, direction)
    assert "slice" in {h.reference for h in built.hops}
    component = original.component_context[0].id
    component_result = original.model_copy(
        update={"context": original.context.model_copy(update={"subject": component})}
    )
    assert len(VirtualTraceBuilder(TraceLimits()).build(component_result).hops) > 1


def test_unresolved_link_never_invents_endpoint():
    original = diagnose().correlation_result
    original = original.model_copy(
        update={
            "semantic_links": (
                CorrelationLink(
                    id="missing",
                    source="service",
                    target="unresolved-service",
                    relation="unresolved_not_found",
                    provenance=provenance(),
                ),
            )
        }
    )
    built = VirtualTraceBuilder(TraceLimits()).build(original)
    assert (
        next(h for h in built.hops if h.reference == "unresolved-service").structural_status
        == "UNRESOLVED"
    )
    empty = ProbePlanner(ProbePolicy(config(endpoints=())), frozenset(ProbeCapability)).plan(
        built, NOW
    )
    assert not empty.requests and "target_unresolved" in empty.warnings
    assert not empty.executed


def test_trace_invalid_origin_and_scope():
    original = diagnose().correlation_result
    with pytest.raises(ResourceNotFound):
        VirtualTraceBuilder(TraceLimits()).build(
            original.model_copy(
                update={"context": original.context.model_copy(update={"subject": "unknown"})}
            )
        )
    built = trace()
    for update in ({"subject": "unknown"}, {"hops": built.hops * 2}, {"environment_id": "other"}):
        with pytest.raises(ValueError):
            VirtualTrace.model_validate(built.model_copy(update=update).model_dump())


def test_plan_missing_capabilities_limits_and_diagnostic_scope():
    cfg = config(limits={"max_probes_per_request": 1})
    planner = ProbePlanner(ProbePolicy(cfg), frozenset())
    p = planner.plan(trace(), NOW)
    assert len(p.requests) == 1 and p.requests[0].reason == "CAPABILITY_UNAVAILABLE"
    assert "probe_plan_truncated" in p.warnings
    diagnostic = diagnose()
    planner.plan(trace(), NOW, diagnostic)
    with pytest.raises(ValueError):
        planner.plan(trace().model_copy(update={"environment_id": "other"}), NOW, diagnostic)
