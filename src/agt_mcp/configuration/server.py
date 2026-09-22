"""Local-only server contract; no anonymous remote deployment mode."""

from typing import Literal

from pydantic import Field

from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.core.models import Identifier, Model, Text


class AuthorizationConfig(Model):
    mode: Literal["deny-all", "local-read-only"] = "deny-all"
    principal: Literal["local-client"] = "local-client"
    environment_ids: tuple[Identifier, ...] = ()
    permissions: frozenset[Capability] = frozenset()


class ServerConfig(Model):
    name: Text = "API Gateway Troubleshooting MCP"
    transport: Literal["stdio", "http"] = "stdio"
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    log_level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    request_timeout_seconds: float = Field(default=30, gt=0, le=300)
    authorization: AuthorizationConfig = AuthorizationConfig()
    enabled_tools: frozenset[ToolName] = frozenset(ToolName)


class MCPConfig(Model):
    server: ServerConfig = ServerConfig()
