"""Structured event projection with bounded identifiers; never payloads/exceptions."""

import logging
from typing import Literal

from pydantic import Field

from agt_mcp.core.errors import ErrorCode
from agt_mcp.core.models import Identifier, Model


class AuditEvent(Model):
    event: Literal["operation_started", "operation_finished", "operation_rejected"]
    environment_id: Identifier
    request_id: Identifier
    correlation_id: Identifier
    adapter: Identifier
    datasource: Identifier | None = None
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    result_status: Literal["ok", "error", "cancelled"]
    error_category: ErrorCode | None = None


def emit_event(logger: logging.Logger, event: AuditEvent) -> None:
    """Emit only the validated envelope; free-form log messages are forbidden here."""
    logger.info(event.model_dump_json())
