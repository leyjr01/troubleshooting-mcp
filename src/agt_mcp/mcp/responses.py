"""Stable structured result envelope, independent of SDK result internals."""

from pydantic import JsonValue

from agt_mcp.core.models import Identifier, Model


class ToolResponse(Model):
    ok: bool
    request_id: Identifier
    correlation_id: Identifier
    environment_id: Identifier
    data: dict[str, JsonValue] | None = None
    error: str | None = None
