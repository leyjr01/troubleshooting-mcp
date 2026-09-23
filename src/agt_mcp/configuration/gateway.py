"""Explicit semantic discovery configuration; no credentials or endpoint URLs."""

from typing import Literal

from agt_mcp.core.models import Model
from agt_mcp.core.runtime import RuntimeName


class GatewayDiscoveryConfig(Model):
    namespace: RuntimeName | None = None
    version_profile: Literal["auto", "2.16"] = "auto"
    include_runtime_resources: bool = True
    include_dependencies: bool = True
