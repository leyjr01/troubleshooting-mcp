"""Fail-closed outbound projection. Raw text is not released in Sprint 0."""

import json
from collections.abc import Mapping
from typing import Literal, Protocol, runtime_checkable

from agt_mcp.core.errors import SanitizationError
from agt_mcp.core.models import Identifier, Model
from agt_mcp.core.operations import OperationContext


class SanitizedPayload(Model):
    environment_id: Identifier
    policy_version: Literal["conservative-1"] = "conservative-1"
    data: dict[str, str | int | bool | None]


@runtime_checkable
class Redactor(Protocol):
    def redact(self, text: str) -> str: ...


@runtime_checkable
class Sanitizer(Protocol):
    def sanitize(
        self, payload: Mapping[str, object], context: OperationContext
    ) -> SanitizedPayload: ...


class OpaqueTextRedactor:
    """No regex promise: all nonempty free text is withheld."""

    def redact(self, text: str) -> str:
        return "[REDACTED]" if text else ""


class ConservativeSanitizer:
    def sanitize(
        self, payload: Mapping[str, object], context: OperationContext
    ) -> SanitizedPayload:
        try:
            encoded = json.dumps(dict(payload), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, RecursionError):
            raise SanitizationError() from None
        if len(encoded) > context.max_payload_bytes:
            raise SanitizationError()
        # Outbound projection discards unknown keys too: keys may contain credentials.
        result: dict[str, str | int | bool | None] = {}
        status = payload.get("status")
        if isinstance(status, str) and status in ("healthy", "unhealthy", "unknown"):
            result["status"] = status
        count = payload.get("count")
        if type(count) is int and 0 <= count <= context.max_items:
            result["count"] = count
        result["content"] = "[REDACTED]"
        return SanitizedPayload(environment_id=context.environment_id, data=result)
