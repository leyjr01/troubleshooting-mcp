"""Canonical deterministic diagnostic fixtures without live API clients."""

import asyncio

from agt_mcp.configuration.troubleshooting import TroubleshootingConfig
from agt_mcp.core.runtime import CategoryResult
from agt_mcp.gateways.threescale.hypotheses import ThreeScaleHypothesisProvider
from agt_mcp.troubleshooting.catalog import (
    GenericHypothesisProvider,
    HypothesisCatalog,
    KubernetesHypothesisProvider,
)
from agt_mcp.troubleshooting.engine import TroubleshootingEngine
from tests.correlation_support import context, query, snapshot
from tests.correlation_support import engine as correlation_engine


def catalog():
    return HypothesisCatalog(
        (
            GenericHypothesisProvider(),
            KubernetesHypothesisProvider(),
            ThreeScaleHypothesisProvider(),
        )
    )


def diagnostic_snapshot(
    atoms=None, component_type="APICAST_PRODUCTION", version="2.16", coverage="completed"
):
    snap = snapshot(atoms)
    return snap.model_copy(
        update={
            "gateway_type": "threescale",
            "version": version,
            "components": (
                snap.components[0].model_copy(
                    update={"type": component_type, "expected": True, "presence": "PRESENT"}
                ),
            ),
            "coverage": tuple(
                CategoryResult(namespace="example", kind=kind, status=coverage, count=1)
                for kind in ("Service", "EndpointSlice", "Pod", "Deployment")
            ),
        }
    )


def engine(snap=None, **limits):
    return TroubleshootingEngine(
        correlation_engine(snap or diagnostic_snapshot()),
        catalog(),
        TroubleshootingConfig(**limits),
    )


def diagnose(subject=None, request=None):
    return asyncio.run((subject or engine()).diagnose(request or query(), context()))


def hypothesis(result, identifier):
    return next(h for h in result.hypotheses if h.definition_id == identifier)
