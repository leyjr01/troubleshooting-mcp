import ast
import asyncio
from pathlib import Path

import pytest

from agt_mcp.configuration.models import Configuration
from agt_mcp.correlation.models import CorrelationLink
from agt_mcp.probes.models import ProbeStatus, ProbeType
from agt_mcp.probes.planner import ProbePlanner
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.runner import ProbeRunner
from agt_mcp.trace.builder import VirtualTraceBuilder
from agt_mcp.trace.models import VirtualTrace
from tests.correlation_support import NOW, context, provenance
from tests.probe_support import FakeExecutor, config, plan, trace
from tests.troubleshooting_support import diagnose, diagnostic_snapshot, engine


@pytest.mark.parametrize("package", ["trace", "probes", "troubleshooting"])
def test_no_concrete_network_gateway_or_llm_imports(package):
    root = Path(__file__).resolve().parents[2] / "src/agt_mcp" / package
    forbidden = (
        "agt_mcp.datasources",
        "agt_mcp.gateways",
        "agt_mcp.mcp",
        "socket",
        "ssl",
        "httpx",
        "aiohttp",
        "requests",
        "urllib",
        "fastmcp",
        "kubernetes",
        "openai",
        "subprocess",
    )
    for path in root.glob("*.py"):
        imports = [
            name
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            for name in (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
        ]
        assert not any(name.startswith(forbidden) for name in imports), path


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "::ffff:127.0.0.1"])
def test_loopback_and_aliases_require_explicit_environment_network(host):
    cfg = config(host=host)
    p = cfg.policy.environments[0].model_copy(update={"allowed_networks": ("10.20.0.0/16",)})
    cfg = cfg.model_copy(update={"policy": cfg.policy.model_copy(update={"environments": (p,)})})
    target = plan(cfg).requests[0].target
    assert (
        ProbePolicy(cfg).addresses(target, ("127.0.0.1" if host == "localhost" else host,))
        != "ALLOWED"
    )


def test_route_unresolved_blocks_even_configured_endpoint():
    original = diagnose().correlation_result
    original = original.model_copy(
        update={
            "semantic_links": (
                CorrelationLink(
                    id="missing-route-target",
                    source="service",
                    target="missing-service",
                    relation="unresolved_not_found",
                    target_kind="Service",
                    provenance=provenance(),
                ),
            )
        }
    )
    cfg = config()
    built = VirtualTraceBuilder(cfg.trace).build(original)
    p = ProbePlanner(ProbePolicy(cfg), FakeExecutor().capabilities()).plan(built, NOW)
    assert not p.requests and "structural_path_incomplete" in p.warnings


def test_semantic_component_dependency_reference_is_preserved_without_secret_read():
    snapshot = diagnostic_snapshot()
    snapshot = snapshot.model_copy(
        update={
            "links": (
                CorrelationLink(
                    id="external-redis",
                    source=snapshot.components[0].id,
                    target="redis-reference",
                    relation="depends_on",
                    provenance=provenance(),
                ),
            )
        }
    )
    result = diagnose(engine(snapshot)).correlation_result
    assert any(e.id == "external-redis" for e in result.semantic_links)
    built = VirtualTraceBuilder(config().trace).build(result)
    assert any(
        h.reference == "redis-reference" and h.structural_status == "UNRESOLVED" for h in built.hops
    )
    cfg = config(endpoints=())
    assert (
        not ProbePlanner(ProbePolicy(cfg), FakeExecutor().capabilities()).plan(built, NOW).requests
    )


def test_cross_scope_probe_and_hop_provenance_rejected():
    built = trace()
    hop = built.hops[0]
    with pytest.raises(ValueError):
        VirtualTrace.model_validate(
            built.model_copy(
                update={
                    "hops": (
                        hop.model_copy(update={"provenance": (provenance(env="other"),)}),
                        *built.hops[1:],
                    )
                }
            ).model_dump()
        )
    results = asyncio.run(
        ProbeRunner(ProbePolicy(config()), FakeExecutor()).execute(plan(), context())
    )
    other = built.model_copy(
        update={
            "hops": tuple(h for h in built.hops if h.reference != "service"),
            "subject": "slice",
            "relationships": (),
        }
    )
    with pytest.raises(ValueError):
        VirtualTraceBuilder(config().trace).attach(other, results)
    with pytest.raises(ValueError):
        Configuration(probes=config())


def test_executor_errors_are_sanitized_and_audited(caplog):
    fake = FakeExecutor()

    async def fail(request, addresses):
        raise RuntimeError("password=do-not-leak")

    fake.execute = fail
    with caplog.at_level("INFO", logger="agt_mcp.audit"):
        results = asyncio.run(ProbeRunner(ProbePolicy(config()), fake).execute(plan(), context()))
    assert results[0].result.error_category == "EXECUTOR_ERROR"
    assert "do-not-leak" not in caplog.text and "do-not-leak" not in str(results)


def test_denied_plan_cannot_relabel_itself_allowed():
    p = plan()
    p = p.model_copy(
        update={"requests": tuple(r.model_copy(update={"allowed": False}) for r in p.requests)}
    )
    fake = FakeExecutor()
    results = asyncio.run(ProbeRunner(ProbePolicy(config()), fake).execute(p, context()))
    assert all(p.result.status == ProbeStatus.BLOCKED for p in results) and not fake.calls


def test_probe_chain_cannot_skip_resolution_or_reorder_stages():
    p = plan()
    fake = FakeExecutor()
    runner = ProbeRunner(ProbePolicy(config()), fake)
    for requests in (p.requests[1:], tuple(reversed(p.requests))):
        with pytest.raises(ValueError):
            asyncio.run(runner.execute(p.model_copy(update={"requests": requests}), context()))
    assert not fake.calls


def test_probe_evidence_cannot_substitute_result_after_hashing():
    results = asyncio.run(
        ProbeRunner(ProbePolicy(config()), FakeExecutor()).execute(plan(), context())
    )
    from agt_mcp.probes.models import ProbeEvidence

    with pytest.raises(ValueError):
        ProbeEvidence.model_validate(
            results[0]
            .model_copy(
                update={
                    "result": results[0].result.model_copy(update={"status": ProbeStatus.FAILED})
                }
            )
            .model_dump()
        )


def test_scoped_dns_answer_and_numeric_metadata_target_blocked():
    cfg = config()
    policy = ProbePolicy(cfg)
    assert policy.addresses(plan(cfg).requests[0].target, ("fe80::1%eth0",)) == "INVALID_ADDRESS"
    blocked = plan(config(host="169.254.169.254"))
    assert all(not r.allowed for r in blocked.requests)


@pytest.mark.parametrize("protocol", ["tcp", "tls", "http"])
def test_planner_only_requests_applicable_protocols(protocol):
    p = plan(config(protocol=protocol))
    kinds = [r.probe_type for r in p.requests]
    assert kinds == [ProbeType.DNS, ProbeType.TCP] + (
        [ProbeType.TLS] if protocol == "tls" else [ProbeType.HTTP] if protocol == "http" else []
    )
