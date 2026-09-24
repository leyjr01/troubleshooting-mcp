"""Small canonical snapshots and fake ports, independent of gateway implementations."""

import asyncio
from datetime import UTC, datetime, timedelta

from agt_mcp.configuration.correlation import CorrelationConfig
from agt_mcp.core.execution import ToolName
from agt_mcp.core.models import Confidence, Evidence, Provenance, Resource
from agt_mcp.correlation.engine import EvidenceCorrelationEngine
from agt_mcp.correlation.models import (
    ComponentContext,
    CorrelationQuery,
    CorrelationSnapshot,
    EvidenceAtom,
)
from agt_mcp.mcp.context import create_context
from agt_mcp.topology.models import Dependency, Topology
from tests.integration.test_mcp_server import config

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)


class Clock:
    value = NOW

    def now(self):
        return self.value


def confidence(level="medium"):
    return Confidence(
        level=level,
        rationale="observed",
        source_reliability="fixture",
        temporal_relevance="recent",
        topological_relevance="direct",
        historical_similarity="not used",
    )


def provenance(source="runtime", env="demo"):
    return Provenance(
        source_id=source,
        environment_id=env,
        retrieved_at=NOW,
        source_reference="runtime:" + "abc12345" * 5,
        content_sha256="a" * 64,
    )


def evidence(id, resource, state="unknown", seconds=-10, source="runtime", kind="status"):
    stamp = NOW + timedelta(seconds=seconds) if seconds is not None else None
    item = Evidence(
        id=id,
        environment_id="demo",
        timestamp=stamp or NOW,
        source=provenance(source),
        type="observation",
        resource_id=resource,
        observation=state,
        raw_reference="snapshot",
        confidence=confidence(),
    )
    return EvidenceAtom(
        evidence=item, occurred_at=stamp, kind=kind, state=state, origin=source + ":" + resource
    )


def snapshot(atoms=None):
    nodes = tuple(
        Resource(
            id=id,
            environment_id="demo",
            kind=kind,
            name=id,
            provider="fixture",
            namespace="example",
        )
        for id, kind in (
            ("service", "service"),
            ("slice", "endpointslice"),
            ("pod", "pod"),
            ("deployment", "deployment"),
        )
    )
    edges = tuple(
        Dependency(
            id="edge-" + str(i),
            source=s,
            target=t,
            relationship=r,
            source_of_information=provenance(),
            confidence=confidence(),
        )
        for i, (s, t, r) in enumerate(
            (
                ("service", "slice", "has_endpointslice"),
                ("slice", "pod", "targets"),
                ("deployment", "pod", "owns"),
            )
        )
    )
    return CorrelationSnapshot(
        environment_id="demo",
        observed_at=NOW,
        topology=Topology(environment_id="demo", nodes=nodes, edges=edges),
        evidence=atoms
        if atoms is not None
        else (
            evidence("no-endpoints", "service", "unavailable"),
            evidence("slice-state", "slice", "unavailable"),
            evidence("crash-loop", "pod", "unavailable", -5),
            evidence("restart", "pod", kind="event", seconds=-3),
        ),
        installation_id="installation",
        components=(
            ComponentContext(
                id="component",
                installation_id="installation",
                type="apicast-production",
                resources=tuple(n.id for n in nodes),
                provenance=(provenance(),),
            ),
        ),
    )


class Provider:
    def __init__(self, value):
        self.value, self.calls = value, 0

    async def collect(self, query, context):
        self.calls += 1
        return self.value


class References:
    def __init__(self, value=(), error=None):
        self.value, self.error, self.calls = value, error, 0

    async def retrieve(self, *args):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


def engine(snap=None, **bounds):
    return EvidenceCorrelationEngine(
        Provider(snap or snapshot()),
        References(),
        References(),
        CorrelationConfig(**bounds),
        Clock(),
    )


def context(tool=ToolName.CORRELATE_EVIDENCE):
    return create_context(config(), tool, "demo", None)


def query(**values):
    return CorrelationQuery(
        **(
            {"resource_id": "service", "include_knowledge": False, "include_history": False}
            | values
        )
    )


def run(subject=None, request=None):
    return asyncio.run((subject or engine()).correlate(request or query(), context()))
