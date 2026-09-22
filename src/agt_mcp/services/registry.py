"""Instance-owned adapter registry; metadata is scoped before resolution."""

from dataclasses import dataclass

from agt_mcp.core.errors import AuthorizationError, ConfigurationError, UnsupportedCapabilityError
from agt_mcp.datasources.base.adapter import DataSourceAdapter
from agt_mcp.gateways.base.adapter import GatewayAdapter


@dataclass(frozen=True)
class AdapterEntry[T: (GatewayAdapter, DataSourceAdapter)]:
    id: str
    environment_id: str
    adapter: T


class AdapterRegistry[T: (GatewayAdapter, DataSourceAdapter)]:
    def __init__(self) -> None:
        self._entries: dict[str, AdapterEntry[T]] = {}
        self._sealed = False

    def register(self, entry: AdapterEntry[T]) -> None:
        if self._sealed or entry.id in self._entries:
            raise ConfigurationError()
        self._entries[entry.id] = entry

    def seal(self) -> None:
        self._sealed = True

    def resolve(self, identifier: str, environment_id: str) -> T:
        entry = self._entries.get(identifier)
        if entry is None:
            raise UnsupportedCapabilityError()
        if entry.environment_id != environment_id:
            raise AuthorizationError()
        return entry.adapter

    def entries(self, environment_id: str | None = None) -> tuple[AdapterEntry[T], ...]:
        return tuple(
            entry
            for entry in self._entries.values()
            if environment_id is None or entry.environment_id == environment_id
        )
