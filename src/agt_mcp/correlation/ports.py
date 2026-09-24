"""Canonical snapshot combines coherent evidence and topology; no vendor imports."""

from datetime import datetime
from typing import Protocol

from agt_mcp.core.execution import ExecutionContext
from agt_mcp.correlation.models import (
    CorrelatedKnowledge,
    CorrelationContext,
    CorrelationQuery,
    CorrelationSnapshot,
    HistoricalSimilarity,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class EvidenceTopologyProvider(Protocol):
    async def collect(
        self, query: CorrelationQuery, context: ExecutionContext
    ) -> CorrelationSnapshot: ...


class KnowledgeCorrelationProvider(Protocol):
    async def retrieve(
        self,
        context: CorrelationContext,
        snapshot: CorrelationSnapshot,
        execution: ExecutionContext,
    ) -> tuple[CorrelatedKnowledge, ...]: ...


class HistoricalIncidentProvider(Protocol):
    async def retrieve(
        self,
        context: CorrelationContext,
        snapshot: CorrelationSnapshot,
        execution: ExecutionContext,
    ) -> tuple[HistoricalSimilarity, ...]: ...
