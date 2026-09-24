"""Bounded fixture adapter; no network, scheduler or persistent cache."""

import heapq
from typing import Literal

from agt_mcp.configuration.observability import ObservabilitySource
from agt_mcp.core.errors import AuthorizationError
from agt_mcp.observability.models import (
    AdapterBatch,
    ObservabilityQuery,
    SignalObservation,
    SignalType,
)
from agt_mcp.observability.scope import matches


class InMemoryObservabilityAdapter:
    def __init__(
        self, config: ObservabilitySource, observations: tuple[SignalObservation, ...] = ()
    ) -> None:
        self.config, self.observations = config, observations

    def capabilities(self) -> frozenset[SignalType]:
        return frozenset(self.config.usage) - {SignalType.EVENT}

    async def health(self) -> Literal["AVAILABLE", "UNAVAILABLE"]:
        return "AVAILABLE" if self.config.enabled else "UNAVAILABLE"

    async def query(self, query: ObservabilityQuery) -> AdapterBatch:
        allowed = {b.resource_id for b in self.config.bindings}
        if (
            not self.config.enabled
            or not query.resource_refs
            or query.environment_id != self.config.environment_id
            or not set(query.resource_refs) <= allowed
        ):
            raise AuthorizationError()
        selected = heapq.nsmallest(
            query.limit + 1,
            (x for x in self.observations if matches(x, query)),
            key=lambda x: (x.timestamp, x.resource_id, x.id),
        )
        return AdapterBatch(
            observations=tuple(selected[: query.limit]),
            warnings=("source_truncated",) if len(selected) > query.limit else (),
        )
