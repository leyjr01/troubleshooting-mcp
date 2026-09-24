"""Small provider-neutral read-only interface."""

from typing import Literal, Protocol

from agt_mcp.observability.models import AdapterBatch, ObservabilityQuery, SignalType


class ObservabilityAdapter(Protocol):
    def capabilities(self) -> frozenset[SignalType]: ...
    async def health(self) -> Literal["AVAILABLE", "UNAVAILABLE"]: ...
    async def query(self, query: ObservabilityQuery) -> AdapterBatch: ...
