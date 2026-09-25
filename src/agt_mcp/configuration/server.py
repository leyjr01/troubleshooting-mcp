"""Loopback defaults and explicitly authenticated container HTTP configuration."""

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from agt_mcp.core.execution import LEGACY_TOOLS, Capability, ToolName
from agt_mcp.core.models import Identifier, Model, Text
from agt_mcp.credentials.providers import CredentialReference


class AuthorizationConfig(Model):
    mode: Literal["deny-all", "local-read-only"] = "deny-all"
    principal: Literal["local-client"] = "local-client"
    environment_ids: tuple[Identifier, ...] = ()
    permissions: frozenset[Capability] = frozenset()


class ServerConfig(Model):
    name: Text = "API Gateway Troubleshooting MCP"
    transport: Literal["stdio", "http"] = "stdio"
    # ADR-0020: opt-in remote binding requires authentication in protected_http.
    host: Literal["127.0.0.1", "0.0.0.0"] = "127.0.0.1"  # nosec B104
    allowed_hosts: tuple[str, ...] = ("127.0.0.1",)
    http_token: CredentialReference | None = None
    shutdown_timeout_seconds: int = Field(default=30, ge=1, le=60)
    port: int = Field(default=8000, ge=1024, le=65535)
    log_level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    request_timeout_seconds: float = Field(default=30, gt=0, le=300)
    authorization: AuthorizationConfig = AuthorizationConfig()
    enabled_tools: frozenset[ToolName] = LEGACY_TOOLS

    @model_validator(mode="after")
    def protected_http(self) -> Self:
        if not self.allowed_hosts or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", h)
            for h in self.allowed_hosts
        ):
            raise ValueError("explicit hostnames required; no wildcard, URL or port")
        # Comparing the configured bind address is the fail-closed auth guard.
        if self.host == "0.0.0.0" and (  # nosec B104
            self.transport != "http" or self.http_token is None
        ):
            raise ValueError("non-loopback requires explicit authenticated HTTP")
        if self.http_token and (
            self.transport != "http"
            or self.http_token.provider not in {"environment", "mounted-file"}
            or self.http_token.environment_id not in self.authorization.environment_ids
        ):
            raise ValueError("invalid HTTP credential scope or provider")
        return self


class MCPConfig(Model):
    server: ServerConfig = ServerConfig()
