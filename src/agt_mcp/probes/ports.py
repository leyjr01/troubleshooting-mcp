"""Injected observation executors. Core knows no socket or HTTP client."""

from typing import Protocol

from agt_mcp.probes.models import ProbeCapability, ProbeObservation, ProbeRequest


class ProbeFailure(Exception):
    def __init__(
        self,
        category: str,
        observation: ProbeObservation | None = None,
        blocked: bool = False,
    ) -> None:
        self.category = category
        self.observation = observation or ProbeObservation()
        self.blocked = blocked


class ProbeExecutor(Protocol):
    def capabilities(self) -> frozenset[ProbeCapability]: ...

    async def execute(
        self, request: ProbeRequest, addresses: tuple[str, ...]
    ) -> ProbeObservation: ...
